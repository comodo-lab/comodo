from controller_state import *
import pytest
from unittest.mock import mock_open, patch


@pytest.fixture
def state():
    return cstate()


def test_cstate_initialization():
    state = cstate()
    assert len(state.__dict__) == 5
    assert state.experiment_uid == None
    assert state.status == "idle"
    assert state.adjusting == AdjustingDict()
    assert state.schema_path == "experiment_schema.json"
    assert state.exp_config == None


def test_cstate_heartbeat(state):
    assert state.heartbeat() == {
        "experiment": None,
        "status": "idle",
        "adjusting": AdjustingDict(),
    }


def test_can_set_experiment_uid(state):
    state.experiment_uid = 123
    assert state.experiment_uid == 123


def test_str(state):
    state.experiment_uid = 123
    assert (
        str(state)
        == '{"experiment": 123, "status": "idle", "adjusting": {"T": 0, "P": 0, "D1": 0, "D2": 0}}'
    )


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
