"""Mock implementation of ComodoConfig for testing."""

import pytest
from unittest.mock import MagicMock

from utils.comodo_config import ComodoConfig
from utils.tests.mocks.mock_comodo_yaml import mock_comodo_yaml


@pytest.fixture
def mock_comodo_config(mock_comodo_yaml):
    """Returns a mock comodo config object."""
    mock_config = MagicMock(spec=ComodoConfig)
    mock_config.path = "/app/comodo.yaml"
    mock_config.raw = mock_comodo_yaml
    mock_config.globals = {
        "heartbeat_interval": 1,
        "watchdog_interval": 1,
        "watchdog_timeout": 5,
        "instrument_setup_wait": 10,
    }

    mock_config.instruments = {
        "furnace": {
            "firmware": "carbolite_gero.tg3",
            "address": "192.168.111.222",
            "simulate": True,
            "variables": {
                "temperature": {
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                        "min": 0,
                        "max": 1000,
                        "unit": "C",
                        "default_setpoint": 25,
                    },
                    "actuator": {
                        "type": "float",
                        "min": 0,
                        "max": 1000,
                        "unit": "C",
                        "safe_stop_setpoint": 0,
                        "tolerance": 1,
                    },
                },
            },
        },
        "pressure": {
            "firmware": "pfeiffer.mpt200",
            "address": "/dev/ttyUSB0",
            "simulate": True,
            "variables": {
                "pressure": {
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                        "min": 0,
                        "max": 10,
                        "unit": "bar",
                        "default_setpoint": 1,
                    },
                },
            },
        },
        "mass_flow": {
            "firmware": "bronkhorst.el_flow_select",
            "address": "/dev/ttyUSB2",
            "simulate": True,
            "variables": {
                "mass_flow": {
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                        "min": 0,
                        "max": 100,
                        "unit": "\\%",
                    },
                    "actuator": {
                        "type": "float",
                        "min": 0,
                        "max": 100,
                        "unit": "\\%",
                        "safe_stop_setpoint": 0,
                        "tolerance": 1,
                    },
                    "setpoint_controller": {
                        "external_sensor": "pressure/pressure",
                        "K_P": 10.0,
                        "K_I": 1.0,
                        "K_D": 0.1,
                        "K_AW": 0.05,
                        "K_DF": 0.01,
                    },
                },
            },
        },
    }

    mock_config.sensors = {
        "furnace/temperature": {
            "interval": 1,
            "max": 1000,
            "min": 0,
            "type": "float",
            "unit": "C",
            "default_setpoint": 25,
        },
        "mass_flow/mass_flow": {
            "interval": 1,
            "max": 100,
            "min": 0,
            "type": "float",
            "unit": "\\%",
        },
        "pressure/pressure": {
            "interval": 1,
            "max": 10,
            "min": 0,
            "type": "float",
            "unit": "bar",
            "default_setpoint": 1,
        },
    }
    mock_config.actuators = {
        "furnace/temperature": {
            "driving_sensor": "furnace/temperature",
            "type": "float",
            "min": 0,
            "max": 1000,
            "unit": "C",
            "safe_stop_setpoint": 0,
            "tolerance": 1,
        },
        "mass_flow/mass_flow": {
            "driving_sensor": "pressure/pressure",
            "type": "float",
            "min": 0,
            "max": 100,
            "unit": "\\%",
            "safe_stop_setpoint": 0,
            "tolerance": 1,
        },
    }
    mock_config.spcs = {
        "pressure-pressure--mass_flow-mass_flow": {
            "actuator": "mass_flow/mass_flow",
            "external_sensor": "pressure/pressure",
            "K_P": 10.0,
            "K_I": 1.0,
            "K_D": 0.1,
            "K_AW": 0.05,
            "K_DF": 0.01,
        },
    }

    mock_config.get_expected_heartbeat.return_value = {
        "firmware": "test_firmware",
        "device_address": "1.2.3.4",
        "simulate": True,
        "variables": ["V_A", "V_B"],
    }

    mock_config.get_default_experiment.return_value = [
        {
            "time": 0,
            "furnace/temperature": 25,
            "furnace/temperature_profile": "linear",
            "pressure/pressure": 1,
            "pressure/pressure_profile": "linear",
        }
    ]

    return mock_config
