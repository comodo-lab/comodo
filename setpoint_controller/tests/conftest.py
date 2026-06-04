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
            "sensor_name": "I1",
            "sensor_var": "A",
            "actuator_name": "I2",
            "actuator_var": "B",
            "heartbeat_interval": 1,
            "spc_id": "I1/A__I2/B",
            "topic_id": "spc-I1.A-I2.B",
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
    spc.status = {
        "state": "idle",
        "setpoints": {},
        "config": {
            "mock": "config",
            "experiment_id": None,
            "sensor": "I1/A",
            "actuator": "I2/B",
            "active": True,
        },
    }
    spc.sensor_name = "I1"
    spc.sensor_var = "A"
    spc.actuator_name = "I2"
    spc.actuator_var = "B"
    spc.spc_id = "I1/A__I2/B"
    spc.topic_id = "spc-I1.A-I2.B"
    spc.pid = mock_pid
    spc.publish_heartbeat = MagicMock()
    return spc


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    pid = MagicMock(spec=PID)
    pid.id = "I1/A__I2/B"
    pid.sensor = "I1/A"
    pid.actuator = "I2/B"
    pid.k_p = 1.0
    pid.k_i = 0.5
    pid.setpoint = None
    pid.configurable = ["k_p", "k_i"]
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
