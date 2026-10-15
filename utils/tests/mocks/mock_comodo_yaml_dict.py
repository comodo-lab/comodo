import pytest


@pytest.fixture
def mock_comodo_yaml_dict():
    return {
        "global": {
            "heartbeat": {"interval": 1},
            "instrument_setup": {"wait": 10},
            "watchdog": {"timeout": 5, "interval": 1},
            "experiment_monitoring": {
                "max_missed_heartbeats": 3,
                "bad_state_tolerance": 7,
                "missed_setpoint_tolerance": 7,
            },
        },
        "instruments": {
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
        },
    }
