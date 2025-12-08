import os
from datetime import datetime
import pytest
from unittest.mock import patch

from tests.conftest import (
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.controller_helper import assign_serial_id


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
