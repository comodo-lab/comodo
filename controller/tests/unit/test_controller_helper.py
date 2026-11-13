import csv
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import time as t
import pytest
from unittest.mock import MagicMock, patch, call

from influxdb_client.client.flux_table import FluxRecord

from tests.conftest import (
    message_bus,
    mqtt_mocks,
    mock_state,
)

from src.controller_helper import (
    get_env_or_secret,
    assign_serial_id,
    dump_database_for_experiment,
    dump_and_clear,
    move_experiment_file,
    dump_database,
    write_dump_failure,
    write_history,
    write_data,
    running_experiment_path,
    save_running_experiment,
    clear_running_experiment,
    recover_lost_experiment,
)


@pytest.fixture
def data_path():
    with patch("src.controller_helper.data_path", new="test_data") as mock_data_path:
        yield "test_data"


class TestGetEnvOrSecret:
    @pytest.fixture
    def env_or_secret_mocks(self):
        with patch("os.getenv") as mock_getenv, patch("builtins.open") as mock_open:
            env_values = {}
            mock_getenv.side_effect = lambda var, default=None: env_values.get(
                var, default
            )
            mock_file = MagicMock()
            mock_file.read.return_value = "secret_value\n"
            mock_open.return_value.__enter__.return_value = mock_file
            yield {
                "env_values": env_values,
                "getenv": mock_getenv,
                "open": mock_open,
            }

    def test_env_var_set(self, env_or_secret_mocks):
        mocks = env_or_secret_mocks
        mocks["env_values"].update({"MY_ENV_VAR": "env_value"})

        value = get_env_or_secret("MY_ENV_VAR")
        assert value == "env_value"
        env_or_secret_mocks["getenv"].assert_called_once_with("MY_ENV_VAR", None)
        env_or_secret_mocks["open"].assert_not_called()

    def test_secret_file_set(self, env_or_secret_mocks):
        mocks = env_or_secret_mocks
        mocks["env_values"].update({"MY_SECRET_FILE": "/path/to/secret"})

        value = get_env_or_secret("MY_ENV_VAR", "MY_SECRET_FILE")

        env_or_secret_mocks["getenv"].call_args_list == [
            call("MY_ENV_VAR", None),
            call("MY_SECRET_FILE", None),
        ]
        env_or_secret_mocks["open"].assert_called_once_with("/path/to/secret", "r")
        assert value == "secret_value"

    def test_env_takes_precedence(self, env_or_secret_mocks):
        mocks = env_or_secret_mocks
        mocks["env_values"].update(
            {
                "MY_ENV_VAR": "env_value",
                "MY_SECRET_FILE": "/path/to/secret",
            }
        )

        value = get_env_or_secret("MY_ENV_VAR", "MY_SECRET_FILE", "default_val")

        env_or_secret_mocks["getenv"].assert_any_call("MY_ENV_VAR", None)
        env_or_secret_mocks["open"].assert_not_called()
        assert value == "env_value"

    def test_neither_set_returns_default(self, env_or_secret_mocks):
        mocks = env_or_secret_mocks

        value = get_env_or_secret("MY_ENV_VAR", "MY_SECRET_FILE", "default_val")

        env_or_secret_mocks["getenv"].call_args_list == [
            call("MY_ENV_VAR", None),
            call("MY_SECRET_FILE", None),
        ]
        env_or_secret_mocks["open"].assert_not_called()
        assert value == "default_val"

    def test_secret_file_not_found_returns_default(self, env_or_secret_mocks):
        mocks = env_or_secret_mocks
        mocks["env_values"].update({"MY_SECRET_FILE": "/path/to/missing_secret"})
        mocks["open"].side_effect = FileNotFoundError

        value = get_env_or_secret("MY_ENV_VAR", "MY_SECRET_FILE", "default_val")

        env_or_secret_mocks["getenv"].call_args_list == [
            call("MY_ENV_VAR", None),
            call("MY_SECRET_FILE", None),
        ]
        env_or_secret_mocks["open"].assert_called_once_with(
            "/path/to/missing_secret", "r"
        )
        assert value == "default_val"


