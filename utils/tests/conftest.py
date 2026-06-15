import pytest

from utils.tests.mocks.mock_mqtt_clients import (
    pytest_runtest_makereport,
    MockMessage,
    InMemoryMessageBus,
    message_bus,
    mqtt_mocks,
    parse_message_args,
)


@pytest.fixture
def mock_topic_map():
    return {
        "error/message/malformed": {
            "name": "errorMalformed",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error", "error_message"],
                "properties": {
                    "topic": {"type": "string"},
                    "error": {"type": "string", "enum": ["invalid_json"]},
                    "error_message": {"type": "string"},
                },
            },
        },
        "error/message/invalid": {
            "name": "errorInvalid",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error", "message"],
                "properties": {
                    "topic": {"type": "string"},
                    "channel": {"type": "string"},
                    "error": {"type": "string", "enum": ["validation_error"]},
                    "path": {"type": "array", "items": {"type": "string"}},
                    "message": {"type": "string"},
                },
            },
        },
        "error/message/unexpected": {
            "name": "errorUnexpected",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error"],
                "properties": {
                    "topic": {"type": "string"},
                    "error": {"type": "string", "enum": ["unexpected_topic"]},
                },
            },
        },
    }
