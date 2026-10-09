import pytest
from unittest.mock import mock_open, patch

from src.controller_state import cstate
from datetime import datetime


class TestCState:
    def test_cstate_initialization(self):
        state = cstate()

        assert state._experiment_start_time == None
        assert state._experiment_id == None
        assert state._exp_file == None
        assert state._status == "idle"
        assert state._exp_config == None
        assert state._setpoints == []
        assert state._current_setpoint == None
        assert state._past_setpoints == []
        assert state._instrument_states == {}
        assert state._expected_heartbeats == {}
        assert state._instruments_ready == False
        assert state._config == None

    def test_cannot_add_new_attribute(self):
        state = cstate()
        try:
            state.new_attribute = 123
        except AttributeError as e:
            assert "'cstate' object has no attribute 'new_attribute'" in e.args[0]
        else:
            assert False, "Should not let you add new attribute"

    def test_cstate_heartbeat(self):
        state = cstate()
        assert state.heartbeat() == {
            "config": {"experiment_id": None},
            "setpoints": {},
            "state": "idle",
        }

    def test_str(self):
        state = cstate()
        state.experiment_id = "123"
        assert (
            str(state)
            == '{"config": {"experiment_id": "123"}, "setpoints": {}, "state": "idle"}'
        )

    def test_reset(self, mock_comodo_config):
        state = cstate()
        state._experiment_start_time = datetime.now()
        state._experiment_id = "123"
        state._exp_file = "path/to/file.json"
        state._status = "running"
        state._exp_config = {"uid": 123, "config": {"resolution": 1}}
        state._setpoints = [{"time": 0, "pressure": 0, "temperature": 0}]
        state._current_setpoint = {"time": 0, "pressure": 0, "temperature": 0}
        state._past_setpoints = [{"time": 0, "pressure": 0, "temperature": 0}]
        state._instrument_states = {"T": "something"}
        state._expected_heartbeats = {"T": {"state": "running"}}
        state._instruments_ready = True
        state._config = mock_comodo_config

        with patch.object(cstate, "reset_expected_heartbeats") as mock_reset_hb:
            state.reset()

        assert state._experiment_start_time == None
        assert state._experiment_id == None
        assert state._exp_file == None
        assert state._status == "idle"
        assert state._exp_config == None
        assert state._setpoints == []
        assert state._current_setpoint == None
        assert state._past_setpoints == []
        assert state._instrument_states == {}
        mock_reset_hb.assert_called_once_with()
        assert state._instruments_ready == False
        assert state._config == mock_comodo_config

    def test_can_set_experiment_start_time(self):
        state = cstate()
        t = datetime.now()
        state.experiment_start_time = t
        assert state.experiment_start_time == t

    def test_cannot_set_wrong_type_experiment_start_time(self):
        state = cstate()
        try:
            state.experiment_start_time = "123"
        except TypeError as e:
            assert (
                "Experiment start time must be a datetime or None, cannot accept <class 'str'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_experiment_id(self):
        state = cstate()
        state.experiment_id = "123"
        assert state.experiment_id == "123"

    def test_cannot_set_wrong_type_experiment_id(self):
        state = cstate()
        try:
            state.experiment_id = 123
        except TypeError as e:
            assert (
                "Experiment UID must be a string or None, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_exp_file(self):
        state = cstate()
        state.exp_file = "path/to/file.json"
        assert state.exp_file == "path/to/file.json"

    def test_cannot_set_wrong_type_exp_file(self):
        state = cstate()
        try:
            state.exp_file = 123
        except TypeError as e:
            assert (
                "Experiment file path must be a string or None, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_set_valid_status(self):
        state = cstate()
        state.status = "running"
        assert state.status == "running"

    def test_status_invalid(self):
        state = cstate()
        try:
            state.status = "invalid_status"
        except ValueError as e:
            assert "Invalid status:" in e.args[0]
        else:
            assert False, "Should not let you set invalid status"

    def test_can_set_exp_config(self):
        state = cstate()
        state.exp_config = {
            "uid": 123,
            "config": {"instruments": ["T", "P", "D1", "D2"]},
        }
        assert state.exp_config == {
            "uid": 123,
            "config": {"instruments": ["T", "P", "D1", "D2"]},
        }

    def test_cannot_set_wrong_type_exp_config(self):
        state = cstate()
        try:
            state.exp_config = 123
        except TypeError as e:
            assert (
                "Experiment configuration must be a dictionary or None, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_setpoints(self):
        state = cstate()
        state.setpoints = [
            {
                "time": 0,
                "pressure": 0,
                "temperature": 0,
            },
            {
                "time": 1,
                "pressure": 100,
                "temperature": 100,
            },
        ]
        assert state.setpoints == [
            {
                "time": 0,
                "pressure": 0,
                "temperature": 0,
            },
            {
                "time": 1,
                "pressure": 100,
                "temperature": 100,
            },
        ]

    def test_cannot_set_wrong_type_setpoints(self):
        state = cstate()
        try:
            state.setpoints = 123
        except TypeError as e:
            assert (
                "Setpoints must be a list of dictionaries, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_current_setpoint(self):
        state = cstate()
        state.current_setpoint = {
            "time": 1,
            "pressure": 2,
            "temperature": 3,
        }
        assert state.current_setpoint == {
            "time": 1,
            "pressure": 2,
            "temperature": 3,
        }

    def test_cannot_set_wrong_type_current_setpoint(self):
        state = cstate()
        try:
            state.current_setpoint = 123
        except TypeError as e:
            assert (
                "Current setpoint must be a dictionary or None, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_past_setpoints(self):
        state = cstate()
        state.past_setpoints.append({"time": 1, "pressure": 2, "temperature": 3})
        assert state.past_setpoints == [{"time": 1, "pressure": 2, "temperature": 3}]

    def test_cannot_set_wrong_type_past_setpoints(self):
        state = cstate()
        try:
            state.past_setpoints = 123
        except TypeError as e:
            assert (
                "Past setpoints must be a list of dictionaries, cannot accept <class 'int'>"
                in e.args[0]
            )
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_instruments(self):
        state = cstate()
        for instrument in ["T", "P"]:
            state.instrument_states[instrument] = {
                "last_contact": 0,
                "config": {},
                "status": "awaiting_config",
                "setpoint": None,
            }
        assert state.instrument_states == {
            "T": {
                "last_contact": 0,
                "config": {},
                "status": "awaiting_config",
                "setpoint": None,
            },
            "P": {
                "last_contact": 0,
                "config": {},
                "status": "awaiting_config",
                "setpoint": None,
            },
        }

    def test_cannot_set_wrong_type_instruments(self):
        state = cstate()
        try:
            state.instrument_states = 123
        except TypeError as e:
            assert "Instrument states must be a dictionary" in e.args[0]
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_expected_heartbeats(self):
        state = cstate()
        state.expected_heartbeats = {
            "T": {"state": "running", "config": {"experiment": {}}},
            "P": {"state": "running", "config": {"experiment": {}}},
        }
        assert state.expected_heartbeats == {
            "T": {"state": "running", "config": {"experiment": {}}},
            "P": {"state": "running", "config": {"experiment": {}}},
        }

    def test_cannot_set_wrong_type_expected_heartbeats(self):
        state = cstate()
        try:
            state.expected_heartbeats = 123
        except TypeError as e:
            assert "Expected heartbeats must be a dictionary" in e.args[0]
        else:
            assert False, "Should not let you set wrong type"

    def test_reset_expected_heartbeats(self, mock_comodo_config):
        state = cstate()
        state.config = mock_comodo_config
        state._expected_heartbeats["furnace"] = {"experiment": {"some": "config"}}
        state._expected_heartbeats["pressure"] = {"experiment": {"some": "config"}}
        state._expected_heartbeats["mass_flow"] = {"experiment": {"some": "config"}}
        state.reset_expected_heartbeats()
        assert state.expected_heartbeats == {
            "furnace": mock_comodo_config.get_expected_heartbeat("furnace"),
            "pressure": mock_comodo_config.get_expected_heartbeat("pressure"),
            "mass_flow": mock_comodo_config.get_expected_heartbeat("mass_flow"),
        }
        assert state.expected_heartbeats["furnace"]["experiment"] == {}
        assert state.expected_heartbeats["pressure"]["experiment"] == {}
        assert state.expected_heartbeats["mass_flow"]["experiment"] == {}

    def test_set_hb_experiment_config(self, capsys):
        state = cstate()
        state._expected_heartbeats["furnace"] = {"experiment": {}}

        state.set_hb_experiment_config("furnace", {"some": "config"})

        assert state.expected_heartbeats["furnace"]["experiment"] == {"some": "config"}
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_set_hb_experiment_config_replacing_warn(self, capsys):
        state = cstate()
        state._expected_heartbeats["furnace"] = {"experiment": {"old": "config"}}

        state.set_hb_experiment_config("furnace", {"new": "config"})

        captured = capsys.readouterr()
        assert (
            "Warning: Replacing existing experiment config for instrument furnace"
            in captured.out
        )
        assert state.expected_heartbeats["furnace"]["experiment"] == {"new": "config"}

    def test_get_expected_heartbeat(self):
        state = cstate()
        exp_furnace_hb = {
            "state": "running",
            "config": {"experiment": {"some": "config"}},
        }
        state._expected_heartbeats["furnace"] = exp_furnace_hb

        expected_hb = state.get_expected_heartbeat("furnace")

        assert expected_hb == exp_furnace_hb

    def test_can_set_instruments_ready(self):
        state = cstate()
        state.instruments_ready = True
        assert state.instruments_ready == True

    def test_cannot_set_wrong_type_instruments_ready(self):
        state = cstate()
        try:
            state.instruments_ready = 123
        except TypeError as e:
            assert "Instruments ready flag must be a boolean" in e.args[0]
        else:
            assert False, "Should not let you set wrong type"

    def test_can_set_config(self, mock_comodo_config):
        state = cstate()
        state.config = mock_comodo_config
        assert state.config == mock_comodo_config

    def test_cannot_set_wrong_type_config(self):
        state = cstate()
        try:
            state.config = 123
        except TypeError as e:
            assert "Config must be an instance of ComodoConfig or None" in e.args[0]
        else:
            assert False, "Should not let you set wrong type"
