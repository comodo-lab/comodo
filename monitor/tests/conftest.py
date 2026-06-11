"""Shared pytest fixtures for monitor tests."""

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
    """Fixture that returns a topic map matching the current messageSpec.yaml structure."""
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string"},
            "message": {"type": "string"},
        },
    }
    return {
        "error/message/malformed": {
            "name": "errorMalformed",
            "schema": schema,
        },
        "error/message/invalid": {
            "name": "errorInvalid",
            "schema": schema,
        },
        "error/message/unexpected": {
            "name": "errorUnexpected",
            "schema": schema,
        },
    }