class TestAssignSerialID:
    @pytest.fixture
    def state(self, mock_state):
        state = mock_state("idle")
        state.status = "validating"
        return state

    def test_updates_serial_id_correctly_empty_dir(self, state, data_path):
        assert state.experiment_id == None
        assert state.exp_file == None
        current_year = str(datetime.now().year)[-2:]

        with (
            patch("os.listdir", return_value=[]) as mock_listdir,
            patch("os.rename") as mock_rename,
        ):
            assign_serial_id(state)

            assert mock_listdir.called
            assert mock_rename.called

        expected_uid = f"D{current_year}-001"
        assert state.experiment_id == expected_uid
        assert state.exp_file == f"{data_path}/{expected_uid}.json"

    def test_updates_serial_id_correctly_non_empty_dir(self, state, data_path):
        assert state.experiment_id == None
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
        assert state.experiment_id == expected_uid
        assert state.exp_file == f"{data_path}/{expected_uid}.json"

    def test_counts_dumped_experiments(self, state, data_path):
        # Once dumped, an experiment's file is moved to its directory
        current_year = str(datetime.now().year)[-2:]

        with patch("os.rename"), patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = [
                f"D{current_year}-041",
                f"D{current_year}-042.json",
                f"D{current_year}-043",
                "tmp",
                "running_experiment.json",
            ]
            assign_serial_id(state)

        expected_uid = f"D{current_year}-044"
        assert state.experiment_id == expected_uid
        assert state.exp_file == f"{data_path}/{expected_uid}.json"

    def test_moves_file_correctly(self, state, data_path):
        assert state.experiment_id == None

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


def record(time, topic, field, value):
    """A record from an InfluxDB query, time in seconds since 2024-01-02T03:45:06Z."""
    return FluxRecord(
        table=0,
        values={
            "_time": T0 + timedelta(seconds=time),
            "topic": topic,
            "_field": field,
            "_value": value,
        },
    )


T0 = datetime(2024, 1, 2, 3, 45, 6, tzinfo=timezone.utc)
FURNACE = "instruments/furnace/temperature"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


