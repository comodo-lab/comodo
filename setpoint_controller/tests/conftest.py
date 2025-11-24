"""Shared pytest fixtures and utilities for setpoint controller tests."""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.pid import PID


class MockMessage:
    """
    Mock MQTT message object.
    """

    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else payload


def parse_message_args(args):
    """
    Parses the arguments received by an mqtt client (i.e. [topic, payload]),
    and returns the topic and loaded JSON message (a dict).
    Example usage:
        topic, message = parse_message_args(mock_mqtt_publisher.publish.call_args[0])
    """
    topic, payload = args
    return topic, json.loads(payload)


@pytest.fixture(autouse=True)
def mock_mqtt_publisher():
    """Mock the MQTTPublisher singleton."""
    with patch("setpoint_controller.MQTTPublisher") as mock_publisher_class:
        mock_instance = MagicMock()
        mock_publisher_class.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_pid():
    """Create a basic PID controller with standard test parameters."""
    return PID(
        id="test_pid",
        sensor="mock_sensor",
        actuator="mock_actuator",
    )
