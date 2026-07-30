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


class TestOnUIMessage:

    @pytest.fixture
    def ouim_mocks(self, message_bus, mqtt_mocks, mock_state):
        with (
            patch("src.on_ui_message.pe") as mock_publish_error,
            patch("src.on_ui_message.data_path", new="test_data"),
            patch("src.on_ui_message.validate_message") as mock_validate_message,
            patch("os.path.exists", return_value=False) as mock_path_exists,
            patch("os.makedirs", return_value=True) as mock_makedirs,
            patch("builtins.open", create=True) as mock_open,
            patch("src.on_ui_message.json.dump") as mock_json_dump,
        ):
            mock_validate_message.return_value = {"id": "123"}
            state = mock_state("idle")

            mqtt_mocks["client_class"](
                id="ui",
                topics="ui/#",
                callback=on_ui_message,
            )

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "state": state,
                "ui_client": mqtt_mocks["client_instance"],
                "validate_message": mock_validate_message,
                "path_exists": mock_path_exists,
                "makedirs": mock_makedirs,
                "open": mock_open,
                "json_dump": mock_json_dump,
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_invalid_ui_message(self, ouim_mocks):
        mqtt_val_err = MQTTValidationException("Invalid message")
        ouim_mocks["validate_message"].side_effect = mqtt_val_err

        msg = MockMessage(topic="ui/start", payload="invalid")
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with("ui/start", b"invalid")
        ouim_mocks["pe"].message_validation.assert_called_once_with(mqtt_val_err)
        ouim_mocks["path_exists"].assert_not_called()
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_ui_start_not_idle(self, ouim_mocks):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "123"

        payload = {"id": "123", "config": {}, "experiment_definition": []}
        msg = MockMessage(topic="ui/start", payload=json.dumps(payload))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/start", json.dumps(payload).encode("utf-8")
        )
        ouim_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            ouim_mocks["state"], msg
        )
        ouim_mocks["path_exists"].assert_not_called()
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_ui_start(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_uid == None
        assert ouim_mocks["state"].status == "idle"

        exp_payload = {"id": "123", "config": {}, "experiment_definition": []}
        ouim_mocks["validate_message"].return_value = exp_payload

        msg = MockMessage(topic="ui/start", payload=json.dumps(exp_payload))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/start", json.dumps(exp_payload).encode("utf-8")
        )
        ouim_mocks["path_exists"].assert_called_once_with("test_data/tmp")
        ouim_mocks["makedirs"].assert_called_once_with("test_data/tmp")
        ouim_mocks["open"].assert_called_once_with(
            "test_data/tmp/experiment_123.json", "w"
        )
        ouim_mocks["json_dump"].assert_called_once_with(
            exp_payload, ouim_mocks["open"]().__enter__()
        )

        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/validate"
        assert json.loads(messages[0].payload) == {
            "id": "123",
            "file": "test_data/tmp/experiment_123.json",
        }

    def test_ui_stop_while_idle(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_uid == None
        assert ouim_mocks["state"].status == "idle"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/stop", json.dumps({"id": "123"}).encode("utf-8")
        )
        ouim_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            ouim_mocks["state"], msg
        )
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_ui_stop(self, ouim_mocks, capsys):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "123"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/stop", json.dumps({"id": "123"}).encode("utf-8")
        )
        assert "Stopping experiment..." in capsys.readouterr().out
        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert '"id": "123"' in messages[0].payload

    def test_stop_for_wrong_uid(self, ouim_mocks):
        ouim_mocks["state"].status = "running"
        ouim_mocks["state"].experiment_uid = "456"

        msg = MockMessage(topic="ui/stop", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/stop", json.dumps({"id": "123"}).encode("utf-8")
        )
        ouim_mocks["pe"].incompatible_uid.assert_called_once_with(
            ouim_mocks["state"],
            msg,
            "123",
            "controller",
        )
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_incompatible_topic(self, ouim_mocks):
        msg = MockMessage(topic="ui/unknown", payload=json.dumps({"id": "123"}))
        on_ui_message(ouim_mocks["ui_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(
            "ui/unknown", json.dumps({"id": "123"}).encode("utf-8")
        )
        ouim_mocks["pe"].incompatible_topic.assert_called_once_with(
            ouim_mocks["state"], msg
        )
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0