class TestDumpInBackground:

    @pytest.fixture
    def state(self, mock_state):
        state = mock_state("running")
        state.experiment_id = "D123-456"
        state.exp_file = "data/D123-456.json"
        state.experiment_start_time = T0.replace(tzinfo=None)
        return state

    def test_starts_a_thread(self, state):
        tf = datetime(2024, 1, 2, 3, 46, 0)
        with (
            patch("src.controller_helper.threading.Thread") as mock_thread,
            patch("src.controller_helper.datetime") as mock_datetime,
        ):
            mock_datetime.now.return_value = tf
            dump_database_for_experiment(state)

        mock_thread.assert_called_once()
        kwargs = mock_thread.call_args.kwargs
        assert kwargs["target"] == dump_and_clear
        assert kwargs["daemon"] is True
        experiment, end, on_done = kwargs["args"]
        # A copy, as the state is reset while the dump runs
        assert experiment is not state
        assert experiment.experiment_id == "D123-456"
        assert experiment.exp_file == "data/D123-456.json"
        assert experiment.experiment_start_time == state.experiment_start_time
        assert end == tf
        assert on_done is None
        mock_thread.return_value.start.assert_called_once_with()

    @pytest.fixture
    def dump_and_clear_mocks(self):
        # A single mock, with each step as a child, to check the order they are called in
        calls = MagicMock()
        with (
            patch("src.controller_helper.INFLUX_WRITE_WAIT", 5),
            patch("src.controller_helper.time.sleep", calls.sleep),
            patch("src.controller_helper.dump_database", calls.dump),
            patch("src.controller_helper.move_experiment_file", calls.move),
            patch("src.controller_helper.clear_running_experiment", calls.clear),
        ):
            yield calls

    def test_waits_dumps_moves_and_clears(self, dump_and_clear_mocks):
        calls = dump_and_clear_mocks
        experiment = SimpleNamespace(experiment_id="D123-456")
        dump_and_clear(experiment, "tf", calls.on_done)

        # Waits for Telegraf to write everything, before querying the database
        assert calls.mock_calls == [
            call.sleep(5),
            call.dump(experiment, "tf"),
            call.move(experiment),
            call.clear("D123-456"),
            call.on_done(),
        ]

    def test_without_on_done(self, dump_and_clear_mocks):
        calls = dump_and_clear_mocks
        experiment = SimpleNamespace(experiment_id="D123-456")
        dump_and_clear(experiment, "tf")

        assert calls.mock_calls == [
            call.sleep(5),
            call.dump(experiment, "tf"),
            call.move(experiment),
            call.clear("D123-456"),
        ]

    def test_clears_and_calls_on_done_even_if_the_dump_fails(
        self, dump_and_clear_mocks
    ):
        calls = dump_and_clear_mocks
        calls.dump.side_effect = RuntimeError("boom")
        experiment = SimpleNamespace(experiment_id="D123-456")
        with pytest.raises(RuntimeError):
            dump_and_clear(experiment, "tf", calls.on_done)

        # Without moving the experiment file
        assert calls.mock_calls == [
            call.sleep(5),
            call.dump(experiment, "tf"),
            call.clear("D123-456"),
            call.on_done(),
        ]

    def test_moves_experiment_file_to_its_directory(self, tmp_path):
        exp_file = tmp_path / "D123-456.json"
        exp_file.write_text("{}")
        move_experiment_file(SimpleNamespace(exp_file=str(exp_file)))

        assert not exp_file.exists()
        assert (tmp_path / "D123-456" / "D123-456.json").read_text() == "{}"


