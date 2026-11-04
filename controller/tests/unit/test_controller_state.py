import pytest
from unittest.mock import mock_open, patch, PropertyMock

import copy

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
        assert state._no_contact_tolerance == None
        assert state._adjusting_tolerance == None

    def test_cannot_add_new_attribute(self):
        state = cstate()
        try:
            state.new_attribute = 123
        except AttributeError as e:
            assert "'cstate' object has no attribute 'new_attribute'" in e.args[0]
        else:
            assert False, "Should not let you add new attribute"

    def test_cstate_heartbeat(self):
        with (
            patch.object(cstate, "evaluate_variables") as mock_eval,
            patch.object(cstate, "update_bad_instrument_counts") as mock_update_bad,
        ):
            mock_eval.return_value = {
                "setpoints": {"var1": 10, "var2": 20},
                "status": {"var1": "at_setpoint", "var2": "adjusting"},
            }
            state = cstate()
            hb = state.heartbeat()

        mock_eval.assert_called_once_with()
        mock_update_bad.assert_called_once_with(mock_eval.return_value)
        assert hb == {
            "config": {"experiment_id": None},
            "setpoints": {"var1": 10, "var2": 20},
            "state": {
                "status": "idle",
                "variables": {
                    "var1": "at_setpoint",
                    "var2": "adjusting",
                },
            },
        }

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
        state._spc_states = {"S": "something"}
        state._expected_heartbeats = {"T": {"state": "running"}}
        state._instruments_ready = True
        state._config = mock_comodo_config
        state._no_contact_tolerance = 3.0
        state._adjusting_tolerance = 14.0

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
        assert state._spc_states == {}
        mock_reset_hb.assert_called_once_with()
        assert state._instruments_ready == False
        assert state._config == mock_comodo_config
        assert state._no_contact_tolerance == 3.0
        assert state._adjusting_tolerance == None

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
        assert state._adjusting_tolerance == None  # state.config is None

    def test_setting_exp_config_sets_adjusting_tolerance(self, mock_comodo_config):
        state = cstate()
        state.config = mock_comodo_config
        state.config.globals["missed_setpoint_tolerance"] = 7
        state.config.globals["heartbeat_interval"] = 3
        state.exp_config = {
            "uid": 123,
            "config": {"instruments": ["T", "P", "D1", "D2"], "resolution": 2.0},
        }
        assert state._adjusting_tolerance == 7 * 2.0 / 3

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

    def test_set_hb_experiment_config_appending(self, capsys):
        state = cstate()
        state._expected_heartbeats["furnace"] = {"experiment": {"old": "config"}}

        state.set_hb_experiment_config("furnace", {"new": "config"})

        assert state.expected_heartbeats["furnace"]["experiment"] == {
            "old": "config",
            "new": "config",
        }
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_set_hb_experiment_config_replacing_warn(self, capsys):
        state = cstate()
        state._expected_heartbeats["furnace"] = {"experiment": {"some": "config"}}

        state.set_hb_experiment_config("furnace", {"some": "other_config"})

        captured = capsys.readouterr()
        assert "WARNING: Replacing existing experiment configuration" in captured.out
        assert "for instrument furnace some: config -> other_config" in captured.out
        assert state.expected_heartbeats["furnace"]["experiment"] == {
            "some": "other_config"
        }

    def test_get_expected_heartbeat(self):
        state = cstate()
        exp_furnace_hb = {
            "state": "running",
            "config": {"experiment": {"some": "config"}},
        }
        state._expected_heartbeats["furnace"] = exp_furnace_hb

        expected_hb = state.get_expected_heartbeat("furnace")

        assert expected_hb == exp_furnace_hb

    def test_can_set_spc_states(self):
        state = cstate()
        state.spc_states = {"S": {"config": None}}
        assert state.spc_states == {"S": {"config": None}}

    def test_cannot_set_wrong_type_spc_states(self):
        state = cstate()
        with pytest.raises(TypeError) as e:
            state.spc_states = "not a dict"
        assert "SPC states must be a dictionary" in str(e.value)

    def test_get_expected_spc_config(self):
        state = cstate()
        assert state.get_expected_spc_config("S") is None
        state._exp_config = {"config": {"spcs": {"S": {"pid": {"k_p": 1.0}}}}}

        assert state.get_expected_spc_config("S") == {"pid": {"k_p": 1.0}}
        assert state.get_expected_spc_config("other") is None

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

    def test_setting_config_sets_no_contact_tolerance(self, mock_comodo_config):
        state = cstate()
        mock_comodo_config.globals["max_missed_heartbeats"] = 3
        mock_comodo_config.globals["heartbeat_interval"] = 7
        state.config = mock_comodo_config

        assert state._no_contact_tolerance == 7 * 3

    def test_cannot_set_wrong_type_config(self):
        state = cstate()
        try:
            state.config = 123
        except TypeError as e:
            assert "Config must be an instance of ComodoConfig or None" in e.args[0]
        else:
            assert False, "Should not let you set wrong type"

    def test_evalueate_variables_returns_empty_if_no_current_setpoints(self):
        state = cstate()
        state._current_setpoint = None
        with patch("src.controller_state.t") as mock_time:
            result = state.evaluate_variables()

        mock_time.assert_not_called()
        assert result == {"setpoints": {}, "status": {}}

    def test_evalueate_variables_returns_expected_values(self):
        t_now = 10
        state = cstate()
        state._no_contact_tolerance = 5
        state._exp_config = {
            "config": {
                "instruments": {
                    "inst_3": {"var_4": {"tolerance": 1}, "var_5": {"tolerance": 1}},
                }
            }
        }
        state._current_setpoint = {
            "inst_1/var_1": 1,  # no_heartbeat
            "inst_2/var_2": 2,  # no_measurement
            "inst_2/var_3": 3,  # no_measurement
            "inst_3/var_4": 4,  # at_setpoint
            "inst_3/var_5": 5,  # adjusting
        }
        instrument_states = {
            "inst_1": {
                "last_contact": 4,  # too old, no heartbeat
                "setpoints": {"var_1": 1},
                "state": {"measurements": {"var_1": 1}},
            },
            "inst_2": {
                "last_contact": 7,
                "setpoints": {
                    "var_2": 2,
                    "var_3": 3,
                },
                "state": {"measurements": {"var_2": None}},  # one None, one not passed
            },
            "inst_3": {
                "last_contact": 9,
                "setpoints": {"var_4": 4, "var_5": 5, "var_6": 6},
                "state": {
                    "measurements": {
                        "var_4": 4,  # at_setpoint
                        "var_5": 7,  # not at setpoint, adjusting"
                        "var_6": 6,  # not in current_setpoint, so ignored
                    }
                },
            },
        }
        state._instrument_states = copy.deepcopy(instrument_states)
        with patch("src.controller_state.t") as mock_time:
            mock_time.time.return_value = t_now
            result = state.evaluate_variables()

        mock_time.time.assert_called_once_with()
        assert result == {
            "setpoints": {
                "inst_1/var_1": 1,
                "inst_2/var_2": 2,
                "inst_2/var_3": 3,
                "inst_3/var_4": 4,
                "inst_3/var_5": 5,
            },
            "status": {
                "inst_1/var_1": "no_heartbeat",
                "inst_2/var_2": "no_measurement",
                "inst_2/var_3": "no_measurement",
                "inst_3/var_4": "at_setpoint",
                "inst_3/var_5": "adjusting",
            },
        }
        assert state._instrument_states == instrument_states

    def test_update_bad_instrument_counts_returns_if_empty(self):
        state = cstate()
        with patch.object(cstate, "config", new_callable=PropertyMock) as mock_config:
            state.update_bad_instrument_counts({"setpoints": {}, "status": {}})
        mock_config.assert_not_called()

    def test_update_bad_instrument_counts_non_evaluated_are_ok(
        self, mock_comodo_config
    ):
        state = cstate()
        state._config = mock_comodo_config
        state._adjusting_tolerance = 10
        state.config.instruments = {"inst_1": {"variables": {"var_1": {}}}}
        state._instrument_states = {"inst_1": {}}

        var_eval = {"status": {"inst_2/var_2": "no_heartbeat"}}
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 0,
            "adjusting": 0,
        }

    def test_update_bad_instrument_counts_tracks_bad_and_adjusting_separately(
        self, mock_comodo_config
    ):
        state = cstate()
        state._config = mock_comodo_config
        state._adjusting_tolerance = 10
        state.config.instruments = {"inst_1": {"variables": {"var_1": {}}}}
        state._instrument_states = {"inst_1": {}}

        var_eval = {"status": {"inst_1/var_1": "no_heartbeat"}}
        state.update_bad_instrument_counts(var_eval)
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 2,
            "adjusting": 0,
        }

        var_eval = {"status": {"inst_1/var_1": "adjusting"}}
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 0,
            "adjusting": 1,
        }

    def test_update_bad_instrument_counts_does_not_double_count(
        self, mock_comodo_config
    ):
        state = cstate()
        state._config = mock_comodo_config
        state._adjusting_tolerance = 10
        state.config.instruments = {
            "inst_1": {"variables": {"var_1": {}, "var_2": {}, "var_3": {}}}
        }
        state._instrument_states = {"inst_1": {}}

        var_eval = {
            "status": {
                "inst_1/var_1": "no_heartbeat",
                "inst_1/var_2": "adjusting",
                "inst_1/var_3": "no_measurement",
            }
        }
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 1,  # this would be 2 if double counting
            "adjusting": 1,
        }

    def test_update_bad_instrument_counts_checks_by_instrument(
        self, mock_comodo_config
    ):
        state = cstate()
        state._config = mock_comodo_config
        state._adjusting_tolerance = 10
        state.config.instruments = {
            "inst_1": {"variables": {"var_1": {}, "var_2": {}}},
            "inst_2": {"variables": {"var_1": {}, "var_2": {}}},
        }
        state._instrument_states = {"inst_1": {}, "inst_2": {}}

        var_eval = {
            "status": {
                "inst_1/var_1": "no_measurement",
                "inst_1/var_2": "adjusting",
                "inst_2/var_1": "at_setpoint",
                "inst_2/var_2": "at_setpoint",
            }
        }
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 1,
            "adjusting": 1,
        }
        assert state._instrument_states["inst_2"]["bad_count"] == {
            "bad_state": 0,
            "adjusting": 0,
        }

    def test_update_bad_instrument_counts_resets_counts_if_all_good(
        self, mock_comodo_config
    ):
        state = cstate()
        state._config = mock_comodo_config
        state._adjusting_tolerance = 10
        state.config.instruments = {
            "inst_1": {"variables": {"var_1": {}, "var_2": {}}},
        }
        state._instrument_states = {"inst_1": {}}

        var_eval = {
            "status": {"inst_1/var_1": "no_measurement", "inst_1/var_2": "adjusting"}
        }
        state.update_bad_instrument_counts(var_eval)
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 2,
            "adjusting": 2,
        }

        var_eval = {
            "status": {"inst_1/var_1": "at_setpoint", "inst_1/var_2": "adjusting"}
        }
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 0,
            "adjusting": 3,
        }

        var_eval = {
            "status": {
                "inst_1/var_1": "no_measurement",
                "inst_1/var_2": "at_setpoint",
            }
        }
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 1,
            "adjusting": 3,  # not reset because there is a bad state, but not increased
        }

        var_eval = {
            "status": {"inst_1/var_1": "at_setpoint", "inst_1/var_2": "at_setpoint"}
        }
        state.update_bad_instrument_counts(var_eval)

        assert state._instrument_states["inst_1"]["bad_count"] == {
            "bad_state": 0,
            "adjusting": 0,  # not reset because there is a bad state
        }

    def test_update_bad_instrument_counts_sets_to_error_if_bad(
        self, mock_comodo_config
    ):
        state = cstate()
        state.status = "running"
        state._config = mock_comodo_config
        state.config.globals["bad_state_tolerance"] = 3
        state._adjusting_tolerance = 10
        state.config.instruments = {
            "inst_1": {"variables": {"var_1": {}}},
        }
        state._instrument_states = {"inst_1": {}}
        var_eval = {"status": {"inst_1/var_1": "no_measurement"}}
        with patch("src.controller_state.pub_err.print_and_publish") as mock_pub_err:
            state.update_bad_instrument_counts(var_eval)
            state.update_bad_instrument_counts(var_eval)
            state.update_bad_instrument_counts(var_eval)

            assert state._instrument_states["inst_1"]["bad_count"] == {
                "bad_state": 3,
                "adjusting": 0,
            }
            mock_pub_err.assert_not_called()
            assert state.status == "running"

            state.update_bad_instrument_counts(var_eval)

            mock_pub_err.assert_called_once_with(
                topic="error/controller",
                code="experiment",
                message="ERROR: Instrument inst_1 in bad state for too long.",
            )
            assert state.status == "error"

    def test_update_bad_instrument_counts_sets_to_error_if_adjusting(
        self, mock_comodo_config
    ):
        state = cstate()
        state.status = "running"
        state._config = mock_comodo_config
        state._adjusting_tolerance = 2
        state.config.instruments = {
            "inst_1": {"variables": {"var_1": {}}},
        }
        state._instrument_states = {"inst_1": {}}
        var_eval = {"status": {"inst_1/var_1": "adjusting"}}
        with patch("src.controller_state.pub_err.print_and_publish") as mock_pub_err:
            state.update_bad_instrument_counts(var_eval)
            state.update_bad_instrument_counts(var_eval)

            assert state._instrument_states["inst_1"]["bad_count"] == {
                "bad_state": 0,
                "adjusting": 2,
            }
            mock_pub_err.assert_not_called()
            assert state.status == "running"

            state.update_bad_instrument_counts(var_eval)

            mock_pub_err.assert_called_once_with(
                topic="error/controller",
                code="experiment",
                message="ERROR: Instrument inst_1 not keeping up with setpoints.",
            )
            assert state.status == "error"
