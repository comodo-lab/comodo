"""Shared pytest fixtures and utilities for ui tests."""

import pytest


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Minimal comodo.yaml with one sensor-only and one actuator variable."""
    content = """\
global:
  heartbeat:
    interval: 1s
  watchdog:
    timeout: 5s
    interval: 1s

instruments:
  test_sensor:
    firmware: test/sensor
    address: "localhost:1234"
    variables:
      reading:
        measurement:
          interval: 1s
        sensor:
          type: float
          min: 0
          max: 100
          unit: V
  test_actuator:
    firmware: test/actuator
    address: "localhost:5678"
    variables:
      output:
        measurement:
          interval: 1s
        sensor:
          type: float
          min: 0
          max: 50
          unit: mA
        actuator:
          type: float
          min: 5
          max: 45
          unit: mA
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
    interval: 1s
  watchdog:
    timeout: 5s
    interval: 1s

instruments:
  pressure:
    firmware: test/pressure
    address: "localhost:1111"
    variables:
      value:
        measurement:
          interval: 1s
        sensor:
          type: float
          min: 0
          max: 10
          unit: bar
  flow:
    firmware: test/flow
    address: "localhost:2222"
    variables:
      rate:
        measurement:
          interval: 1s
        sensor:
          type: float
          min: 0
          max: 100
          unit: "%"
        actuator:
          type: float
          min: 0
          max: 100
          unit: "%"
        setpoint_controller:
          external_sensor: pressure.value
          P: 10.0
          I: 1.0
          D: 0.1
"""
    f = tmp_path / "comodo.yaml"
    f.write_text(content)
    return str(f)
