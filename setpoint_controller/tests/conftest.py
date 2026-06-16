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
            "sensor_instrument": "I1",
            "sensor_variable": "A",
            "actuator_instrument": "I2",
            "actuator_variable": "B",
            "heartbeat_interval": 1,
        }
        d_kwargs.update(kwargs)
        d_kwargs.update(
            {
                "spc_id": f"{d_kwargs['sensor_instrument']}-{d_kwargs['sensor_variable']}--{d_kwargs['actuator_instrument']}-{d_kwargs['actuator_variable']}"
            }
        )

        # Create and return SetpointController instance
        return SetpointController(**d_kwargs)

    return _create


@pytest.fixture
def mock_spc(mock_spc_status, mock_pid):
    """SetpointController with default parameters."""
    spc = MagicMock(spec=SetpointController)
    spc.sensor_instrument = "I1"
    spc.sensor_variable = "A"
    spc.actuator_instrument = "I2"
    spc.actuator_variable = "B"
    spc.spc_id = "I1-A--I2-B"
    spc.pid = mock_pid
    spc.status = mock_spc_status
    spc.start_heartbeat_loop = MagicMock()
    spc.publish_heartbeat = MagicMock()
    return spc


@pytest.fixture
def mock_spc_status():
    """SetpointController.Status with default parameters."""
    status = MagicMock(spec=SetpointController.Status)

    status.enabled = True
    status.state = "idle"
    status.sensor_setpoint = None
    status.sensor_measurement = None
    status.actuator_setpoint = None
    status.experiment_id = None

    def get_status_as_dict():
        return {
            "status": {
                "state": status.state,
                "enabled": status.enabled,
                "sensor_measurement": status.sensor_measurement,
                "actuator_setpoint": status.actuator_setpoint,
                "experiment_id": status.experiment_id,
            },
            "setpoints": {
                "sensor_setpoint": status.sensor_setpoint,
            },
        }

    status.as_dict.side_effect = get_status_as_dict

    return status


@pytest.fixture
def mock_pid():
    """PID with default parameters."""
    pid = MagicMock(spec=PID)
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
def rand_pid():
    """PID with random parameters."""
    return PID(
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
