import json
import pytest
from jsonschema import ValidationError

from utils.mqtt_validator import (
    load_spec,
    check_payload_json_validity,
    check_topic_expected,
    check_message_valid,
    UnexpectedTopicException,
)


class TestLoadSpec:
    def test_load_spec(self):
        topic_map = load_spec("utils/tests/file_fixtures/sample_asyncapi.yaml")
        assert "error/message/malformed" in topic_map
        assert topic_map["error/message/malformed"]["name"] == "errorMalformed"
        assert topic_map["error/message/malformed"]["schema"]["type"] == "object"
        assert topic_map["error/message/malformed"]["schema"]["required"] == [
            "topic",
            "error",
            "error_message",
        ]

        assert "error/message/invalid" in topic_map
        assert topic_map["error/message/invalid"]["name"] == "errorInvalid"
        assert (
            topic_map["error/message/invalid"]["schema"]["properties"]["error"]["enum"]
            == ["validation_error"]
        )

        assert "error/message/unexpected" in topic_map
        assert topic_map["error/message/unexpected"]["name"] == "errorUnexpected"
        assert topic_map["error/message/unexpected"]["schema"]["required"] == [
            "topic",
            "error",
        ]


class TestCheckPayloadJsonValidity:
    def test_valid_json(self):
        result = check_payload_json_validity("test/topic", '{"key": "val"}')
        assert result is None

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            check_payload_json_validity("test/topic", "not valid json")

class TestCheckTopicExpected:
    def test_topic_found(self):
        entry = {"name": "test", "schema": {}}
        result = check_topic_expected(entry, "test/topic")
        assert result is None

    def test_topic_not_found(self):
        with pytest.raises(UnexpectedTopicException):
            check_topic_expected(None, "test/topic")

class TestCheckMessageValid:
    def test_valid_message(self, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test", "error": "unexpected_topic"}'
        result = check_message_valid(entry, "error/message/unexpected", payload)
        assert result is None

    def test_schema_mismatch(self, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test", "error": "not_in_enum"}'
        with pytest.raises(ValidationError):
            check_message_valid(entry, "error/message/unexpected", payload)

    def test_missing_required_field(self, mock_topic_map):
        entry = mock_topic_map["error/message/unexpected"]
        payload = '{"topic": "test"}'
        with pytest.raises(ValidationError):
            check_message_valid(entry, "error/message/unexpected", payload)
