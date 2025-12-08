import os
from datetime import datetime
from pyexpat.errors import messages
import pytest
from unittest.mock import MagicMock, patch, call

from tests.conftest import (
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
    message_bus,
)

from src.controller_helper import assign_serial_id, dump_database_for_experiment


@pytest.fixture
def data_path():
    with patch("src.controller_helper.data_path", new="test_data") as mock_data_path:
        yield "test_data"


class TestAssignSerialID:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        state = mock_state("ready", mock_experiment_dict, mock_setpoints)
        return state

    def test_updates_serial_id_correctly_empty_dir(self, state, data_path):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"
        assert state.exp_file == None
        current_year = str(datetime.now().year)[-2:]

        with patch("os.listdir", return_value=[]) as mock_listdir, patch(
            "os.rename"
        ) as mock_rename:
            assign_serial_id(state)

            assert mock_listdir.called
            assert mock_rename.called

        expected_uid = f"D{current_year}-001"
        assert state.experiment_uid == expected_uid
        assert state.exp_file == f"{data_path}/{expected_uid}.json"

    def test_updates_serial_id_correctly_non_empty_dir(self, state, data_path):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"
        assert state.exp_file == None
        current_year = str(datetime.now().year)[-2:]

        with patch("os.rename") as mock_rename, patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = [
                f"D{current_year}-041.json",
                f"D{current_year}-005.json",
                f"D{current_year}-514.txt",
                "D21-365.json",
            ]
            assign_serial_id(state)

        expected_uid = f"D{current_year}-042"
        assert state.experiment_uid == expected_uid
        assert state.exp_file == f"{data_path}/{expected_uid}.json"

    def test_moves_file_correctly(self, state, data_path):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"

        current_year = str(datetime.now().year)[-2:]
        d_path = f"{data_path}/D{current_year}-41.test_temp_exp.json"
        tmp_path = f"{data_path}/tmp/123.test_temp_exp.json"
        state.exp_file = tmp_path
        assert not os.path.exists(d_path)
        assert not os.path.exists(tmp_path)
        try:
            os.makedirs(os.path.dirname(d_path), exist_ok=True)
            os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
            with open(d_path, "w") as f:
                f.write("The answer is 42")
            with open(tmp_path, "w") as f:
                f.write("But what is the question?")
            assert os.path.exists(d_path)
            assert os.path.exists(tmp_path)

            assign_serial_id(state)

            expected_file = f"{data_path}/D{current_year}-042.json"
            assert state.exp_file == expected_file
            assert os.path.exists(d_path)
            assert os.path.exists(expected_file)
            assert not os.path.exists(tmp_path)
        except AssertionError as e:
            raise e
        finally:
            if os.path.exists(d_path):
                os.remove(d_path)
            if os.path.exists(expected_file):
                os.remove(expected_file)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(state.exp_file):
                if t.time() - os.path.getctime(state.exp_file) < 15:
                    os.remove(state.exp_file)


