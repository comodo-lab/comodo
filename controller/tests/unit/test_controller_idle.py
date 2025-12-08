import json
import pytest
import time as t
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
)

from src.on_controller_message import c_idle
from src.validation import ValidationException

# =============== Fixtures ===============


state = mock_state("idle")


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_idle,
        obj=state,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture(autouse=True)
def mock_c_starting():
    with patch("src.on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None
        mock_c_starting.__name__ = "mock_c_starting"
        yield mock_c_starting


# ========================================


def test_incompatible_request(message_bus, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    msg = MockMessage(topic="controller/run", payload="not important")
    c_idle(controller_client, msg, state)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert "Controller is idle. Cannot act on controller/run" in messages[0].payload


def test_wrong_json(message_bus, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    msg = MockMessage(topic="controller/validate", payload="this is not json")
    c_idle(controller_client, msg, state)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Error decoding controller/validate message, wrong JSON" in messages[0].payload
    )


def test_json_missing_file_key(message_bus, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    msg = MockMessage(topic="controller/validate", payload=json.dumps({"uid": "123"}))
    c_idle(controller_client, msg, state)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Error decoding controller/validate message, missing: \n   'file'"
        in json.loads(messages[0].payload)["error"]
    )


def test_missing_file(message_bus, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    msg = MockMessage(
        topic="controller/validate",
        payload=json.dumps({"uid": "123", "file": "missing_file.json"}),
    )
    with patch("src.on_controller_message.validate_file") as mock_validate_file:
        mock_validate_file.side_effect = ValidationException(
            f"Error: File not found - {state.schema_path}"
        )
        c_idle(controller_client, msg, state)

        mock_validate_file.assert_called_once_with(
            "missing_file.json", state.schema_path
        )

    assert state._status_history == ["validating", "idle"]
    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/validator/failed"
    assert "File not found" in messages[0].payload


def test_valid_file(message_bus, state, controller_client, mock_c_starting):
    assert state.experiment_uid == None
    assert state.experiment_start_time == None
    assert state.status == "idle"

    with patch("src.on_controller_message.validate_file") as mock_validate_file:
        mock_validate_file.return_value = {
            "uid": "123",
            "experiment": {},
        }
        msg = MockMessage(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": "valid_file.json"}),
        )
        c_idle(controller_client, msg, state)

        mock_validate_file.assert_called_once_with("valid_file.json", state.schema_path)

    assert state.experiment_start_time != None
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == mock_c_starting
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 2
    assert messages[0].topic == "validator/passed"
    assert '{"uid": "123", "valid": true}' in messages[0].payload
    assert messages[1].topic == "controller/start"
    assert '{"uid": "123"}' in messages[1].payload


def test_invalid_file(message_bus, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("src.on_controller_message.validate_file") as mock_validate_file:
        mock_validate_file.side_effect = ValidationException(f"Test validation error")
        msg = MockMessage(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": "invalid_file.json"}),
        )
        c_idle(controller_client, msg, state)

    assert state._status_history == ["validating", "idle"]
    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/validator/failed"
    assert "Test validation error" in messages[0].payload
    assert '"uid": "123"' in messages[0].payload
