import json
from unittest.mock import patch
import pytest

from app import on_message

from utils.tests.mocks.mock_mqtt_clients import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)


class TestOnMessage:
    def test_valid_message(self, message_bus, mock_topic_map):
        with patch("utils.message_validator.load_spec", return_value=mock_topic_map):
            msg = MockMessage(
                topic="error/message/unexpected",
                payload='{"topic": "test", "error": "unexpected_topic"}',
            )
            on_message(None, msg)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0

    def test_unexpected_topic(self, message_bus, mock_topic_map):
        with patch("utils.message_validator.load_spec", return_value=mock_topic_map):
            msg = MockMessage(topic="some/unknown/topic", payload='{"a": 1}')
            on_message(None, msg)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "unexpected_topic"

    def test_invalid_json(self, message_bus, mock_topic_map):
        with patch("utils.message_validator.load_spec", return_value=mock_topic_map):
            msg = MockMessage(
                topic="error/message/malformed",
                payload="not valid json",
            )
            on_message(None, msg)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "invalid_json"

    def test_schema_mismatch(self, message_bus, mock_topic_map):
        with patch("utils.message_validator.load_spec", return_value=mock_topic_map):
            msg = MockMessage(
                topic="error/message/unexpected",
                payload='{"topic": "test", "error": "unknown_error"}',
            )
            on_message(None, msg)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        payload = json.loads(messages[0].payload)
        assert payload["code"] == "validation_error"
