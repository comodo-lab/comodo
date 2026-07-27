import json
import pytest
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
)

from src.on_ui_message import on_ui_message
from utils.mqtt_validator import MQTTValidationException


class TestOnWatchdogMessage:

    @pytest.fixture
    def ouim_mocks(self, mqtt_mocks, mock_state):
        with (
            patch("src.on_ui_message.data_path", new="test_data"),
            patch("src.on_ui_message.validate_message") as mock_validate_message,
        ):
            state = mock_state("idle")

            mqtt_mocks["client_class"](
                id="ui",
                topics="ui/#",
                callback=on_ui_message,
            )

            yield {
                "state": state,
                "ui_client": mqtt_mocks["client_instance"],
                "validate_message": mock_validate_message,
            }

    # ========================================

    def test_invalid_ui_message(self, message_bus, ouim_mocks, capsys):
        assert ouim_mocks["state"].experiment_uid == None

        msg = MockMessage(topic="ui/start", payload="invalid")
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = "Cannot decode ui/start message, wrong JSON:"
        assert exp_err in messages[0].payload
        assert f"ERROR: {exp_err}" in capsys.readouterr().out
        ouim_mocks["validate_message"].assert_not_called()

    def test_missing_id(self, message_bus, ouim_mocks, capsys):
        assert ouim_mocks["state"].experiment_uid == None

        exp_err = "Cannot decode ui/start message, missing: \n   'id'"
        msg = MockMessage(topic="ui/start", payload=json.dumps({"config": "foo"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        messages = message_bus.get_messages(decoded=True)
        payload_obj = json.loads(messages[0].payload)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert payload_obj["code"] == "missing_key"
        assert exp_err in payload_obj["message"]
        assert exp_err in capsys.readouterr().out
        ouim_mocks["validate_message"].assert_not_called()

    def test_invalid_ui_start(self, message_bus, ouim_mocks, capsys):
        assert ouim_mocks["state"].experiment_uid == None
        assert ouim_mocks["state"].status == "idle"
        ouim_mocks["validate_message"].side_effect = MQTTValidationException(
            "Invalid experiment"
        )

        exp_payload = {"id": "123", "config": {}, "experiment_definition": []}
        msg = MockMessage(topic="ui/start", payload=json.dumps(exp_payload))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/start", json.dumps(exp_payload).encode("utf-8")
        )

        messages = message_bus.get_messages(decoded=True)
        payload_obj = json.loads(messages[0].payload)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        assert payload_obj["code"] == "experiment_validation"
        assert "Invalid experiment" in messages[0].payload
        assert "Invalid experiment" in capsys.readouterr().out

    def test_valid_ui_start(self, message_bus, ouim_mocks):
        assert ouim_mocks["state"].experiment_uid == None
        assert ouim_mocks["state"].status == "idle"

        exp_payload = {"id": "123", "config": {}, "experiment_definition": []}
        with (
            patch("os.path.exists", return_value=False) as mock_path_exists,
            patch("os.makedirs", return_value=True) as mock_makedirs,
            patch("builtins.open", create=True) as mock_open,
            patch("src.on_ui_message.json.dump") as mock_json_dump,
        ):
            msg = MockMessage(topic="ui/start", payload=json.dumps(exp_payload))
            on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

            ouim_mocks["validate_message"].assert_called_once_with(
                "ui/start", json.dumps(exp_payload).encode("utf-8")
            )
            mock_path_exists.assert_called_once_with("test_data/tmp")
            mock_makedirs.assert_called_once_with("test_data/tmp")
            mock_open.assert_called_once_with("test_data/tmp/experiment_123.json", "w")
            mock_json_dump.assert_called_once_with(exp_payload, mock_open().__enter__())

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/validate"
        assert json.loads(messages[0].payload) == {
            "id": "123",
            "file": "test_data/tmp/experiment_123.json",
        }

    def test_idle_only_listens_to_start(self, message_bus, ouim_mocks):
        assert ouim_mocks["state"].experiment_uid == None
        assert ouim_mocks["state"].status == "idle"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        assert ouim_mocks["state"].status == "idle"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is idle. Cannot act on ui/stop." in messages[0].payload
        )
        ouim_mocks["validate_message"].assert_not_called()

    def test_valid_ui_stop(self, message_bus, ouim_mocks):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "123"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert '"id": "123"' in messages[0].payload

    def test_stop_for_wrong_uid(self, message_bus, ouim_mocks):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "456"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Current experiment is 456. Controller cannot act on ui/stop for experiment 123."
            in messages[0].payload
        )
        ouim_mocks["validate_message"].assert_not_called()

    def test_not_idle_only_listens_to_stop(self, message_bus, ouim_mocks):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "123"

        payload = {"id": "123", "config": {}, "experiment_definition": []}
        msg = MockMessage(topic="ui/start", payload=json.dumps(payload))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/start", json.dumps(payload).encode("utf-8")
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is running. Cannot act on ui/start."
            in messages[0].payload
        )
