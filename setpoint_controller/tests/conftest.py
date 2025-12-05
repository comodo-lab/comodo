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
    mqtt_mocks,
    parse_message_args,
)

from setpoint_controller import SetpointController
from src.pid import PID


@pytest.fixture
def base_SPC():
    """
    Create a SetpointController with default values for mqtt and sensor/actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        SetpointController instance
    """

    def _create(**kwargs):
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

    return _create


@pytest.fixture
def base_PID(**kwargs):
    """
    Create a PID controller with default values for id, sensor and actuator.
    Allows overriding any of these via kwargs.

    Inputs:
        **kwargs: keyword arguments to override defaults
    Returns:
        PID instance
    """

    def _create(**kwargs):
        d_kwargs = {
            "id": "test_pid",
            "sensor": "mock_sensor",
            "actuator": "mock_actuator",
        }

        d_kwargs.update(kwargs)

        # Create and return PID instance
        return PID(**d_kwargs)

    return _create


@pytest.fixture
def mock_spc(mock_pid):
    """SetpointController with default parameters."""
    spc = MagicMock(spec=SetpointController)
    spc.state = {
        "name": f"pid_A__B",
        "status": "no_setpoint",
        "setpoint": None,
        "config": {"mock": "config"},
    }
    spc.start_heartbeat_loop = MagicMock()
    spc.pid = mock_pid
    return spc


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    pid = MagicMock(spec=PID)
    pid.id = "pid/mock_sensor__mock_actuator"
    pid.sensor = "mock_sensor"
    pid.actuator = "mock_actuator"
    pid.k_p = 1.0
    pid.k_i = 0.5
    pid.setpoint = None
    pid.configurable = ["mock", "configurable", "params"]
    pid.get_state.return_value = {"mock": "state"}
    pid.step = MagicMock(return_value=5.0)

    def get_config_impl():
        return {
            "k_p": pid.k_p,
            "k_i": pid.k_i,
        }

    pid.get_config.side_effect = get_config_impl
    return pid


@pytest.fixture
def rand_pid(base_PID):
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
