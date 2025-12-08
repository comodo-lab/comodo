import json
import pytest
import time as t
from unittest.mock import call, patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.on_controller_message import c_starting


# =============== Fixtures ===============


state = mock_state("starting")


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_starting,
        obj=state,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture(autouse=True)
def mock_split_setpoints(mock_setpoints):
    with patch("src.on_controller_message.split_setpoints") as mock_split_setpoints:
        mock_split_setpoints.return_value = mock_setpoints
        yield mock_split_setpoints


@pytest.fixture
def mock_c_ready():
    with patch("src.on_controller_message.c_ready") as mock_c_ready:
        mock_c_ready.return_value = None
        mock_c_ready.__name__ = "mock_c_ready"
        yield mock_c_ready


@pytest.fixture
def mock_c_stopping():
    with patch("src.on_controller_message.c_stopping") as mock_c_stopping:
        mock_c_stopping.return_value = None
        mock_c_stopping.__name__ = "mock_c_stopping"
        yield mock_c_stopping


# ========================================


def test_incompatible_request(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    msg = MockMessage(topic="controller/run", payload="not important")
    c_starting(controller_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Controller is validating. Cannot act on controller/run" in messages[0].payload
    )


def test_accepts_stop_signal(state, controller_client, mock_c_stopping):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    msg = MockMessage(topic="controller/stop", payload="not important")
    c_starting(controller_client, msg, state)

    assert mock_c_stopping.called


def test_valid_start(
    message_bus,
    state,
    controller_client,
    mock_experiment_dict,
    mock_split_setpoints,
    mock_c_ready,
):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    sensors = mock_experiment_dict["config"]["sensors"]
    sensor_names = [sensor["name"] for sensor in sensors]
    ns = len(sensors)

    msg = MockMessage(topic="controller/start", payload=json.dumps({"uid": "123"}))
    c_starting(controller_client, msg, state)

    # goes through starting to awaiting_sensors
    assert state._status_history == ["starting", "awaiting_sensors"]
    # State object updated correctly
    assert state.experiment_uid == "123"
    assert state.setpoints is not None
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == mock_c_ready
    # Sensor config list updated correctly
    assert len(state.sensors) == ns + 1
    assert state.sensors["configured"] == False
    for sensor_key in state.sensors.keys():
        if sensor_key != "configured":
            assert sensor_key in sensor_names
            sensor = state.sensors[sensor_key]
            assert "last_contact" in sensor
            assert sensor["last_contact"] is None
            assert "config" in sensor
            assert sensor["config"] is not None
            assert "status" in sensor
            assert sensor["status"] is None
            assert "setpoint" in sensor
            assert sensor["setpoint"] is None
    # Split setpoints called
    mock_split_setpoints.assert_called_once_with(
        mock_experiment_dict["experiment"],
        mock_experiment_dict["config"]["resolution"],
    )
    # Timer message sent
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1 + len(sensors)
    assert messages[0].topic == "timer/start/sensor_setup"
    assert messages[0].payload == json.dumps({"uid": "123"})
    # Sensor setup messages sent
    for i, sensor in enumerate(sensors):
        assert messages[i + 1].topic == f"sensor/{sensor['name']}/setup"
        assert messages[i + 1].payload == json.dumps(sensor)
