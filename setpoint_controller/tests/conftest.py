"""Shared pytest fixtures and utilities for setpoint controller tests."""

import pytest
from unittest.mock import patch, MagicMock
import json
from random import uniform as rand

from utils.tests.mocks.mock_mqtt_clients import (
    pytest_runtest_makereport,
    MockMessage,
    InMemoryMessageBus,
    message_bus,
    mock_MQTTClient,
    mock_MQTTPublisher,
    mock_load_message,
    parse_message_args,
)

from setpoint_controller import SetpointController
from src.pid import PID


def base_SPC(**kwargs):
    """
    Create a SetpointController with default values for mqtt and sensor/actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        SetpointController instance
    """
    d_kwargs = {
        "mqtt_host": "test_host",
        "mqtt_user": "test_user",
        "mqtt_pass": "test_pass",
        "sensor": "test_sensor",
        "actuator": "test_actuator",
        "sensor": "A",
        "actuator": "B",
        "heartbeat_interval": 1,
    }
    d_kwargs.update(kwargs)

    # Create and return SetpointController instance
    return SetpointController(**d_kwargs)


def base_PID(**kwargs):
    """
    Create a PID controller with default values for id, sensor and actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        PID instance
    """
    d_kwargs = {"id": "test_pid", "sensor": "mock_sensor", "actuator": "mock_actuator"}

    d_kwargs.update(kwargs)

    # Create and return PID instance
    return PID(**d_kwargs)


@pytest.fixture
def mock_spc():
    """SetpointController with default parameters."""
    spc = MagicMock(spec=SetpointController)
    spc.state = {
        "name": f"pid_A__B",
        "status": "no_setpoint",
        "setpoint": None,
        "config": {"mock": "config"},
    }
    spc.pid = base_PID()
    return spc


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    return base_PID()


@pytest.fixture
def rand_pid():
    """PID with random parameters."""
    return base_PID(
        k_p=rand(0.01, 10.0),
        k_i=rand(0.01, 10.0),
        k_d=rand(0.01, 10.0),
        k_aw=rand(0.01, 10.0),
        k_df=rand(0.01, 10.0),
        max=rand(0.01, 10.0),
        min=rand(0.01, 10.0),
        max_rate=rand(0.01, 10.0),
    )


@pytest.fixture
def mock_pid_time():
    """Mock time.time() only within PID.step for deterministic testing."""
    mock_time = [0.0]

    def increment_time():
        result = mock_time[0]
        mock_time[0] += 1  # 1 second per call
        return result

    with patch("src.pid.PID.now", side_effect=increment_time):
        yield mock_time
