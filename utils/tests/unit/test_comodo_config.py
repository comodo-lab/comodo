import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call

from comodo_config import find_missing_params, ComodoConfig
from tests.conftest import (
    mock_comodo_yaml_dict,
    mock_comodo_config,
)


class TestFindMissingParams:
    def test_none_missing(self):
        base_dict = {"a": {"b": {"c": 1}, "d": {"e": 2, "f": 3}}}
        required_params = ["a.b.c", "a.d.e", "a.d.f"]
        missing = find_missing_params(base_dict, required_params)
        assert missing == None

    def test_one_missing(self):
        base_dict = {"a": {"b": {"c": 1}, "d": {"e": 2}}}
        required_params = ["a.b.c", "a.d.e", "a.d.f"]
        missing = find_missing_params(base_dict, required_params)
        assert missing == "'a.d.f' parameter"

    def test_two_missing(self):
        base_dict = {"a": {"b": {"c": 1}, "d": {}}}
        required_params = ["a.b.c", "a.d.e", "a.d.f"]
        missing = find_missing_params(base_dict, required_params)
        assert missing == "'a.d.e' and 'a.d.f' parameters"

    def test_more_than_two_missing(self):
        base_dict = {"a": {"b": {}, "d": {}}}
        required_params = ["a.b.c", "a.d.e", "a.d.f"]
        missing = find_missing_params(base_dict, required_params)
        assert missing == "'a.b.c', 'a.d.e' and 'a.d.f' parameters"


class TestInit:
    def test_empty(self):
        config = ComodoConfig()
        assert config.path == "/app/comodo.yaml"
        assert config.raw == {}
        assert config.globals == {
            "heartbeat_interval": None,
            "watchdog_interval": None,
            "watchdog_timeout": None,
            "instrument_setup_wait": None,
        }
        assert config.instruments == {}
        assert config.sensors == {}
        assert config.actuators == {}
        assert config.spcs == {}

    def test_with_path(self):
        config = ComodoConfig(path="/path/to/config.yaml")
        assert config.path == "/path/to/config.yaml"
        assert config.raw == {}
        assert config.globals == {
            "heartbeat_interval": None,
            "watchdog_interval": None,
            "watchdog_timeout": None,
            "instrument_setup_wait": None,
        }
        assert config.instruments == {}
        assert config.sensors == {}
        assert config.actuators == {}
        assert config.spcs == {}


class TestLoad:
    @pytest.fixture
    def mocks_for_load(self, mock_comodo_yaml_dict):
        with (
            patch("builtins.open") as mock_open,
            patch("yaml.safe_load") as mock_yaml_load,
            patch(
                "comodo_config.ComodoConfig.populate_globals"
            ) as mock_populate_globals,
            patch(
                "comodo_config.ComodoConfig.populate_instruments"
            ) as mock_populate_instruments,
            patch(
                "comodo_config.ComodoConfig.populate_sensors_actuators_spcs"
            ) as mock_populate_vars,
        ):

            mock_yaml_load.return_value = mock_comodo_yaml_dict

            # Yield mocks for use in tests
            yield {
                "mock_open": mock_open,
                "mock_yaml_load": mock_yaml_load,
                "mock_populate_globals": mock_populate_globals,
                "mock_populate_instruments": mock_populate_instruments,
                "mock_populate_vars": mock_populate_vars,
            }

    def test_full_comodo_yaml(self, mocks_for_load, mock_comodo_yaml_dict):
        config = ComodoConfig()
        result = config.load()

        mocks_for_load["mock_open"].assert_called_once_with("/app/comodo.yaml", "r")
        mocks_for_load["mock_yaml_load"].assert_called_once()
        assert config.raw == mock_comodo_yaml_dict
        mocks_for_load["mock_populate_globals"].assert_called_once()
        mocks_for_load["mock_populate_instruments"].assert_called_once()
        mocks_for_load["mock_populate_vars"].assert_called_once()

        assert result is config


