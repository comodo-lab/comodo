import json
import pytest

from checks import (
    check_payload_json_validity,
    check_topic_expected,
    check_message_valid,
)

from utils.tests.mocks.mock_mqtt_clients import (
    message_bus,
    mqtt_mocks,
)


class TestCheckPayloadJsonValidity:
    def test_valid_json(self, message_bus):
        result = check_payload_json_validity("test/topic", '{"key": "val"}')
        assert result is True
        assert len(message_bus.get_messages()) == 0

    def test_invalid_json(self, message_bus):
        result = check_payload_json_validity("test/topic", "not valid json")
        assert result is None
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/malformed"
        payload = json.loads(messages[0].payload)
        assert payload["error"] == "invalid_json"
        assert payload["topic"] == "test/topic"
        assert "error_message" in payload


class TestCheckTopicExpected:
    def test_topic_found(self, message_bus):
        entry = {"name": "test", "schema": {}}
        result = check_topic_expected(entry, "test/topic")
        assert result is True
        assert len(message_bus.get_messages()) == 0

    def test_topic_not_found(self, message_bus):
        result = check_topic_expected(None, "test/topic")
        assert result is False
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/unexpected"
        payload = json.loads(messages[0].payload)
        assert payload["error"] == "unexpected_topic"
        assert payload["topic"] == "test/topic"


class TestCheckMessageValid:
    def test_valid_message(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test", "error": "unexpected_topic"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is True
        assert len(message_bus.get_messages()) == 0

    def test_schema_mismatch(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test", "error": "not_in_enum"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is False
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/invalid"
        err = json.loads(messages[0].payload)
        assert err["error"] == "validation_error"
        assert err["topic"] == "error/message/unexpected"
        assert err["channel"] == "errorUnexpected"

    def test_missing_required_field(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is False
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/invalid"
