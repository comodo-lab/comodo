import json
import pytest
from jsonschema import ValidationError
from unittest.mock import patch
import yaml

from utils.mqtt_validator import (
    match_topic,
    load_spec,
    validate_message,
    check_payload_json_validity,
    check_topic_expected,
    check_message_valid,
    print_and_publish_error,
    MQTTValidationException,
)
from utils.tests.mocks.mock_topic_map import mock_topic_map
from utils.tests.mocks.mock_mqtt_clients import message_bus, mqtt_mocks


class TestMatchTopic:
    def test_match_topic_exact(self, mock_topic_map):
        result = match_topic("test/topic", mock_topic_map)
        assert result == mock_topic_map["test/topic"]

    def test_match_topic_with_single_level_wildcard(self, mock_topic_map):
        result = match_topic("wildcard/123/topic", mock_topic_map)
        assert result == mock_topic_map["wildcard/+/topic"]

    def test_match_topic_with_multi_level_wildcard(self, mock_topic_map):
        result = match_topic("wildcard/topic/try/456", mock_topic_map)
        assert result == mock_topic_map["wildcard/topic/#"]

    def test_no_matching_topic(self, mock_topic_map):
        result = match_topic("nonexistent/topic", mock_topic_map)
        assert result is None


class TestLoadSpec:
    def test_load_spec(self):
        topic_map = load_spec("/utils/tests/file_fixtures/sample_asyncapi.yaml")

        assert "error/message/malformed" in topic_map
        tmm = topic_map["error/message/malformed"]
        assert tmm["name"] == "errorMalformed"
        assert tmm["schema"]["type"] == "object"
        assert tmm["schema"]["required"] == ["topic", "error", "error_message"]

        assert "error/message/invalid" in topic_map
        tmi = topic_map["error/message/invalid"]
        assert tmi["name"] == "errorInvalid"
        assert tmi["schema"]["properties"]["error"]["enum"] == ["validation_error"]

        assert "error/message/unexpected" in topic_map
        tmu = topic_map["error/message/unexpected"]
        assert tmu["name"] == "errorUnexpected"
        assert tmu["schema"]["required"] == ["topic", "error"]

    def test_load_spec_is_cached(self):
        load_spec.cache_clear()
        with patch("utils.mqtt_validator.yaml.safe_load", wraps=yaml.safe_load) as load:
            first = load_spec("/utils/tests/file_fixtures/sample_asyncapi.yaml")
            second = load_spec("/utils/tests/file_fixtures/sample_asyncapi.yaml")

        load.assert_called_once()
        assert second is first


