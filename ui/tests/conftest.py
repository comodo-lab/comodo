"""Shared pytest fixtures and utilities for ui tests."""

import pytest


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Minimal comodo.yaml with one sensor-only and one actuator variable."""
    content = """\
global:
  heartbeat:
    interval: 1
  instrument_setup:
    wait: 10
  watchdog:
    timeout: 5
    interval: 1

instruments:
  test_sensor:
    firmware: test/sensor
    address: "localhost:1234"
    variables:
      reading:
        measurement:
          interval: 1
        sensor:
          type: float
          min: 0
          max: 10
          unit: X
  test_actuator:
    firmware: test/actuator
    address: "localhost:5678"
    variables:
      output:
        measurement:
          interval: 1
        sensor:
          type: float
          min: 0
          max: 10
          unit: X
        actuator:
          type: float
          min: 0
          max: 10
          unit: X
"""
    f = tmp_path / "comodo.yaml"
    f.write_text(content)
    return str(f)


@pytest.fixture
def sample_config_with_pid(tmp_path):
    """comodo.yaml with a PID setpoint_controller referencing an external sensor."""
    content = """\
global:
  heartbeat:
    interval: 1
  instrument_setup:
    wait: 10
  watchdog:
    timeout: 5
    interval: 1

instruments:
  test_sensor:
    firmware: test/sensor
    address: "localhost:1111"
    variables:
      value:
        measurement:
          interval: 1
        sensor:
          type: float
          min: 0
          max: 10
          unit: X
  test_spc:
    firmware: test/spc
    address: "localhost:2222"
    variables:
      output:
        measurement:
          interval: 1
        sensor:
          type: float
          min: 0
          max: 10
          unit: X
        actuator:
          type: float
          min: 0
          max: 10
          unit: X
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
