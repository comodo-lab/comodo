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
        assert payload["code"] == "invalid_json"
        assert "message" in payload


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
        assert payload["code"] == "unexpected_topic"
        assert "message" in payload


class TestCheckMessageValid:
    def test_valid_message(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"code": "unexpected_topic", "message": "something"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)

    def test_schema_mismatch(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"code": "unexpected_topic", "extra_field": "bad"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is False
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/invalid"
        err = json.loads(messages[0].payload)
        assert err["code"] == "validation_error"
        assert "message" in err

    def test_missing_required_field(self, message_bus, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"code": "unexpected_topic"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is False
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/invalid"