class TestValidateMessage:
    @pytest.fixture
    def validate_message_mocks(self):
        with (
            patch("utils.mqtt_validator.check_payload_json_validity") as mock_check_pay,
            patch("utils.mqtt_validator.check_topic_expected") as mock_check_topic,
            patch("utils.mqtt_validator.check_message_valid") as mock_check_message,
        ):
            yield {
                "mock_check_payload_json_validity": mock_check_pay,
                "mock_check_topic_expected": mock_check_topic,
                "mock_check_message_valid": mock_check_message,
            }

    def test_unexpected_topic_MQTT_only(self, validate_message_mocks):
        validate_message_mocks["mock_check_topic_expected"].side_effect = (
            MQTTValidationException("Unexpected topic: unexpected/topic")
        )

        with pytest.raises(MQTTValidationException) as e:
            validate_message(
                topic="unexpected/topic",
                payload='{"key": "val"}',
                combine_exceptions=True,
            )

        assert "Unexpected topic: unexpected/topic" in str(e.value)
        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "unexpected/topic"
        )
        validate_message_mocks["mock_check_payload_json_validity"].assert_not_called()

    def test_unexpected_topic(self, validate_message_mocks):
        validate_message_mocks["mock_check_topic_expected"].side_effect = (
            MQTTValidationException("Unexpected topic: unexpected/topic")
        )

        with pytest.raises(MQTTValidationException) as e:
            validate_message(
                topic="unexpected/topic",
                payload='{"key": "val"}',
                combine_exceptions=False,
            )

        assert "Unexpected topic: unexpected/topic" in str(e.value)
        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "unexpected/topic"
        )
        validate_message_mocks["mock_check_payload_json_validity"].assert_not_called()

    def test_invalid_payload_MQTT_only(self, validate_message_mocks):
        validate_message_mocks["mock_check_payload_json_validity"].side_effect = (
            json.JSONDecodeError(msg="not json", doc="json_doc", pos=0)
        )

        with pytest.raises(MQTTValidationException) as e:
            validate_message(
                topic="expected/topic",
                payload='{"key": "val"}',
                combine_exceptions=True,
            )

        assert "Invalid JSON payload for topic 'expected/topic'" in str(e.value)
        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "expected/topic"
        )
        validate_message_mocks[
            "mock_check_payload_json_validity"
        ].assert_called_once_with('{"key": "val"}')

    def test_invalid_payload(self, validate_message_mocks):
        validate_message_mocks["mock_check_payload_json_validity"].side_effect = (
            json.JSONDecodeError(msg="not json", doc="json_doc", pos=0)
        )

        with pytest.raises(json.JSONDecodeError) as e:
            validate_message(
                topic="expected/topic",
                payload='{"key": "val"}',
                combine_exceptions=False,
            )

        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "expected/topic"
        )
        validate_message_mocks[
            "mock_check_payload_json_validity"
        ].assert_called_once_with('{"key": "val"}')

    def test_invalid_message_MQTT_only(self, validate_message_mocks):
        validate_message_mocks["mock_check_message_valid"].side_effect = (
            ValidationError(
                "Well this is odd...",
                validator="you_failed",
                path=[],
                schema={},
                instance={},
            )
        )

        with pytest.raises(MQTTValidationException) as e:
            validate_message(
                topic="expected/topic",
                payload='{"key": "val"}',
                combine_exceptions=True,
            )

        assert "Well this is odd..." in str(e.value)
        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "expected/topic"
        )
        validate_message_mocks[
            "mock_check_payload_json_validity"
        ].assert_called_once_with('{"key": "val"}')
        validate_message_mocks["mock_check_message_valid"].assert_called_once_with(
            validate_message_mocks["mock_check_topic_expected"].return_value,
            validate_message_mocks["mock_check_payload_json_validity"].return_value,
        )

    def test_invalid_message(self, validate_message_mocks):
        validate_message_mocks["mock_check_message_valid"].side_effect = (
            ValidationError(
                "Well this is odd...",
                validator="whodis",
                path=[],
                schema={},
                instance={},
            )
        )

        with pytest.raises(ValidationError) as e:
            validate_message(
                topic="expected/topic",
                payload='{"key": "val"}',
                combine_exceptions=False,
            )

        assert "Well this is odd..." in str(e.value)
        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "expected/topic"
        )
        validate_message_mocks[
            "mock_check_payload_json_validity"
        ].assert_called_once_with('{"key": "val"}')
        validate_message_mocks["mock_check_message_valid"].assert_called_once_with(
            validate_message_mocks["mock_check_topic_expected"].return_value,
            validate_message_mocks["mock_check_payload_json_validity"].return_value,
        )

    def test_valid_message(self, validate_message_mocks):
        mock_json_load = validate_message_mocks["mock_check_payload_json_validity"]
        mock_json_load.return_value = {"key": "val"}

        loaded = validate_message(
            topic="expected/topic",
            payload='{"key": "val"}',
            combine_exceptions=True,
        )

        validate_message_mocks["mock_check_topic_expected"].assert_called_once_with(
            "asyncapi", "expected/topic"
        )
        mock_json_load.assert_called_once_with('{"key": "val"}')
        validate_message_mocks["mock_check_message_valid"].assert_called_once_with(
            validate_message_mocks["mock_check_topic_expected"].return_value,
            validate_message_mocks["mock_check_payload_json_validity"].return_value,
        )
        assert loaded == mock_json_load.return_value


