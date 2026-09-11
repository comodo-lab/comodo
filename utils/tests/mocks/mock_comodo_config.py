"""Mock implementation of ComodoConfig for testing."""

import pytest
from unittest.mock import MagicMock

from utils.comodo_config import ComodoConfig
from utils.tests.mocks.mock_comodo_yaml_dict import mock_comodo_yaml_dict


@pytest.fixture
def mock_comodo_config(mock_comodo_yaml_dict):
    """Returns a mock comodo config object."""
    mock_config = MagicMock(spec=ComodoConfig)
    mock_config.path = "/app/comodo.yaml"
    mock_config.raw = mock_comodo_yaml_dict
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
                    "min": 0,
                    "max": 1000,
                    "unit": "C",
                    "default_setpoint": 25,
                    "tolerance": 1,
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                    },
                    "actuator": {
                        "type": "float",
                        "safe_stop_setpoint": 0,
                    },
                }
            },
        },
        "pressure": {
            "firmware": "pfeiffer.mpt200",
            "address": "/dev/ttyUSB0",
            "simulate": True,
            "variables": {
                "pressure": {
                    "min": 1,
                    "max": 200,
                    "unit": "bar",
                    "tolerance": 0.5,
                    "default_setpoint": 1,
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                    },
                }
            },
        },
        "mass_flow": {
            "firmware": "bronkhorst.el_flow_select",
            "address": "/dev/ttyUSB2",
            "simulate": True,
            "variables": {
                "mass_flow": {
                    "min": 0,
                    "max": 100,
                    "unit": "\\%",
                    "sensor": {
                        "interval": 1,
                        "type": "float",
                    },
                    "actuator": {
                        "type": "float",
                        "safe_stop_setpoint": 0,
                    },
                    "setpoint_controller": {
                        "external_sensor": "pressure/pressure",
                        "K_P": 10.0,
                        "K_I": 1.0,
                        "K_D": 0.1,
                        "K_AW": 0.05,
                        "K_DF": 0.01,
                    },
                }
            },
        },
    }

    mock_config.sensors = {
        "furnace/temperature": {
            "min": 0,
            "max": 1000,
            "unit": "C",
            "tolerance": 1,
            "default_setpoint": 25,
            "interval": 1,
            "type": "float",
        },
        "mass_flow/mass_flow": {
            "min": 0,
            "max": 100,
            "unit": "\\%",
            "interval": 1,
            "type": "float",
        },
        "pressure/pressure": {
            "min": 1,
            "max": 200,
            "unit": "bar",
            "default_setpoint": 1,
            "tolerance": 0.5,
            "interval": 1,
            "type": "float",
        },
    }
    mock_config.actuators = {
        "furnace/temperature": {
            "driving_sensor": "furnace/temperature",
            "type": "float",
            "safe_stop_setpoint": 0,
        },
        "mass_flow/mass_flow": {
            "driving_sensor": "pressure/pressure",
            "type": "float",
            "safe_stop_setpoint": 0,
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
        "address": "1.2.3.4",
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
