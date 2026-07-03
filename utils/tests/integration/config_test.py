from comodo_config import ComodoConfig

class TestConfigLoad:
    def test_config_load(self):
        # ----------------------------------------------------------------------
        # Load config and assert is non-none
        
        config = ComodoConfig(path="utils/tests/file_fixtures/comodo.yaml")
        config.load()
        assert config is not None

        # ----------------------------------------------------------------------
        # Check global settings
            
        assert config.globals == {            
            "heartbeat_interval": 1.0,
            "watchdog_interval": 1.0,
            "watchdog_timeout": 5.0,
            "instrument_setup_wait": 10.0
        }, "Config failed to load global settings correctly"

        # ----------------------------------------------------------------------
        # Check instrument parsing

        assert config.instruments.keys() == {
            "furnace_centre",
            "furnace_left",
            "furnace_right",
            "pressure_downstream",
            "pressure_upstream",
            "mass_flow",
            "mass_spec"
        }, "Config failed to load instruments correctly"

        assert config.instruments["furnace_centre"].setup == {
            "firmware": "carbolite_gero.tg3",
            "address": "192.168.111.222",
            "variables": ["temperature"]
        }, "Config failed to load instrument setup correctly"

        # ----------------------------------------------------------------------
        # Check variable parsing

        assert config.actuators.keys() == {
            "furnace_centre/temperature",
            "mass_flow/mass_flow"
        }, "Config failed to load actuators correctly"
        
        assert config.sensors.keys() == {
            "furnace_centre/temperature",
            "furnace_left/temperature",
            "furnace_right/temperature",
            "pressure_downstream/pressure",
            "pressure_upstream/pressure",
            "mass_flow/temperature",
            "mass_flow/pressure_upstream",
            "mass_flow/pressure_downstream",
            "mass_spec/mass_spec",
        }, "Config failed to load sensors correctly"

        assert config.actuators["furnace_centre/temperature"] == {
            "min": 0,
            "max": 1000,
            "default_setpoint": 0,
            "tolerance": 1.0,
        }, "Config failed to load actuator setup correctly"
        
        assert config.sensors["pressure_downstream/pressure"] == {
            "min": 0,
            "max": 10
        }, "Config failed to load sensor setup correctly"            

        # ----------------------------------------------------------------------
        # Check SPC listings

        assert len(config.spcs) == 1, "Config failed to load the correct number of SPCs"

        spc = config.spcs[0]
        assert spc == {
            "K_P": 10.0,
            "K_I": 1.0,
            "K_D": 0.1,
            "K_AW": 0.05,
            "K_DF": 0.01,
            "actuator": "mass_flow/mass_flow",
            "external_sensor": "pressure_upstream/pressure"
        }, "Config failed to load SPC setup correctly"

        # ----------------------------------------------------------------------
        # Check default experiment derivation

        assert config.get_default_experiment() == [
            {
                "time": 0,
                "furnace_centre/temperature": 0,
                "furnace_centre/temperature_profile": "linear",
                "mass_flow/mass_flow": 0,
                "mass_flow/mass_flow_profile": "linear"
            }
        ], "Config failed to load default experiment correctly"
