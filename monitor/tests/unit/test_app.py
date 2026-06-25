import json
from unittest.mock import patch

from jsonschema import ValidationError
import pytest

from app import on_message

from utils.mqtt_validator import MQTTValidationException
from utils.tests.mocks.mock_mqtt_clients import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)


class TestOnMessage:
    @pytest.fixture
    def on_message_mocks(self):
        with (patch("app.validate_message") as mock_val_msg,):
            mocks = {
                "mock_validate_message": mock_val_msg,
            }
            yield mocks

    # ========================================

    def test_unexpected_topic(self, message_bus, on_message_mocks):
        mocks = on_message_mocks
        mocks["mock_validate_message"].side_effect = MQTTValidationException(
            "Unexpected topic"
        )

        msg = MockMessage(
            topic="something/unexpected",
            payload='{"topic": "test", "error": "something wrong"}',
        )
        on_message(None, msg, None)

        assert mocks["mock_validate_message"].called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "unexpected_topic"
        assert payload["message"] == f"Unexpected topic: {msg.topic}"

    def test_invalid_json(self, message_bus, on_message_mocks):
        mocks = on_message_mocks
        mocks["mock_validate_message"].side_effect = json.JSONDecodeError(
            msg="not json", doc="json_doc", pos=0
        )

        msg = MockMessage(
            topic="this/is/fine",
            payload="this is not valid json",
        )
        on_message(None, msg, None)

        assert mocks["mock_validate_message"].called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "invalid_json"
        assert payload["message"] == "not json: line 1 column 1 (char 0)"
        assert payload["topic"] == msg.topic

    def test_schema_mismatch(self, message_bus, on_message_mocks):
        mocks = on_message_mocks
        mocks["mock_validate_message"].side_effect = ValidationError(
            "Well this is odd...", validator="whodis", path=[], schema={}, instance={}
        )

        msg = MockMessage(
            topic="this/is/fine",
            payload='{"this": "does not", "match": "the schema"}',
        )
        on_message(None, msg, None)

        assert mocks["mock_validate_message"].called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "validation_error"
        assert payload["message"] == "Well this is odd..."
        assert payload["topic"] == msg.topic
        assert payload["failed_check"] == "whodis"
        assert payload["offending_key"] == "<root>"

    def test_unexpected_exception(self, message_bus, on_message_mocks, capsys):
        mocks = on_message_mocks
        mocks["mock_validate_message"].side_effect = Exception("Unexpected error")

        msg = MockMessage(
            topic="this/is/odd",
            payload='{"an": "unexpected", "exception": "ocurred"}',
        )
        on_message(None, msg, None)

        assert mocks["mock_validate_message"].called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0
        captured = capsys.readouterr()
        assert "ERROR: Message invalid: Unexpected error" in captured.out

    def test_valid_message(self, message_bus, on_message_mocks):
        mocks = on_message_mocks
        mocks["mock_validate_message"].side_effect = None
        msg = MockMessage(
            topic="this/is/fine",
            payload='{"this": "is", "also": "fine"}',
        )
        on_message(None, msg, None)

        assert mocks["mock_validate_message"].called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            raise_MQTTValidationException_only=False,
        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0
