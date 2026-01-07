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
)

from src.on_ui_message import on_ui_message


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("idle", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def ui_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="ui",
        topics="ui/#",
        callback=on_ui_message,
    )
    return mqtt_mocks["client_instance"]


@pytest.fixture(autouse=True)
def data_path():
    with patch("src.on_ui_message.data_path", new="test_data"):
        yield "test_data"


# ========================================


def test_invalid_ui_message(message_bus, state, ui_client):
    assert state.experiment_uid == None

    msg = MockMessage(topic="ui/start", payload="invalid")
    on_ui_message(ui_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert f"Error decoding ui/start message, wrong JSON" in messages[0].payload


def test_missing_uid(message_bus, state, ui_client):
    assert state.experiment_uid == None

    msg = MockMessage(topic="ui/start", payload=json.dumps({"no": "uid"}))
    on_ui_message(ui_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        f"Error decoding ui/start message, missing: \n   'uid'"
        in json.loads(messages[0].payload)["error"]
    )


def test_valid_ui_start(message_bus, state, ui_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("os.path.exists", return_value=False) as mock_path_exists, patch(
        "os.makedirs", return_value=True
    ) as mock_makedirs, patch("builtins.open", create=True) as mock_open, patch(
        "src.on_ui_message.json.dump"
    ) as mock_json_dump:
        msg = MockMessage(topic="ui/start", payload=json.dumps({"uid": "123"}))
        on_ui_message(ui_client, msg, state)

        mock_path_exists.assert_called_once_with("test_data/tmp")
        mock_makedirs.assert_called_once_with("test_data/tmp")
        mock_open.assert_called_once_with("test_data/tmp/experiment_123.json", "w")
        mock_json_dump.assert_called_once_with({"uid": "123"}, mock_open().__enter__())

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/validate"
    assert json.loads(messages[0].payload) == {
        "uid": "123",
        "file": "test_data/tmp/experiment_123.json",
    }


def test_idle_only_listens_to_start(message_bus, state, ui_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    msg = MockMessage(topic="ui/stop", payload=json.dumps({"uid": "123"}))
    on_ui_message(ui_client, msg, state)

    assert state.status == "idle"
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert "Controller is idle. Cannot act on ui/stop" in messages[0].payload


def test_valid_ui_stop(message_bus, state, ui_client):
    state.status = "running"
    state.experiment_uid = "123"

    msg = MockMessage(topic="ui/stop", payload=json.dumps({"uid": "123"}))
    on_ui_message(ui_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/stop"
    assert '"uid": "123"' in messages[0].payload


def test_stop_for_wrong_uid(message_bus, state, ui_client):
    state.status = "running"
    state.experiment_uid = "456"

    msg = MockMessage(topic="ui/stop", payload=json.dumps({"uid": "123"}))
    on_ui_message(ui_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert (
        "Current experiment is 456. Cannot act on ui/stop for experiment 123."
        in messages[0].payload
    )


def test_not_idle_only_listens_to_stop(message_bus, state, ui_client):
    state.status = "running"
    state.experiment_uid = "123"

    msg = MockMessage(topic="ui/start", payload=json.dumps({"uid": "123"}))
    on_ui_message(ui_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    assert "Controller is running. Cannot act on ui/start" in messages[0].payload