class TestPopulateGlobals:
    @pytest.fixture
    def mocks_for_globals(self, mock_comodo_yaml_dict):
        with patch("comodo_config.find_missing_params") as mock_find_missing_params:
            mock_find_missing_params.return_value = None

            config_with_raw = ComodoConfig()
            config_with_raw.raw = mock_comodo_yaml_dict

            yield {
                "config_with_raw": config_with_raw,
                "mock_find_missing_params": mock_find_missing_params,
            }

    def test_missing_keys(self, mocks_for_globals):
        config = mocks_for_globals["config_with_raw"]
        missing = (
            "'global.watchdog.interval' and 'global.instrument_setup.wait' parameters"
        )
        mock_missing_params = mocks_for_globals["mock_find_missing_params"]
        mock_missing_params.return_value = missing

        with pytest.raises(KeyError) as e:
            config.populate_globals()

        assert mock_missing_params.called_once_with(
            config.raw,
            [
                "global.heartbeat.interval",
                "global.watchdog.interval",
                "global.watchdog.timeout",
                "global.instrument_setup.wait",
            ],
        )
        assert f"Missing {missing} in configuration" in str(e.value)

        assert config.globals == {
            "heartbeat_interval": None,
            "watchdog_interval": None,
            "watchdog_timeout": None,
            "instrument_setup_wait": None,
        }

    def test_with_0_values(self, mocks_for_globals):
        config = mocks_for_globals["config_with_raw"]
        config.raw["global"]["instrument_setup"]["wait"] = 0

        with pytest.raises(ValueError) as e:
            config.populate_globals()

        assert (
            "Global parameter 'instrument_setup_wait' must be a positive number"
            in str(e.value)
        )

    def test_with_watchdog_timeout_less_than_interval(self, mocks_for_globals):
        config = mocks_for_globals["config_with_raw"]
        config.raw["global"]["watchdog"]["interval"] = 5
        config.raw["global"]["watchdog"]["timeout"] = 3

        with pytest.raises(ValueError) as e:
            config.populate_globals()

        assert (
            "Global parameter 'watchdog_timeout' must be greater than 'watchdog_interval'"
            in str(e.value)
        )

    def test_full_comodo_yaml(self, mocks_for_globals):
        config = mocks_for_globals["config_with_raw"]

        config.populate_globals()

        assert config.globals == {
            "heartbeat_interval": 1,
            "watchdog_interval": 1,
            "watchdog_timeout": 5,
            "instrument_setup_wait": 10,
        }


class TestPopulateInstruments:
    @pytest.fixture
    def mocks_for_inst(self, mock_comodo_yaml_dict, mock_comodo_config):
        with patch("comodo_config.find_missing_params") as mock_find_missing_params:
            mock_find_missing_params.return_value = None

            config_with_raw = ComodoConfig()
            config_with_raw.raw = mock_comodo_yaml_dict
            expected_instruments = mock_comodo_config.instruments

            yield {
                "config_with_raw": config_with_raw,
                "mock_find_missing_params": mock_find_missing_params,
                "expected_instruments": expected_instruments,
            }

    def test_with_missing_instruments_section(self, mocks_for_inst):
        config = mocks_for_inst["config_with_raw"]
        config.raw.pop("instruments", None)

        with pytest.raises(KeyError) as e:
            config.populate_instruments()

        assert "Missing 'instruments' section in configuration." in str(e.value)
        assert mocks_for_inst["mock_find_missing_params"].not_called()

    def test_with_missing_keys(self, mocks_for_inst):
        config = mocks_for_inst["config_with_raw"]

        missing = "'firmware' parameter"
        mock_missing_params = mocks_for_inst["mock_find_missing_params"]
        mock_missing_params.return_value = missing

        with pytest.raises(KeyError) as e:
            config.populate_instruments()

        assert mock_missing_params.called_once_with(
            config.raw["instruments"]["furnace"],
            ["firmware", "address", "variables"],
        )
        assert f"Missing {missing} for instrument 'furnace' in configuration." in str(
            e.value
        )

    def test_with_no_variables(self, mocks_for_inst):
        config = mocks_for_inst["config_with_raw"]
        config.raw["instruments"]["furnace"]["variables"] = {}

        with pytest.raises(ValueError) as e:
            config.populate_instruments()

        assert "Instrument 'furnace' must have at least one variable" in str(e.value)

    def test_full_comodo_yaml(self, mocks_for_inst):
        config = mocks_for_inst["config_with_raw"]

        config.populate_instruments()

        assert config.instruments == mocks_for_inst["expected_instruments"]


