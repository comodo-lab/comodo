import json
from unittest.mock import patch

from jsonschema import ValidationError
import pytest

from monitor import on_message, print_and_publish_error, monitor, main

from utils.mqtt_validator import MQTTValidationException
from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mqtt_validator_mocks,
)


class TestPrintAndPublishError:
    def test_with_topic(self, message_bus, capsys):
        print_and_publish_error("some_code", "Some message", topic="a/topic", extra=1)

        assert capsys.readouterr().out == "ERROR: Some message (topic: a/topic)\n"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        assert json.loads(messages[0].payload) == {
            "code": "some_code",
            "message": "Some message",
            "topic": "a/topic",
            "extra": 1,
        }

    def test_without_topic(self, message_bus, capsys):
        print_and_publish_error("some_code", "Some message")

        assert capsys.readouterr().out == "ERROR: Some message\n"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message"
        assert json.loads(messages[0].payload) == {
            "code": "some_code",
            "message": "Some message",
        }


class TestOnMessage:
    @pytest.fixture
    def om_mocks(self, mqtt_validator_mocks):
        with patch("monitor.print_and_publish_error") as mock_print_and_publish_error:
            yield {
                "validate_message": mqtt_validator_mocks["validate_message"],
                "print_and_publish_error": mock_print_and_publish_error,
            }

    def run_on_message(self, mocks, topic, payload):
        """Calls on_message with a message, and checks it was validated."""
        msg = MockMessage(topic=topic, payload=payload)
        on_message(None, msg, None)
        mocks["validate_message"].assert_called_once_with(
            topic=msg.topic,
            payload=msg.payload,
            combine_exceptions=False,
        )
        return msg

    # ========================================

    def test_valid_message(self, om_mocks):
        om_mocks["validate_message"].side_effect = None

        self.run_on_message(om_mocks, "this/is/fine", '{"this": "is", "also": "fine"}')

        om_mocks["print_and_publish_error"].assert_not_called()

    def test_unexpected_topic(self, om_mocks):
        om_mocks["validate_message"].side_effect = MQTTValidationException(
            "Unexpected topic"
        )

        msg = self.run_on_message(
            om_mocks, "something/unexpected", '{"topic": "test", "error": "wrong"}'
        )

        om_mocks["print_and_publish_error"].assert_called_once_with(
            "unexpected_topic", f"Unexpected topic: {msg.topic}"
        )

    def test_invalid_json(self, om_mocks):
        om_mocks["validate_message"].side_effect = json.JSONDecodeError(
            msg="not json", doc="json_doc", pos=0
        )

        msg = self.run_on_message(om_mocks, "this/is/fine", "this is not valid json")

        om_mocks["print_and_publish_error"].assert_called_once_with(
            "invalid_json", "not json: line 1 column 1 (char 0)", topic=msg.topic
        )

    def test_payload_not_utf8(self, om_mocks):
        om_mocks["validate_message"].side_effect = UnicodeDecodeError(
            "utf-8", b"\x80abc", 0, 1, "invalid start byte"
        )

        msg = self.run_on_message(om_mocks, "this/is/fine", b"\x80abc")

        om_mocks["print_and_publish_error"].assert_called_once_with(
            "invalid_json",
            "'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
            topic=msg.topic,
        )

    def test_schema_mismatch_at_root(self, om_mocks):
        om_mocks["validate_message"].side_effect = ValidationError(
            "Well this is odd...", validator="whodis", path=[], schema={}, instance={}
        )

        msg = self.run_on_message(
            om_mocks, "this/is/fine", '{"this": "does not", "match": "the schema"}'
        )

        om_mocks["print_and_publish_error"].assert_called_once_with(
            "validation_error",
            "Well this is odd...",
            topic=msg.topic,
            failed_check="whodis",
            offending_key="<root>",
        )

    def test_schema_mismatch_in_nested_key(self, om_mocks):
        om_mocks["validate_message"].side_effect = ValidationError(
            "'x' is not of type 'number'",
            validator="type",
            path=["config", "pid", 0, "k_p"],
            schema={},
            instance={},
        )

        msg = self.run_on_message(om_mocks, "this/is/fine", '{"config": "..."}')

        om_mocks["print_and_publish_error"].assert_called_once_with(
            "validation_error",
            "'x' is not of type 'number'",
            topic=msg.topic,
            failed_check="type",
            offending_key="config.pid.0.k_p",
        )

    def test_unexpected_exception(self, om_mocks, message_bus, capsys):
        om_mocks["validate_message"].side_effect = Exception("Unexpected error")

        msg = self.run_on_message(
            om_mocks, "this/is/odd", '{"an": "unexpected", "exception": "ocurred"}'
        )

        om_mocks["print_and_publish_error"].assert_not_called()
        message = f"Could not validate message on {msg.topic}: Unexpected error"
        assert capsys.readouterr().out == f"ERROR: {message}\n"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/monitor"
        assert json.loads(messages[0].payload) == {
            "code": "exception",
            "message": message,
        }

        )
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0