class TestDatabaseDump:

    @pytest.fixture
    def experiment(self, tmp_path):
        return SimpleNamespace(
            experiment_id="D123-456",
            exp_file=f"{tmp_path}/D123-456.json",
            experiment_start_time=T0.replace(tzinfo=None),
        )

    @pytest.fixture(autouse=True)
    def dump_mocks(self):
        with (
            patch("os.getenv") as mock_getenv,
            patch(
                "src.controller_helper.get_env_or_secret", return_value=None
            ) as mock_get_secret,
            patch("src.controller_helper.influxdb_client") as mock_influx,
            patch("src.controller_helper.pub_err") as mock_publish_error,
            patch("src.controller_helper.time.sleep") as mock_sleep,
            # Not the real values, to check they are not hard-coded
            patch("src.controller_helper.DUMP_ATTEMPTS", 4),
            patch("src.controller_helper.DUMP_RETRY_WAIT", 7),
            patch("src.controller_helper.INFLUX_TIMEOUT_MS", 1234),
        ):
            env_values = {
                "INFLUX_BUCKET": "bucket1,bucket2",
                "INFLUX_HOST": "localhost",
                "INFLUX_ORG": "my_org",
            }
            mock_getenv.side_effect = lambda var, default=None: env_values.get(
                var, default
            )
            mock_client = mock_influx.InfluxDBClient.return_value
            mock_client.__enter__.return_value = mock_client
            mock_query = mock_client.query_api.return_value.query
            # One table per bucket
            mock_query.side_effect = [
                [
                    SimpleNamespace(
                        records=[
                            record(0.5, f"{FURNACE}/measurement", "value", 25.0),
                            record(0.2, f"{FURNACE}/setpoint", "value", 30.0),
                        ]
                    )
                ],
                [
                    SimpleNamespace(
                        records=[
                            record(
                                0.1, "controller/heartbeat", "state_status", "running"
                            )
                        ]
                    )
                ],
            ]
            yield {
                "pub_err": mock_publish_error,
                "getenv": mock_getenv,
                "get_secret": mock_get_secret,
                "mock_influx": mock_influx,
                "mock_client": mock_client,
                "mock_query": mock_query,
                "sleep": mock_sleep,
                "attempts": 4,
                "retry_wait": 7,
                "timeout_ms": 1234,
            }

    def test_warns_on_missing_token(self, experiment, dump_mocks, tmp_path):
        assert dump_mocks["getenv"]("INFLUX_TOKEN") is None  # Adds a call to getenv
        tf = (T0 + timedelta(seconds=2)).replace(tzinfo=None)
        dump_database(experiment, tf)

        assert dump_mocks["getenv"].call_args_list == [
            call("INFLUX_TOKEN"),  # Call added by first line of this test
            call("INFLUX_BUCKET", "comodo"),
            call("INFLUX_HOST", "localhost"),
            call("INFLUX_ORG", "comodo"),
        ]
        dump_mocks["get_secret"].assert_called_once_with(
            "INFLUX_TOKEN", "INFLUX_TOKEN_FILE", None
        )
        interval = {
            "t0": f"{T0.replace(tzinfo=None).isoformat()}Z",
            "tf": f"{tf.isoformat()}Z",
        }
        dump_mocks["pub_err"].database_error.assert_called_once_with(
            "Cannot dump influx database. INFLUX_TOKEN not set. "
            f"Experiment time interval recorded in dump.fail: {json.dumps(interval)}"
        )
        dump_mocks["mock_query"].assert_not_called()
        dump_mocks["sleep"].assert_not_called()
        dump_fail = tmp_path / "D123-456" / "dump.fail"
        assert json.loads(dump_fail.read_text()) == interval

    def test_database_dump_error(self, experiment, dump_mocks, tmp_path, capsys):
        dump_mocks["get_secret"].return_value = "dummy_token"
        dump_mocks["mock_query"].side_effect = Exception("Database error")
        tf = (T0 + timedelta(seconds=2)).replace(tzinfo=None)
        dump_database(experiment, tf)

        attempts, retry_wait = dump_mocks["attempts"], dump_mocks["retry_wait"]
        # Tries DUMP_ATTEMPTS times, waiting between them, with a new connection each time
        assert dump_mocks["mock_query"].call_count == attempts
        assert dump_mocks["mock_influx"].InfluxDBClient.call_count == attempts
        assert dump_mocks["sleep"].call_args_list == [call(retry_wait)] * (attempts - 1)
        # Warns on the logs after each failed attempt but the last, which publishes the error
        captured = capsys.readouterr()
        for attempt in range(1, attempts):
            assert (
                f"Warning: could not dump influx database for experiment D123-456"
                f" (attempt {attempt} of {attempts}): Database error. Retrying in {retry_wait} s."
            ) in captured.out
        assert f"attempt {attempts} of" not in captured.out
        interval = {
            "t0": f"{T0.replace(tzinfo=None).isoformat()}Z",
            "tf": f"{tf.isoformat()}Z",
        }
        dump_mocks["pub_err"].database_error.assert_called_once_with(
            f"Could not dump influx database after {attempts} attempts: Database error"
            f" Experiment time interval recorded in dump.fail: {json.dumps(interval)}"
        )
        dump_fail = tmp_path / "D123-456" / "dump.fail"
        assert json.loads(dump_fail.read_text()) == interval

    def test_retries_after_a_failed_attempt(
        self, experiment, dump_mocks, tmp_path, capsys
    ):
        dump_mocks["get_secret"].return_value = "dummy_token"
        bucket1 = [
            SimpleNamespace(
                records=[record(0.5, f"{FURNACE}/measurement", "value", 25.0)]
            )
        ]
        bucket2 = [
            SimpleNamespace(
                records=[record(0.1, "controller/heartbeat", "state_status", "running")]
            )
        ]
        # The first attempt fails on the second bucket, after getting the first
        dump_mocks["mock_query"].side_effect = [
            bucket1,
            Exception("Timed out"),
            bucket1,
            bucket2,
        ]
        dump_database(experiment, (T0 + timedelta(seconds=2)).replace(tzinfo=None))

        dump_mocks["sleep"].assert_called_once_with(dump_mocks["retry_wait"])
        captured = capsys.readouterr()
        assert (
            f"(attempt 1 of {dump_mocks['attempts']}): Timed out. Retrying"
            in captured.out
        )
        assert "saved at" in captured.out
        dump_mocks["pub_err"].database_error.assert_not_called()
        exp_dir = tmp_path / "D123-456"
        assert not (exp_dir / "dump.fail").exists()
        # Only the records of the successful attempt, without those of the failed one
        assert read_csv(exp_dir / "history.csv") == [
            ["time", "topic", "field", "value"],
            [iso(0.1), "controller/heartbeat", "state_status", "running"],
            [iso(0.5), f"{FURNACE}/measurement", "value", "25.0"],
        ]

    def test_database_dump(self, experiment, dump_mocks, tmp_path, capsys):
        dump_mocks["get_secret"].return_value = "dummy_token"
        tf = (T0 + timedelta(seconds=2)).replace(tzinfo=None)
        dump_database(experiment, tf)

        dump_mocks["mock_influx"].InfluxDBClient.assert_called_once_with(
            url="http://localhost:8086",
            token="dummy_token",
            org="my_org",
            timeout=dump_mocks["timeout_ms"],
        )
        # The connection is closed once done
        dump_mocks["mock_client"].__exit__.assert_called_once()
        t0_s = experiment.experiment_start_time.isoformat()
        assert dump_mocks["mock_query"].call_args_list == [
            call(
                f'from(bucket: "{bucket}") |> range(start: {t0_s}Z, stop: {tf.isoformat()}Z)',
                org="my_org",
            )
            for bucket in ["bucket1", "bucket2"]
        ]
        # The records of every bucket, in time order
        exp_dir = tmp_path / "D123-456"
        assert read_csv(exp_dir / "history.csv") == [
            ["time", "topic", "field", "value"],
            [
                (T0 + timedelta(seconds=0.1)).isoformat(),
                "controller/heartbeat",
                "state_status",
                "running",
            ],
            [
                (T0 + timedelta(seconds=0.2)).isoformat(),
                f"{FURNACE}/setpoint",
                "value",
                "30.0",
            ],
            [
                (T0 + timedelta(seconds=0.5)).isoformat(),
                f"{FURNACE}/measurement",
                "value",
                "25.0",
            ],
        ]
        assert read_csv(exp_dir / "data.csv") == [
            [
                "time",
                "elapsed_s",
                "furnace/temperature",
                "furnace/temperature_setpoint",
            ],
            [iso(0.2), "0.2", "", "30.0"],
            [iso(0.5), "0.5", "25.0", ""],
        ]
        dump_mocks["pub_err"].database_error.assert_not_called()
        dump_mocks["sleep"].assert_not_called()
        assert not (exp_dir / "dump.fail").exists()
        captured = capsys.readouterr()
        assert (
            f"Influx database for experiment D123-456 saved at {exp_dir}."
            in captured.out
        )


