import json
import pytest

from app import on_message

from utils.tests.mocks.mock_mqtt_clients import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)


@pytest.fixture
def monitor_client(mqtt_mocks, mock_topic_map):
    mqtt_mocks["client_class"](
        id="monitor",
        topics=["#"],
        callback=on_message,
        obj=mock_topic_map,
    )
    return mqtt_mocks["client_instance"]("monitor")


class TestOnMessage:
    def test_valid_message(self, message_bus, monitor_client, mock_topic_map):
        msg = MockMessage(
            topic="error/message/unexpected",
            payload='{"topic": "test", "error": "unexpected_topic"}',
        )
        on_message(monitor_client, msg, mock_topic_map)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0

    def test_unexpected_topic(self, message_bus, monitor_client, mock_topic_map):
        msg = MockMessage(topic="some/unknown/topic", payload='{"a": 1}')
        on_message(monitor_client, msg, mock_topic_map)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/unexpected"

    def test_invalid_json(self, message_bus, monitor_client, mock_topic_map):
        msg = MockMessage(
            topic="error/message/malformed",
            payload="not valid json",
        )
        on_message(monitor_client, msg, mock_topic_map)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/malformed"
        payload = json.loads(messages[0].payload)
        assert payload["error"] == "invalid_json"

    def test_schema_mismatch(self, message_bus, monitor_client, mock_topic_map):
        msg = MockMessage(
            topic="error/message/unexpected",
            payload='{"topic": "test", "error": "unknown_error"}',
        )
        on_message(monitor_client, msg, mock_topic_map)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/message/invalid"
        payload = json.loads(messages[0].payload)
        assert payload["error"] == "validation_error"
