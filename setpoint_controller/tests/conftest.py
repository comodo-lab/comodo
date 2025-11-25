"""Shared pytest fixtures and utilities for setpoint controller tests."""

import json
import pytest
from unittest.mock import patch, MagicMock
from random import uniform as rand

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


def base_pid(kwargs=None):
    """
    Create a PID controller with default values for id, sensor and actuator.
    Allows overriding any of these or other PID parameters via the kwargs dict.

    Inputs:
        kwargs: dict of parameters to override defaults
    Returns:
        PID instance
    """
    d_kwargs = {"id": "test_pid", "sensor": "mock_sensor", "actuator": "mock_actuator"}

    if kwargs is not None:
        d_kwargs.update(kwargs)

    # Create and return PID instance
    return PID(**d_kwargs)


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    return base_pid()


@pytest.fixture
def rand_pid():
    """PID with random parameters."""
    return base_pid(
        {
            "k_p": rand(0.01, 10.0),
            "k_i": rand(0.01, 10.0),
            "k_d": rand(0.01, 10.0),
            "k_aw": rand(0.01, 10.0),
            "k_df": rand(0.01, 10.0),
            "max": rand(0.01, 10.0),
            "min": rand(0.01, 10.0),
            "max_rate": rand(0.01, 10.0),
        }
    )