class TestWriteDumpFailure:

    def test_writes_the_experiment_interval(self, tmp_path):
        exp_dir = tmp_path / "D123-456"
        t0 = T0.replace(tzinfo=None)
        tf = t0 + timedelta(hours=2)

        message = write_dump_failure(str(exp_dir), t0, tf)

        interval = {"t0": f"{t0.isoformat()}Z", "tf": f"{tf.isoformat()}Z"}
        assert json.loads((exp_dir / "dump.fail").read_text()) == interval
        assert (
            message
            == f"Experiment time interval recorded in dump.fail: {json.dumps(interval)}"
        )

    def test_returns_the_error_if_it_cannot_write(self, tmp_path, capsys):
        # Create a file where the directory should be to make it fail
        exp_dir = tmp_path / "D123-456"
        exp_dir.write_text("")
        t0 = T0.replace(tzinfo=None)
        message = write_dump_failure(str(exp_dir), t0, t0)

        assert message.startswith("Failed to write dump.fail file: ")
        captured = capsys.readouterr()
        assert f"ERROR: {message}" in captured.out


def iso(seconds):
    """The time, seconds after T0, as written in the CSV files."""
    return (T0 + timedelta(seconds=seconds)).isoformat()


class TestWriteHistory:

    def test_rows_in_time_order(self, tmp_path):
        write_history(
            [
                record(2, "b", "value", 1.5),
                record(1, "c", "state_status", "idle"),
                record(1, "a", "config_simulate", "true"),
            ],
            tmp_path / "history.csv",
        )
        assert read_csv(tmp_path / "history.csv") == [
            ["time", "topic", "field", "value"],
            [(T0 + timedelta(seconds=1)).isoformat(), "a", "config_simulate", "true"],
            [(T0 + timedelta(seconds=1)).isoformat(), "c", "state_status", "idle"],
            [(T0 + timedelta(seconds=2)).isoformat(), "b", "value", "1.5"],
        ]

    def test_same_time_topic_and_field_with_numbers_and_strings(self, tmp_path):
        # Sorting doesn't compare the values, which could be of different types
        write_history(
            [record(1, "a", "x", 1.0), record(1, "a", "x", "text")],
            tmp_path / "history.csv",
        )
        assert len(read_csv(tmp_path / "history.csv")) == 3

    def test_no_records(self, tmp_path):
        write_history([], tmp_path / "history.csv")
        assert read_csv(tmp_path / "history.csv") == [
            ["time", "topic", "field", "value"]
        ]