class TestPopulateSensorsActuatorsSPCs:
    @pytest.fixture
    def mocks_for_saspcs(self, mock_comodo_config):
        with patch("comodo_config.find_missing_params") as mock_find_missing_params:
            mock_find_missing_params.return_value = None

            config_with_insts = ComodoConfig()
            config_with_insts.instruments = mock_comodo_config.instruments

            expected_sensors = mock_comodo_config.sensors
            expected_actuators = mock_comodo_config.actuators
            expected_spcs = mock_comodo_config.spcs

            yield {
                "config_with_insts": config_with_insts,
                "mock_find_missing_params": mock_find_missing_params,
                "expected_sensors": expected_sensors,
                "expected_actuators": expected_actuators,
                "expected_spcs": expected_spcs,
            }

    def test_sensor_only(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {"variables": {"V_A": {"sensor": {"some": "config"}}}}
        }

        config.populate_sensors_actuators_spcs()

        assert config.sensors == {"I_A/V_A": {"some": "config"}}
        assert config.actuators == {}
        assert config.spcs == {}

    def test_actuator_missing_safe_stop_setpoint(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {"variables": {"V_A": {"actuator": {"some": "config"}}}}
        }

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert "Actuator 'I_A/V_A' does not have a 'safe_stop_setpoint'" in str(e.value)

    def test_actuator_missing_driving_sensor(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {"variables": {"V_A": {"actuator": {"safe_stop_setpoint": 0}}}}
        }

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "Driving sensor 'I_A/V_A' for actuator 'I_A/V_A' not found in sensors."
            in str(e.value)
        )

    def test_actuator_with_driving_sensor_missing_default_setpoint(
        self, mocks_for_saspcs
    ):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "sensor": {"some": "config"},
                        "actuator": {"safe_stop_setpoint": 0},
                    }
                }
            }
        }

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "Driving sensor 'I_A/V_A' for actuator 'I_A/V_A' does not have a 'default_setpoint'"
            in str(e.value)
        )

    def test_actuator_with_full_driving_sensor(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "sensor": {"default_setpoint": 0},
                        "actuator": {"safe_stop_setpoint": 0},
                    }
                }
            }
        }

        config.populate_sensors_actuators_spcs()

        assert config.sensors == {"I_A/V_A": {"default_setpoint": 0}}
        assert config.actuators == {
            "I_A/V_A": {
                "safe_stop_setpoint": 0,
                "driving_sensor": "I_A/V_A",
            }
        }
        assert config.spcs == {}

    def test_spc_without_actuator(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "setpoint_controller": {
                            "external_sensor": "mass_flow/mass_flow"
                        }
                    }
                }
            }
        }

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "SPC can only be linked to a variable with an 'actuator' in configuration."
            in str(e.value)
        )
        assert "Variable 'I_A/V_A' does not have an 'actuator'" in str(e.value)

    def test_spc_missing_external_sensor(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "actuator": {"safe_stop_setpoint": 0},
                        "setpoint_controller": {
                            "external_sensor": "mass_flow/mass_flow"
                        },
                    }
                }
            }
        }
        missing = "'external_sensor' parameter"
        mock_missing_params = mocks_for_saspcs["mock_find_missing_params"]
        mock_missing_params.return_value = missing

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "Missing 'external_sensor' parameter for SPC linked to variable 'I_A/V_A' in configuration."
            in str(e.value)
        )

    def test_spc_with_actuator_but_mising_driving_sensor(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "actuator": {"safe_stop_setpoint": 0},
                        "setpoint_controller": {"external_sensor": "I_B/V_B"},
                    },
                }
            }
        }
        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "Driving sensor 'I_B/V_B' for actuator 'I_A/V_A' not found in sensors."
            in str(e.value)
        )

    def test_spc_with_actuator_missing_default_setpoint(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "actuator": {"safe_stop_setpoint": 0},
                        "setpoint_controller": {"external_sensor": "I_B/V_B"},
                    }
                }
            },
            "I_B": {
                "variables": {
                    "V_B": {
                        "sensor": {"some": "config"},
                    }
                }
            },
        }

        with pytest.raises(KeyError) as e:
            config.populate_sensors_actuators_spcs()

        assert (
            "Driving sensor 'I_B/V_B' for actuator 'I_A/V_A' does not have a 'default_setpoint'"
            in str(e.value)
        )

    def test_spc_with_actuator_and_complete_driving_sensor(self, mocks_for_saspcs):
        config = ComodoConfig()
        config.instruments = {
            "I_A": {
                "variables": {
                    "V_A": {
                        "actuator": {"safe_stop_setpoint": 0},
                        "setpoint_controller": {"external_sensor": "I_B/V_B"},
                    }
                }
            },
            "I_B": {
                "variables": {
                    "V_B": {
                        "sensor": {"default_setpoint": 0},
                    }
                }
            },
        }

        config.populate_sensors_actuators_spcs()

        assert config.sensors == {"I_B/V_B": {"default_setpoint": 0}}
        assert config.actuators == {
            "I_A/V_A": {
                "safe_stop_setpoint": 0,
                "driving_sensor": "I_B/V_B",
            }
        }
        assert config.spcs == {
            "I_B-V_B--I_A-V_A": {
                "external_sensor": "I_B/V_B",
                "actuator": "I_A/V_A",
            }
        }

    def test_full_comodo_yaml(self, mocks_for_saspcs):
        config = mocks_for_saspcs["config_with_insts"]

        config.populate_sensors_actuators_spcs()

        assert config.sensors == mocks_for_saspcs["expected_sensors"]
        assert config.actuators == mocks_for_saspcs["expected_actuators"]
        assert config.spcs == mocks_for_saspcs["expected_spcs"]


