import json
import pytest
from unittest.mock import patch


from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
    mock_c_stopping,
)

from src.on_controller_message import c_running


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("running", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_running,
        obj=state,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture
def mock_c_end(autouse=True):
    with patch("src.on_controller_message.c_end") as mock_c_end:
        mock_c_end.return_value = None
        mock_c_end.__name__ = "mock_c_end"
        yield mock_c_end


# ========================================


def test_incompatible_request(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running

    msg = MockMessage(
        topic="controller/something_else", payload=json.dumps({"uid": "123"})
    )
    c_running(controller_client, msg, state)

    assert state.status == "ready"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Controller is ready. Cannot act on controller/something_else"
        in messages[0].payload
    )


def test_accepts_stop_signal(message_bus, state, controller_client, mock_c_stopping):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running

    msg = MockMessage(topic="controller/stop", payload="not important")
    c_running(controller_client, msg, state)

    assert mock_c_stopping.called


def test_sends_end_signal_when_setpoints_empty(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert controller_client.callback == c_running
    state.setpoints = []

    msg = MockMessage(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    c_running(controller_client, msg, state)

    assert controller_client.callback.__name__ == "c_stopping"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/end"
    assert messages[0].payload == json.dumps({"uid": "123"})


def test_updates_state_on_first_setpoint_only(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    assert state.setpoints != []

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    # Should update state on first setpoint
    assert state.status == "running"
    assert state.current_setpoint is not None

    # Should not update state on second setpoint
    state.status = "idle"
    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    assert state.status == "idle"


def test_saves_past_setpoints(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    assert state.setpoints != []

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    # Should not have saved "None" as past setpoint
    assert state.past_setpoints == []
    assert state.current_setpoint is not None
    new_sp = state.current_setpoint

    # Should save current setpoint on next run
    c_running(controller_client, msg, state)

    assert state.past_setpoints == [new_sp]


def test_sets_current_setpoint(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    assert state.current_setpoint == all_setpoints[0]


def test_drops_current_setpoint_from_list(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    assert state.setpoints == all_setpoints[1:]


def test_sends_setpoint(message_bus, state, controller_client, mock_experiment_dict):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    first_sp = state.setpoints[0]
    sensors = [k for k in first_sp if k != "duration"]

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1 + len(sensors)

    for i, sensor in enumerate(sensors):
        assert messages[i].topic == f"sensor/{sensor}/setpoint"
        assert json.loads(messages[i].payload) == {
            "duration": first_sp["duration"],
            sensor: first_sp[sensor],
        }


def test_starts_setpoint_timer(
    message_bus, state, controller_client, mock_experiment_dict
):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    first_sp = state.setpoints[0]
    sensors = [k for k in first_sp if k != "duration"]

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1 + len(sensors)
    assert messages[-1].topic == "timer/start/setpoint"
    assert json.loads(messages[-1].payload) == {
        "uid": "123",
        "duration": first_sp["duration"],
    }


def test_saves_and_clears_last_setpoint(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert controller_client.callback == c_running
    state.status == "running"
    last_setpoint = state.setpoints[-1].copy()
    state.current_setpoint = last_setpoint.copy()
    state.setpoints = []

    msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
    c_running(controller_client, msg, state)

    assert state.current_setpoint is None
    assert state.past_setpoints == [last_setpoint]
