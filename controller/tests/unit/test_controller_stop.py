import json
import pytest
import os
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.on_controller_message import c_stopping


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("end", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_stopping,
        obj=state,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture(autouse=True)
def mock_c_idle():
    with patch("src.on_controller_message.c_idle") as mock_c_idle:
        mock_c_idle.return_value = None
        mock_c_idle.__name__ = "mock_c_idle"
        yield mock_c_idle


@pytest.fixture(autouse=True)
def mock_dump():
    with patch("src.on_controller_message.dump_database_for_experiment") as mock_dump:
        mock_dump.return_value = None
        yield mock_dump


# ========================================


def test_incompatible_request(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    msg = MockMessage(
        topic="controller/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    c_stopping(controller_client, msg, state)

    assert state.status == "running"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[-1].topic == "error/controller"
    assert (
        "Controller is running. Cannot act on controller/something_else"
        in messages[-1].payload
    )


def test_checks_uid(message_bus, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    msg = MockMessage(
        topic="controller/stop",
        payload=json.dumps({"uid": "456"}),
    )
    c_stopping(controller_client, msg, state)

    assert state.status == "running"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[-1].topic == "error/controller"
    assert (
        "Current experiment is 123. Cannot act on controller/stop for experiment 456."
        in messages[-1].payload
    )


def test_valid_stop(message_bus, state, controller_client, mock_dump):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    msg = MockMessage(topic="controller/stop", payload=json.dumps({"uid": "123"}))
    c_stopping(controller_client, msg, state)

    assert state.status == "stopping"
    mock_dump.assert_called_once()
    state.reset.assert_called_once()
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/stopped"
    assert messages[0].payload == json.dumps({"uid": "123"})


def test_controller_stopped_changes_callback_to_idle(
    message_bus, state, controller_client
):
    assert controller_client.callback == c_stopping
    state.status = "stopping"

    msg = MockMessage(topic="controller/stopped", payload=json.dumps({"uid": "123"}))
    c_stopping(controller_client, msg, state)

    assert controller_client.callback.__name__ == "mock_c_idle"


def test_stop_from_any_callback(message_bus, state, controller_client, mock_dump):
    assert state.experiment_uid == "123"
    state.status == "something"
    controller_client.callback = "mock_callback"

    msg = MockMessage(topic="controller/stop", payload=json.dumps({"uid": "123"}))
    c_stopping(controller_client, msg, state)

    assert state.status == "stopping"
    mock_dump.assert_called_once()
    state.reset.assert_called_once()
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/stopped"
    assert messages[0].payload == json.dumps({"uid": "123"})