class TestWriteData:

    def write(self, tmp_path, records):
        write_data(records, T0, tmp_path / "data.csv")
        return read_csv(tmp_path / "data.csv")

    def test_values_at_their_own_times(self, tmp_path):
        rows = self.write(
            tmp_path,
            [
                record(1.5, f"{FURNACE}/measurement", "value", 26.0),
                record(0.5, f"{FURNACE}/measurement", "value", 25.0),
                record(0.1, f"{FURNACE}/setpoint", "value", 30.0),
                record(0.8, "instruments/pressure/pressure/measurement", "value", 1.0),
            ],
        )
        # Nothing filled in, or resampled
        assert rows == [
            [
                "time",
                "elapsed_s",
                "furnace/temperature",
                "furnace/temperature_setpoint",
                "pressure/pressure",
            ],
            [iso(0.1), "0.1", "", "30.0", ""],
            [iso(0.5), "0.5", "25.0", "", ""],
            [iso(0.8), "0.8", "", "", "1.0"],
            [iso(1.5), "1.5", "26.0", "", ""],
        ]

    def test_values_at_the_same_time_share_a_row(self, tmp_path):
        rows = self.write(
            tmp_path,
            [
                record(1.2311, f"{FURNACE}/measurement", "value", 25.0),
                record(
                    1.2311, "instruments/pressure/pressure/measurement", "value", 1.0
                ),
                record(1.2312, f"{FURNACE}/setpoint", "value", 30.0),
            ],
        )
        # Not rounded
        assert rows[1:] == [
            [iso(1.2311), "1.2311", "25.0", "", "1.0"],
            [iso(1.2312), "1.2312", "", "30.0", ""],
        ]

    def test_values_of_the_same_column_keep_their_own_rows(self, tmp_path):
        rows = self.write(
            tmp_path,
            [
                record(1.23, f"{FURNACE}/measurement", "value", 25.0),
                record(1.23, f"{FURNACE}/measurement", "value", 26.0),
            ],
        )
        assert rows[1:] == [
            [iso(1.23), "1.23", "25.0"],
            [iso(1.23), "1.23", "26.0"],
        ]

    def test_only_variable_values(self, tmp_path):
        rows = self.write(
            tmp_path,
            [
                record(0.5, f"{FURNACE}/measurement", "value", 25.0),
                record(0.5, f"{FURNACE}/measurement", "other", 1.0),
                record(0.5, "instruments/furnace/heartbeat", "value", 1.0),
                record(0.5, "controller/command/run", "experiment_id", "D1"),
            ],
        )
        assert rows == [
            ["time", "elapsed_s", "furnace/temperature"],
            [iso(0.5), "0.5", "25.0"],
        ]

    def test_no_data(self, tmp_path):
        assert self.write(tmp_path, []) == [["time", "elapsed_s"]]


