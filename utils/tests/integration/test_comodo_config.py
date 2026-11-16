from comodo_config import ComodoConfig

from tests.conftest import (
    mock_comodo_yaml_dict,
    mock_comodo_config,
)


class TestConfigLoad:
    def test_config_load(self, mock_comodo_yaml_dict, mock_comodo_config):
        # ----------------------------------------------------------------------
        # Load config and check object was populated correctly

        config = ComodoConfig(path="/utils/tests/mocks/comodo.yaml")
        assert config is not None
        config.load()

        assert config.raw == mock_comodo_yaml_dict

        assert (
            config.globals == mock_comodo_config.globals
        ), "Config failed to load global settings correctly"

        assert (
            config.instruments == mock_comodo_config.instruments
        ), "Config failed to load instruments correctly"

        assert (
            config.actuators == mock_comodo_config.actuators
        ), "Config failed to load actuators correctly"

        assert (
            config.sensors == mock_comodo_config.sensors
        ), "Config failed to load sensors correctly"

        assert (
            config.spcs == mock_comodo_config.spcs
        ), "Config failed to load SPCs correctly"

        # ----------------------------------------------------------------------
        # Check default experiment derivation

        assert (
            config.get_default_experiment()
            == mock_comodo_config.get_default_experiment()
        ), "Config failed to load default experiment correctly"

        # ----------------------------------------------------------------------
        # Check heartbeat makes variables into flat list

        expected_heartbeat = {
            "name": "furnace",
            "firmware": "carbolite_gero.tg3",
            "address": "192.168.111.222",
            "simulate": True,
            "variables": ["temperature"],
            "default_setpoints": {"temperature": 25},
            "external_actuators": {},
            "safe_stop_setpoints": {"temperature": 0},
            "measurement_intervals": {"temperature": 1},
            "heartbeat_interval": 1.0,
            "max_missed_heartbeats": 3,
            "experiment": {},
        }
        assert (
            config.get_expected_heartbeat("furnace") == expected_heartbeat
        ), "Config failed to load expected heartbeat correctly"
