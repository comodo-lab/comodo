"""
Tests of the firmware compose file template (templates/compose.firmware.yaml.j2).
They render it with the jinja2 CLI, as compose-gen does (see compose.gen.yaml), with the same versions.
"""

import json
import subprocess
from pathlib import Path

import pytest
import yaml

import src.config as config


@pytest.fixture
def render(tmp_path):
    """
    Renders the template with a comodo.yaml with the given instruments, as compose-gen does,
    and returns the parsed compose file.
    """

    def _render(instruments):
        comodo_config = {
            "global": {
                "heartbeat": {"interval": 2},
                "experiment_monitoring": {"max_missed_heartbeats": 4},
            },
            "instruments": instruments,
        }
        config_path = tmp_path / "comodo.yaml"
        # In the given order, as written in a comodo.yaml
        config_path.write_text(yaml.safe_dump(comodo_config, sort_keys=False))
        template = Path(__file__).parents[2] / "templates/compose.firmware.yaml.j2"
        result = subprocess.run(
            ["jinja2", str(template), str(config_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return yaml.safe_load(result.stdout)

    return _render


def env_json(service, key):
    """
    The JSON values (e.g. DEFAULT_SETPOINTS) are rendered as strings, as the firmware reads them from its env.
    """
    return json.loads(service["environment"][key])


class TestInstrumentService:
    def test_instrument_environment(self, render):
        compose = render(
            {
                "furnace": {
                    "firmware": "carbolite_gero.tg3",
                    "address": "192.168.1.10",
                    "device_id": 3,
                    "simulate": True,
                    "variables": {
                        "temperature": {
                            "default_setpoint": 25,
                            "sensor": {"interval": 1},
                            "actuator": {"safe_stop_setpoint": 0},
                        },
                    },
                },
            }
        )
        env = compose["services"]["furnace"]["environment"]
        assert env == {
            "MQTT_HOST": "${MQTT_HOST:-rabbitmq}",
            "MQTT_USER": "${MQTT_USER}",
            "MQTT_PASS": "${MQTT_PASS}",
            "INSTRUMENT_NAME": "furnace",
            "FIRMWARE": "carbolite_gero.tg3",
            "ADDRESS": "192.168.1.10",
            "DEVICE_ID": "3",
            "SIMULATE": "true",
            "ACTIVE_VARIABLES": '["temperature"]',
            "DEFAULT_SETPOINTS": '{"temperature": 25}',
            "EXTERNAL_ACTUATORS": "null",
            "SAFE_STOP_SETPOINTS": '{"temperature": 0}',
            "MEASUREMENT_INTERVALS": '{"temperature": 1}',
            "HEARTBEAT_INTERVAL": 2.0,
            "MAX_MISSED_HEARTBEATS": 4,
        }

    def test_every_variable_of_an_instrument(self, render):
        compose = render(
            {
                "transformer": {
                    "firmware": "adafruit.ads1115",
                    "address": "/dev/i2c-1",
                    "variables": {
                        "current": {
                            "default_setpoint": 1,
                            "sensor": {"interval": 1},
                            "actuator": {"safe_stop_setpoint": 0},
                        },
                        "voltage": {
                            "default_setpoint": 2,
                            "sensor": {"interval": 3},
                            "actuator": {"safe_stop_setpoint": 4},
                        },
                        "power": {"sensor": {"interval": 5}},
                    },
                },
            }
        )
        service = compose["services"]["transformer"]
        assert env_json(service, "ACTIVE_VARIABLES") == ["current", "voltage", "power"]
        assert env_json(service, "DEFAULT_SETPOINTS") == {"current": 1, "voltage": 2}
        assert env_json(service, "SAFE_STOP_SETPOINTS") == {"current": 0, "voltage": 4}
        assert env_json(service, "MEASUREMENT_INTERVALS") == {
            "current": 1,
            "voltage": 3,
            "power": 5,
        }

    def test_settings_not_given(self, render):
        compose = render(
            {
                "probe": {
                    "firmware": "pfeiffer.mpt200",
                    "address": "192.168.1.11",
                    "variables": {"pressure": {}},
                },
            }
        )
        env = compose["services"]["probe"]["environment"]
        assert env["SIMULATE"] == "false"
        assert env["DEVICE_ID"] == ""
        for key in [
            "DEFAULT_SETPOINTS",
            "EXTERNAL_ACTUATORS",
            "SAFE_STOP_SETPOINTS",
            "MEASUREMENT_INTERVALS",
        ]:
            assert env[key] == "null"

    def test_device_address_is_mapped(self, render):
        compose = render(
            {
                "serial": {
                    "firmware": "esi.hp1410b",
                    "address": "/dev/ttyUSB0",
                    "variables": {"pressure": {}},
                },
                "network": {
                    "firmware": "carbolite_gero.tg3",
                    "address": "192.168.1.10",
                    "variables": {"temperature": {}},
                },
            }
        )
        serial = compose["services"]["serial"]
        assert serial["devices"] == ["/dev/ttyUSB0:/dev/ttyUSB0"]
        assert serial["privileged"] is True
        network = compose["services"]["network"]
        assert "devices" not in network
        assert "privileged" not in network


class TestSetpointController:
    def test_setpoint_controller(self, render):
        compose = render(
            {
                "pressure": {
                    "firmware": "esi.hp1410b",
                    "address": "/dev/ttyUSB0",
                    "variables": {
                        "pressure": {
                            "default_setpoint": 1,
                            "sensor": {"interval": 1},
                        },
                    },
                },
                "mass_flow": {
                    "firmware": "bronkhorst.el_flow_select",
                    "address": "/dev/ttyUSB2",
                    "variables": {
                        "mass_flow": {
                            "min": 0,
                            "max": 100,
                            "sensor": {"interval": 1},
                            "actuator": {"safe_stop_setpoint": 0},
                            "setpoint_controller": {
                                "external_sensor": "pressure/pressure",
                                "K_P": 10.0,
                                "K_I": 1.0,
                            },
                        },
                    },
                },
            }
        )
        services = compose["services"]
        # The driven sensor's instrument knows which actuator drives it, to simulate it
        assert env_json(services["pressure"], "EXTERNAL_ACTUATORS") == {
            "pressure": "mass_flow/mass_flow"
        }
        assert services["mass_flow"]["environment"]["EXTERNAL_ACTUATORS"] == "null"
        assert services["spc-mass_flow-mass_flow"]["environment"] == {
            "MQTT_HOST": "${MQTT_HOST:-rabbitmq}",
            "MQTT_USER": "${MQTT_USER}",
            "MQTT_PASS": "${MQTT_PASS}",
            "HEARTBEAT_INTERVAL": 2.0,
            "SENSOR": "pressure/pressure",
            "DEFAULT_SETPOINT": 1,
            "ACTUATOR": "mass_flow/mass_flow",
            "K_P": 10.0,
            "K_I": 1.0,
            "OUT_MIN": 0,
            "OUT_MAX": 100,
        }

    def test_actuator_limits_override_variable_limits(self, render):
        compose = render(
            {
                "furnace": {
                    "firmware": "carbolite_gero.tg3",
                    "address": "192.168.1.10",
                    "variables": {
                        "temperature": {"default_setpoint": 25},
                        "power": {
                            "min": 0,
                            "max": 100,
                            "actuator": {"min": 10, "max": 90},
                            "setpoint_controller": {
                                "external_sensor": "furnace/temperature"
                            },
                        },
                    },
                },
            }
        )
        env = compose["services"]["spc-furnace-power"]["environment"]
        assert env["OUT_MIN"] == 10
        assert env["OUT_MAX"] == 90

    def test_no_setpoint_controllers(self, render):
        compose = render(
            {
                "furnace": {
                    "firmware": "carbolite_gero.tg3",
                    "address": "192.168.1.10",
                    "variables": {"temperature": {}},
                },
            }
        )
        assert set(compose["services"]) == {"mqtt-probe-firmware", "furnace"}


class TestFirmwareConfig:
    def test_firmware_loads_the_rendered_environment(self, render, monkeypatch):
        compose = render(
            {
                "pressure": {
                    "firmware": "esi.hp1410b",
                    "address": "/dev/ttyUSB0",
                    "device_id": 2,
                    "simulate": True,
                    "variables": {
                        "pressure": {
                            "default_setpoint": 1,
                            "sensor": {"interval": 1},
                        },
                    },
                },
                "mass_flow": {
                    "firmware": "bronkhorst.el_flow_select",
                    "address": "/dev/ttyUSB2",
                    "variables": {
                        "mass_flow": {
                            "default_setpoint": 0,
                            "sensor": {"interval": 2},
                            "actuator": {"safe_stop_setpoint": 0},
                            "setpoint_controller": {
                                "external_sensor": "pressure/pressure"
                            },
                        },
                    },
                },
            }
        )
        # Docker passes every value of the environment as a string
        for key, value in compose["services"]["pressure"]["environment"].items():
            monkeypatch.setenv(key, str(value))

        loaded = config.load_config()

        assert loaded == {
            **config.DEFAULT_CONFIG,
            # Not interpolated, as docker compose would
            "MQTT_HOST": "${MQTT_HOST:-rabbitmq}",
            "MQTT_USER": "${MQTT_USER}",
            "MQTT_PASS": "${MQTT_PASS}",
            "INSTRUMENT_NAME": "pressure",
            "FIRMWARE": "esi.hp1410b",
            "ADDRESS": "/dev/ttyUSB0",
            "DEVICE_ID": "2",
            "SIMULATE": True,
            "ACTIVE_VARIABLES": ["pressure"],
            "DEFAULT_SETPOINTS": {"pressure": 1},
            "EXTERNAL_ACTUATORS": {"pressure": "mass_flow/mass_flow"},
            "SAFE_STOP_SETPOINTS": {},
            "MEASUREMENT_INTERVALS": {"pressure": 1},
            "HEARTBEAT_INTERVAL": 2.0,
            "MAX_MISSED_HEARTBEATS": 4,
        }
