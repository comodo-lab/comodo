"""Shared pytest fixtures and utilities for ui tests."""

import pytest

GLOBALS = """\
global:
  heartbeat:
    interval: 1
  instrument_setup:
    wait: 10
  experiment_monitoring:
    max_missed_heartbeats: 3
    bad_state_tolerance: 7
    missed_setpoint_tolerance: 7
  watchdog:
    timeout: 5
    interval: 1
"""


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Minimal comodo.yaml with one sensor-only and one actuator variable."""
    content = GLOBALS + """
instruments:
  test_sensor:
    firmware: test.sensor
    address: "localhost:1234"
    variables:
      reading:
        min: 0
        max: 10
        unit: X
        sensor:
          interval: 1
          type: float
  test_actuator:
    firmware: test.actuator
    address: "localhost:5678"
    variables:
      output:
        min: 0
        max: 10
        unit: X
        tolerance: 0.5
        default_setpoint: 5
        sensor:
          interval: 1
          type: float
        actuator:
          type: float
          safe_stop_setpoint: 0
"""
    f = tmp_path / "comodo.yaml"
    f.write_text(content)
    return str(f)


@pytest.fixture
def sample_config_with_pid(tmp_path):
    """comodo.yaml with an actuator-only variable driven by a setpoint controller."""
    content = GLOBALS + """
instruments:
  test_sensor:
    firmware: test.sensor
    address: "localhost:1111"
    variables:
      value:
        min: 0
        max: 10
        unit: X
        tolerance: 0.5
        default_setpoint: 2
        sensor:
          interval: 1
          type: float
  test_spc:
    firmware: test.spc
    address: "localhost:2222"
    variables:
      output:
        min: 0
        max: 100
        unit: X
        actuator:
          type: float
          safe_stop_setpoint: 0
        setpoint_controller:
          external_sensor: test_sensor/value
          K_P: 10.0
          K_I: 1.0
          K_D: 0.1
          K_AW: 0.05
          K_DF: 0.01
"""
    f = tmp_path / "comodo.yaml"
    f.write_text(content)
    return str(f)
