import pytest
from unittest.mock import mock_open, patch

from src.controller_state import cstate
from datetime import datetime


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
    assert state.instrument_states == {}
    assert state.instruments_ready == False


def test_cannot_add_new_attribute(state):
    try:
        state.new_attribute = 123
    except AttributeError as e:
        assert "'cstate' object has no attribute 'new_attribute'" in e.args[0]
    else:
        assert False, "Should not let you add new attribute"


def test_cstate_heartbeat(state):
    assert state.heartbeat() == {
        "config": {"experiment_id": None},
        "setpoints": {},
        "state": "idle",
    }


def test_str(state):
    state.experiment_uid = "123"
    assert (
        str(state)
        == '{"config": {"experiment_id": "123"}, "setpoints": {}, "state": "idle"}'
    )


def test_reset(state):
    state.experiment_start_time = datetime.now()
    state.experiment_uid = "123"
    state.exp_file = "path/to/file.json"
    state.status = "running"
    state.exp_config = {"uid": 123, "config": {"resolution": 1}}
    state.setpoints = [{"time": 0, "pressure": 0, "temperature": 0}]
    state.current_setpoint = {"time": 0, "pressure": 0, "temperature": 0}
    state.past_setpoints = [{"time": 0, "pressure": 0, "temperature": 0}]
    state.instrument_states = {}

    state.reset()

    clean_state = cstate()
    for attr in state.__slots__:
        assert getattr(state, attr) == getattr(clean_state, attr)


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
    state.exp_config = {"uid": 123, "config": {"instruments": ["T", "P", "D1", "D2"]}}
    assert state.exp_config == {
        "uid": 123,
        "config": {"instruments": ["T", "P", "D1", "D2"]},
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


def test_can_set_instruments(state):
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


def test_cannot_set_wrong_type_instruments(state):
    try:
        state.instrument_states = 123
    except TypeError as e:
        assert (
            "Instrument states must be a dictionary, cannot accept <class 'int'>"
            in e.args[0]
        )
    else:
        assert False, "Should not let you set wrong type"