class TestRunningExperiment:

    @pytest.fixture(autouse=True)
    def tmp_data_path(self, tmp_path):
        with patch("src.controller_helper.data_path", new=str(tmp_path)):
            yield tmp_path

    @pytest.fixture
    def rec_mocks(self):
        with (
            patch("src.controller_helper.pub_err") as mock_publish_error,
            patch("src.controller_helper.dump_database_for_experiment") as mock_dump,
        ):
            yield {"pub_err": mock_publish_error, "dump": mock_dump}

    @pytest.fixture
    def state(self, mock_state):
        state = mock_state("idle")
        state.experiment_id = "D26-001"
        state.exp_file = "data/D26-001.json"
        state.experiment_start_time = datetime(2026, 1, 2, 3, 4, 5)
        return state

    def test_save_and_clear(self, state, tmp_data_path):
        save_running_experiment(state)

        assert running_experiment_path() == str(
            tmp_data_path / "running_experiment.json"
        )
        with open(running_experiment_path()) as f:
            assert json.load(f) == {
                "experiment_id": "D26-001",
                "exp_file": "data/D26-001.json",
                "start_time": "2026-01-02T03:04:05",
            }

        clear_running_experiment()

        assert not os.path.exists(running_experiment_path())

    def test_clear_only_the_given_experiment(self, state):
        save_running_experiment(state)

        # Another experiment started while this one was being dumped
        clear_running_experiment("D26-000")
        assert os.path.exists(running_experiment_path())

        clear_running_experiment("D26-001")
        assert not os.path.exists(running_experiment_path())

    def test_clear_given_experiment_without_record(self):
        clear_running_experiment("D26-001")  # Doesn't raise

        assert not os.path.exists(running_experiment_path())

    def test_clear_without_record(self):
        clear_running_experiment()  # Doesn't raise

        assert not os.path.exists(running_experiment_path())

    def test_recover_without_record(self, rec_mocks):
        recover_lost_experiment()

        rec_mocks["pub_err"].lost_experiment.assert_not_called()
        rec_mocks["dump"].assert_not_called()

    def test_recover_lost_experiment(self, state, rec_mocks):
        save_running_experiment(state)

        recover_lost_experiment()

        rec_mocks["pub_err"].lost_experiment.assert_called_once_with("D26-001")
        # Dumps the experiment's data, as stopping it would have
        rec_mocks["dump"].assert_called_once()
        lost = rec_mocks["dump"].call_args.args[0]
        assert lost.experiment_id == "D26-001"
        assert lost.exp_file == "data/D26-001.json"
        assert lost.experiment_start_time == datetime(2026, 1, 2, 3, 4, 5)
        # The dump clears the record once done
        assert os.path.exists(running_experiment_path())

    def test_recover_unreadable_record(self, rec_mocks):
        with open(running_experiment_path(), "w") as f:
            f.write("not json")

        recover_lost_experiment()

        rec_mocks["pub_err"].lost_experiment.assert_called_once()
        assert "unknown" in rec_mocks["pub_err"].lost_experiment.call_args.args[0]
        rec_mocks["dump"].assert_not_called()
        assert not os.path.exists(running_experiment_path())