class TestCheckTopicExpected:
    @pytest.fixture
    def check_topic_mocks(self):
        with (
            patch("utils.mqtt_validator.load_spec") as mock_load_spec,
            patch("utils.mqtt_validator.match_topic") as mock_match_topic,
        ):
            yield {
                "mock_load_spec": mock_load_spec,
                "mock_match_topic": mock_match_topic,
            }

    def test_topic_found(self, check_topic_mocks, mock_topic_map):
        check_topic_mocks["mock_load_spec"].return_value = mock_topic_map
        check_topic_mocks["mock_match_topic"].return_value = mock_topic_map[
            "test/topic"
        ]

        result = check_topic_expected("schema_name", "test/topic")

        check_topic_mocks["mock_load_spec"].assert_called_once_with("schema_name")
        check_topic_mocks["mock_match_topic"].assert_called_once_with(
            "test/topic", mock_topic_map
        )
        assert result == mock_topic_map["test/topic"]

    def test_topic_not_found(self, check_topic_mocks, mock_topic_map):
        check_topic_mocks["mock_load_spec"].return_value = mock_topic_map
        check_topic_mocks["mock_match_topic"].return_value = None

        with pytest.raises(MQTTValidationException):
            result = check_topic_expected("schema_name", "inexistent/topic")

        check_topic_mocks["mock_load_spec"].assert_called_once_with("schema_name")
        check_topic_mocks["mock_match_topic"].assert_called_once_with(
            "inexistent/topic", mock_topic_map
        )


class TestCheckPayloadJsonValidity:
    def test_valid_json(self):
        result = check_payload_json_validity('{"key": "val"}')
        assert result == {"key": "val"}

    def test_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            check_payload_json_validity("not valid json")


class TestCheckMessageValid:

    def test_schema_mismatch(self, mock_topic_map):
        entry = mock_topic_map["test/topic"]
        loaded_payload = {"test_str": "something", "something": "unexpected"}
        with pytest.raises(ValidationError):
            check_message_valid(entry, loaded_payload)

    def test_missing_required_field(self, mock_topic_map):
        entry = mock_topic_map["test/topic"]
        loaded_payload = {"test_str": "something"}  # Missing 'test_num'
        with pytest.raises(ValidationError):
            check_message_valid(entry, loaded_payload)

    def test_additional_properties_not_allowed(self, mock_topic_map):
        entry = mock_topic_map["test/topic"]
        loaded_payload = {
            "test_str": "something",
            "test_num": 123,
            "extra_field": "not allowed",
        }
        with pytest.raises(ValidationError):
            check_message_valid(entry, loaded_payload)

    def test_valid_message(self, mock_topic_map):
        entry = mock_topic_map["test/topic"]
        loaded_payload = {"test_str": "something", "test_num": 123}
        result = check_message_valid(entry, loaded_payload)
        assert result is None

    def test_additional_properties_allowed(self, mock_topic_map):
        entry = mock_topic_map["another/topic"]
        loaded_payload = {
            "another_str": "something",
            "another_num": 456,
            "extra_field": "allowed",
        }
        result = check_message_valid(entry, loaded_payload)
        assert result is None


class TestPrintAndPublishError:

    def test_print_and_publish_error(self, message_bus, mqtt_mocks, capsys):
        print_and_publish_error(
            "error/topic", MQTTValidationException("Test error message")
        )

        messages = message_bus.get_messages()
        assert len(messages) == 1
        assert messages[0].topic == "error/topic"
        assert json.loads(messages[0].payload) == {
            "code": "message_validation",
            "message": "Test error message",
        }

        captured = capsys.readouterr()
        assert "ERROR: Test error message" in captured.out