class TestDatabaseDump:

    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        state = mock_state("running", mock_experiment_dict, mock_setpoints)
        return state

    @pytest.fixture(autouse=True)
    def dump_mocks(self):
        with patch("src.controller_helper.config") as mock_config, patch(
            "os.getenv"
        ) as mock_getenv, patch(
            "src.controller_helper.influxdb_client"
        ) as mock_influx, patch(
            "os.path.exists"
        ) as mock_path_exists, patch(
            "os.makedirs"
        ) as mock_makedirs:
            mock_config.__getitem__.side_effect = lambda key: {
                "influxdb": {
                    "url": "http://localhost:8086",
                    "org": "my_org",
                    "buckets": ["bucket1", "bucket2", "bucket3"],
                }
            }[key]
            env_values = {}
            mock_getenv.side_effect = lambda var, default=None: env_values.get(
                var, default
            )
            mock_influx_client = MagicMock()
            mock_influx_client.query_api.return_value = MagicMock()
            mock_csv_data = MagicMock()
            mock_bucket_data = [
                ["#some", "data", "here"],
                ["maybe", "some", "info"],
                ["and", "finally", "values"],
                ["0.123", "2024-03-05T14:26:43.715914833Z", "measurement"],
            ]
            mock_csv_data.to_values.return_value = mock_bucket_data
            mock_query_csv = mock_influx_client.query_api.return_value.query_csv
            mock_query_csv.return_value = mock_csv_data
            mock_influx.InfluxDBClient.return_value = mock_influx_client
            yield {
                "env_values": env_values,
                "getenv": mock_getenv,
                "mock_influx": mock_influx,
                "influx_client": mock_influx_client,
                "mock_query_csv": mock_query_csv,
                "mock_bucket_data": mock_bucket_data,
                "path_exists": mock_path_exists,
                "makedirs": mock_makedirs,
            }

    def test_warns_on_missing_token(self, state, dump_mocks, message_bus):
        assert dump_mocks["getenv"]("INFLUX_TOKEN") is None
        with patch("builtins.print") as mock_print:
            dump_database_for_experiment(state)

            mock_print.assert_called_once_with(
                "INFLUX_TOKEN environment variable not set. Cannot dump influx database."
            )
            messages = message_bus.get_messages(decoded=True)
            assert len(messages) == 1
            assert messages[0].topic == "error/controller"
            assert (
                "Error dumping database. INFLUX_TOKEN not set." in messages[0].payload
            )

    def test_database_dump(self, state, dump_mocks, data_path):
        dump_mocks["env_values"].update({"INFLUX_TOKEN": "dummy_token"})
        t0 = datetime(2024, 1, 2, 3, 45, 6)
        t0_s = t0.isoformat()
        tf = datetime(2025, 2, 3, 4, 56, 7)
        tf_s = tf.isoformat()
        state.experiment_start_time = t0
        tmp_path = f"{data_path}/tmp/123.test_temp_exp.json"
        state.exp_file = tmp_path
        dump_mocks["path_exists"].return_value = False
        assert not os.path.exists(tmp_path)
        with patch("src.controller_helper.datetime") as mock_datetime, patch(
            "builtins.open", create=True
        ) as mock_open, patch(
            "src.controller_helper.csv.writer"
        ) as mock_csv_writer, patch(
            "builtins.print"
        ) as mock_print:
            mock_datetime.now.return_value = tf
            cw_instance = MagicMock()
            mock_csv_writer.return_value = cw_instance
            dump_database_for_experiment(state)

            mock_datetime.now.assert_called_once_with()
            dump_mocks["mock_influx"].InfluxDBClient.assert_called_once_with(
                url="http://localhost:8086",
                token="dummy_token",
                org="my_org",
            )
            dump_mocks["influx_client"].query_api.assert_called_once_with()
            dump_mocks["makedirs"].assert_called_once_with(
                f"{data_path}/tmp/123.test_temp_exp"
            )
            assert dump_mocks["mock_query_csv"].call_args_list == [
                call(
                    org="my_org",
                    query=f'from(bucket: "bucket1") |> range(start: {t0_s}Z, stop: {tf_s}Z)',
                ),
                call(
                    org="my_org",
                    query=f'from(bucket: "bucket2") |> range(start: {t0_s}Z, stop: {tf_s}Z)',
                ),
                call(
                    org="my_org",
                    query=f'from(bucket: "bucket3") |> range(start: {t0_s}Z, stop: {tf_s}Z)',
                ),
            ]
            assert mock_open.call_args_list == [
                call(
                    f"{data_path}/tmp/123.test_temp_exp/bucket1.csv",
                    "w",
                    newline="",
                ),
                call(
                    f"{data_path}/tmp/123.test_temp_exp/bucket2.csv",
                    "w",
                    newline="",
                ),
                call(
                    f"{data_path}/tmp/123.test_temp_exp/bucket3.csv",
                    "w",
                    newline="",
                ),
            ]
            cw_instance.writerows.assert_has_calls(
                [
                    call(dump_mocks["mock_bucket_data"]),
                    call(dump_mocks["mock_bucket_data"]),
                    call(dump_mocks["mock_bucket_data"]),
                ]
            )
            mock_print.assert_called_once_with(
                f"  Influx database for experiment {state.experiment_uid} saved at {data_path}/tmp/123.test_temp_exp."
            )