class TestGetExpectedHeartbeat:
    @pytest.fixture
    def mocks_for_gehb(self, mock_comodo_yaml_dict, mock_comodo_config):
        config_with_insts = ComodoConfig()
        config_with_insts.instruments = mock_comodo_config.instruments

        yield {
            "config_with_insts": config_with_insts,
        }

    def test_missing_instrument(self, mocks_for_gehb):
        config = mocks_for_gehb["config_with_insts"]

        with pytest.raises(KeyError) as e:
            config.get_expected_heartbeat("non_existent_instrument")

        assert (
            "Instrument 'non_existent_instrument' not found in configuration."
            in str(e.value)
        )

    def test_full_comodo_yaml(self, mocks_for_gehb):
        config = mocks_for_gehb["config_with_insts"]

        heartbeat = config.get_expected_heartbeat("furnace")

        assert heartbeat == {
            "firmware": "carbolite_gero.tg3",
            "device_address": "192.168.111.222",
            "simulate": True,
            "variables": ["temperature"],
        }


class TestGetDefaultExperiment:
    @pytest.fixture
    def mocks_for_gde(self, mock_comodo_config):
        config_with_saspcs = ComodoConfig()
        config_with_saspcs.sensors = mock_comodo_config.sensors
        config_with_saspcs.actuators = mock_comodo_config.actuators
        config_with_saspcs.spcs = mock_comodo_config.spcs

        expected_def_experiment = mock_comodo_config.get_default_experiment()

        yield {
            "config_with_saspcs": config_with_saspcs,
            "expected_def_experiment": expected_def_experiment,
        }

    def test_full_comodo_yaml(self, mocks_for_gde):
        config = mocks_for_gde["config_with_saspcs"]

        default_experiment = config.get_default_experiment()

        assert default_experiment == mocks_for_gde["expected_def_experiment"]
