import json
import pytest
import time as t
import os
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

from src.on_controller_message import c_ready, assign_serial_id


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("ready", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_ready,
        obj=state,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture(autouse=True)
def mock_split_setpoints(mock_setpoints):
    with patch("src.on_controller_message.split_setpoints") as mock_split_setpoints:
        mock_split_setpoints.return_value = mock_setpoints
        yield mock_split_setpoints


@pytest.fixture
def mock_c_running(autouse=True):
    with patch("src.on_controller_message.c_running") as mock_c_running:
        mock_c_running.return_value = None
        mock_c_running.__name__ = "mock_c_running"
        yield mock_c_running


# ========================================


def test_incompatible_request(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    msg = MockMessage(
        topic="controller/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    c_ready(controller_client, msg, state)

    assert state.status == "awaiting_sensors"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Controller is awaiting_sensors. Cannot act on controller/something_else"
        in messages[0].payload
    )


def test_accepts_stop_signal(message_bus, state, controller_client, mock_c_stopping):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    msg = MockMessage(topic="controller/stop", payload="not important")
    c_ready(controller_client, msg, state)

    assert mock_c_stopping.called


def test_updates_states_correctly(
    message_bus,
    state,
    controller_client,
    mock_c_running,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    with patch("src.on_controller_message.assign_serial_id") as mock_assign:
        mock_assign.return_value = None
        msg = MockMessage(topic="controller/ready", payload=json.dumps({"uid": "123"}))
        c_ready(controller_client, msg, state)

        mock_assign.assert_called_once_with(state)
        assert state.status == "ready"
        assert state.experiment_uid == "123"
        assert controller_client.callback == mock_c_running
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/run"
        assert messages[0].payload == '{"uid": "123"}'
