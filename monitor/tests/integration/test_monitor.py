"""
Integration tests for the monitor.

These start the monitor (monitor()), and publish messages on an in-memory message bus,
which the monitor validates against the real MQTT schema (/schemas/mqtt_schema.yaml).
MQTT communication is replaced with the message bus, so no broker is needed.
"""

import json
import time

import pytest
from unittest.mock import AsyncMock, patch

import monitor
from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    monitor_env,
    run_to_completion,
)


@pytest.fixture
def running_monitor(mqtt_mocks, monitor_env):
    """
    Starts the monitor, without waiting forever: asyncio.Event is patched, so the monitor returns once set up.
    The monitor's MQTT client stays subscribed to the message bus, so messages published on it are monitored.
    """
    with patch("monitor.asyncio.Event") as mock_event:
        mock_event.return_value.wait = AsyncMock()
        run_to_completion(monitor.monitor())
    return mqtt_mocks["client_instance"]("mqtt-monitor")


def wait_for_messages(message_bus, topic, count=1, timeout=2.0):
    """
    Waits until at least `count` messages are published on `topic`, and returns them, decoded.
    The message bus delivers messages in separate threads, so the monitor's response is not immediate.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        messages = message_bus.get_messages(topic, decoded=True)
        if len(messages) >= count:
            return messages
        time.sleep(0.01)
    return message_bus.get_messages(topic, decoded=True)


def error_payloads(messages):
    """Returns the decoded JSON payloads of the given messages."""
    return [json.loads(m.payload) for m in messages]


def test_valid_message_is_not_reported(message_bus, running_monitor):
    message_bus.publish("mqtt-probe/test", json.dumps({"uid": 1}))

    time.sleep(0.2)
    assert message_bus.get_messages("error/#") == []


def test_unexpected_topic_is_reported(message_bus, running_monitor):
    message_bus.publish("not/in/the/schema", json.dumps({"uid": 1}))

    errors = error_payloads(wait_for_messages(message_bus, "error/message"))
    assert errors == [
        {"code": "unexpected_topic", "message": "Unexpected topic: not/in/the/schema"}
    ]


def test_invalid_json_is_reported(message_bus, running_monitor):
    message_bus.publish("mqtt-probe/test", "this is not json")

    errors = error_payloads(wait_for_messages(message_bus, "error/message"))
    assert len(errors) == 1
    assert errors[0]["code"] == "invalid_json"
    assert errors[0]["topic"] == "mqtt-probe/test"


def test_payload_not_utf8_is_reported_as_invalid_json(message_bus, running_monitor):
    message_bus.publish(
        "mqtt-probe/test", MockMessage(topic="mqtt-probe/test", payload=b"\x80abc")
    )

    errors = error_payloads(wait_for_messages(message_bus, "error/message"))
    assert len(errors) == 1
    assert errors[0]["code"] == "invalid_json"
    assert errors[0]["topic"] == "mqtt-probe/test"


def test_schema_mismatch_is_reported_with_offending_key(message_bus, running_monitor):
    message_bus.publish("mqtt-probe/test", json.dumps({"uid": "not a number"}))

    errors = error_payloads(wait_for_messages(message_bus, "error/message"))
    assert len(errors) == 1
    assert errors[0]["code"] == "validation_error"
    assert errors[0]["topic"] == "mqtt-probe/test"
    assert errors[0]["failed_check"] == "type"
    assert errors[0]["offending_key"] == "uid"


def test_own_error_messages_are_valid(message_bus, running_monitor):
    """
    The monitor also receives the errors it publishes (it subscribes to all topics).
    They must be valid themselves, or each error would be reported again, endlessly.
    """
    message_bus.publish("not/in/the/schema", "{}")
    message_bus.publish("mqtt-probe/test", "this is not json")
    message_bus.publish("mqtt-probe/test", json.dumps({"uid": "not a number"}))

    wait_for_messages(message_bus, "error/message", count=3)
    time.sleep(0.2)
    errors = error_payloads(message_bus.get_messages("error/message", decoded=True))
    assert sorted(e["code"] for e in errors) == [
        "invalid_json",
        "unexpected_topic",
        "validation_error",
    ]
