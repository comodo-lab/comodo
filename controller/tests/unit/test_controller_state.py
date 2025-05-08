from tests.tests_helper import *

from controller_state import *
import pytest
from unittest.mock import mock_open, patch


@pytest.fixture
def state():
    return cstate()


def test_cstate_initialization():
    state = cstate()
    assert state.experiment_start_time == None
    assert state.experiment_uid == None
    assert state.exp_file == None
    assert state.status == "idle"
    assert state.exp_config == None
    assert state.setpoints == []
    assert state.current_setpoint == None
    assert state.past_setpoints == []
    assert state.sensors == {"configured": False}
    assert state.adjusting == AdjustingDict()
    assert state.schema_path == "schemas/schema_experiment.json"
    assert state.schema_sensor_heartbeat_path == "schemas/schema_sensor_heartbeat.json"


def test_cannot_add_new_attribute(state):
    try:
        state.new_attribute = 123
    except AttributeError as e:
        assert "'cstate' object has no attribute 'new_attribute'" in e.args[0]
    else:
        assert False, "Should not let you add new attribute"


def test_cstate_heartbeat(state):
    assert state.heartbeat() == {
        "experiment": None,
        "status": "idle",
        "adjusting": AdjustingDict(),
    }


def test_str(state):
    state.experiment_uid = "123"
    assert (
        str(state)
        == '{"experiment": "123", "status": "idle", "adjusting": {"T": 0, "P": 0, "D1": 0, "D2": 0}}'
    )


def test_can_set_experiment_start_time(state):
    t = datetime.now()
    state.experiment_start_time = t
    assert state.experiment_start_time == t


def test_cannot_set_wrong_type_experiment_start_time(state):
    try:
        state.experiment_start_time = "123"
    except TypeError as e:
        assert (
            "Experiment start time must be a datetime or None, cannot accept <class 'str'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_experiment_uid(state):
    state.experiment_uid = "123"
    assert state.experiment_uid == "123"


def test_cannot_set_wrong_type_experiment_uid(state):
    try:
        state.experiment_uid = 123
    except TypeError as e:
        assert (
            "Experiment UID must be a string or None, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_exp_file(state):
    state.exp_file = "path/to/file.json"
    assert state.exp_file == "path/to/file.json"


def test_cannot_set_wrong_type_exp_file(state):
    try:
        state.exp_file = 123
    except TypeError as e:
        assert (
            "Experiment file path must be a string or None, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_set_valid_status(state):
    state.status = "running"
    assert state.status == "running"


def test_status_invalid(state):
    try:
        state.status = "invalid_status"
    except ValueError as e:
        assert "Invalid status:" in e.args[0]
    else:
        assert False, "Should not let you set invalid status"


def test_can_set_exp_config(state):
    state.exp_config = {"uid": 123, "config": {"sensors": ["T", "P", "D1", "D2"]}}
    assert state.exp_config == {
        "uid": 123,
        "config": {"sensors": ["T", "P", "D1", "D2"]},
    }


def test_cannot_set_wrong_type_exp_config(state):
    try:
        state.exp_config = 123
    except TypeError as e:
        assert (
            "Experiment configuration must be a dictionary or None, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_setpoints(state):
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


def test_cannot_set_wrong_type_setpoints(state):
    try:
        state.setpoints = 123
    except TypeError as e:
        assert (
            "Setpoints must be a list of dictionaries, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_current_setpoint(state):
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


def test_cannot_set_wrong_type_current_setpoint(state):
    try:
        state.current_setpoint = 123
    except TypeError as e:
        assert (
            "Current setpoint must be a dictionary or None, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_past_setpoints(state):
    state.past_setpoints.append({"time": 1, "pressure": 2, "temperature": 3})
    assert state.past_setpoints == [{"time": 1, "pressure": 2, "temperature": 3}]


def test_cannot_set_wrong_type_past_setpoints(state):
    try:
        state.past_setpoints = 123
    except TypeError as e:
        assert (
            "Past setpoints must be a list of dictionaries, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"


def test_can_set_sensors(state):
    for sensor in ["T", "P"]:
        state.sensors[sensor] = {
            "last_contact": 0,
            "config": {},
            "status": "awaiting_config",
            "setpoint": None,
        }
    assert state.sensors == {
        "configured": False,
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


def test_cannot_set_wrong_type_sensors(state):
    try:
        state.sensors = 123
    except TypeError as e:
        assert "Sensors must be a dictionary, cannot accept <class 'int'>" in e.args[0]
    else:
        assert False, "Should not let you set wrong type"


def test_set_valid_adjusting_dict(state):
    state.adjusting = {"T": 1, "P": 0, "D1": 0, "D2": 1}
    assert state.adjusting == {"T": 1, "P": 0, "D1": 0, "D2": 1}


def test_cstate_set_invalid_adjusting_dict(state):
    try:
        state.adjusting = {"T": 1, "P": 0, "D1": 0, "D2": 1, "X": 1}
    except ValueError as e:
        assert "Invalid adjusting key: X" in e.args[0]
    else:
        assert False, "Should not let you set invalid key"
    try:
        state.adjusting = {"T": 1, "P": 0, "D1": 0}
    except ValueError as e:
        assert "Incomplete adjusting keys." in e.args[0]
    else:
        assert False, "Should not let you set incomplete dict"


def test_AdjustingDict_initialization():
    adj = AdjustingDict()
    assert adj == {"T": 0, "P": 0, "D1": 0, "D2": 0}


def test_AdjustingDict_setitem():
    adj = AdjustingDict()
    adj["T"] = 1
    assert adj == {"T": 1, "P": 0, "D1": 0, "D2": 0}


def test_AdjustingDict_setitem_invalid_key():
    adj = AdjustingDict()
    try:
        adj["X"] = 1
    except ValueError as e:
        assert "Invalid adjusting key: X" in e.args[0]
    else:
        assert False, "Should not let you set invalid key"


def test_AdjustingDict_setitem_invalid_value():
    adj = AdjustingDict()
    try:
        adj["T"] = 2
    except ValueError as e:
        assert "Invalid value for T: 2" in e.args[0]
    else:
        assert False, "Should not let you set invalid value"


def test_AdjustingDict_delitem():
    adj = AdjustingDict()
    try:
        del adj["T"]
    except RuntimeError as e:
        assert "Cannot delete items" in e.args[0]
    else:
        assert False, "Should not let you delete items"
    assert adj == {"T": 0, "P": 0, "D1": 0, "D2": 0}
