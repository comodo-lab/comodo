"""Shared pytest fixtures and utilities for monitor tests."""

import pytest

from utils.tests.mocks.mock_topic_map import mock_topic_map

from utils.tests.mocks.mock_mqtt_clients import (
    pytest_runtest_makereport,
    MockMessage,
    InMemoryMessageBus,
    message_bus,
    mqtt_mocks,
    parse_message_args,
)
from utils.tests.mocks.mock_mqtt_validator import mqtt_validator_mocks


@pytest.fixture
def monitor_env(monkeypatch):
    """Sets the environment variables read by the monitor, and returns them."""
    env = {
        "MQTT_HOST": "test_host",
        "MQTT_USER": "test_user",
        "MQTT_PASS": "test_pass",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


def run_to_completion(coroutine):
    """
    Runs a coroutine that never suspends (e.g. with everything it awaits mocked) without an event loop,
    and returns its result.
    """
    try:
        coroutine.send(None)
    except StopIteration as stop:
        return stop.value
    coroutine.close()
    raise AssertionError("The coroutine did not run to completion")
