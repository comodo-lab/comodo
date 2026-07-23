import yaml
import pytest


@pytest.fixture
def mock_comodo_yaml():
    return yaml.safe_load("""
global:
  heartbeat:
    interval: 1
  instrument_setup:
    wait: 10
  watchdog:
    timeout: 5
    interval: 1

instruments:
  furnace:
    firmware: carbolite_gero.tg3
    address: "192.168.111.222"
    simulate: true
    variables:
      temperature:
        sensor:
          interval: 1
          type: float
          min: 0
          max: 1000
          unit: C
          default_setpoint: 25
        actuator:
          type: float
          min: 0
          max: 1000
          unit: C
          safe_stop_setpoint: 0
          tolerance: 1
  pressure:
    firmware: pfeiffer.mpt200
    address: "/dev/ttyUSB0"
    simulate: true
    variables:
      pressure:
        sensor:
          interval: 1
          type: float
          min: 0
          max: 10
          unit: bar
          default_setpoint: 1
  mass_flow:
    firmware: bronkhorst.el_flow_select
    address: "/dev/ttyUSB2"
    simulate: true
    variables:
      mass_flow:
        sensor:
          interval: 1
          type: float
          min: 0
          max: 100
          unit: \%
        actuator:
          type: float
          min: 0
          max: 100
          unit: \%
          safe_stop_setpoint: 0
          tolerance: 1
        setpoint_controller:
          external_sensor: pressure/pressure
          K_P: 10.0
          K_I: 1.0
          K_D: 0.1
          K_AW: 0.05
          K_DF: 0.01

visualisations:
  temperature_graph:
    title: Temperature
    type: graph
    y_values:
      - temperature
  pressure_graph:
      title: Pressure
      type: graph
      y_values:
        - pressure
  mass_flow_gauge:
    title: Mass Flow
    type: gauge
    value:
      - mass_flow
""")
