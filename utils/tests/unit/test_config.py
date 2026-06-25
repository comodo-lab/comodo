import pytest
import yaml
from utils.config import ComodoConfig, load, get

FIXTURE_PATH = "utils/tests/file_fixtures/comodo.yaml"


@pytest.fixture
def sample_config():
    return ComodoConfig(FIXTURE_PATH)


class TestLoad:
    def test_load_valid(self):
        cfg = ComodoConfig(FIXTURE_PATH)
        assert cfg is not None

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            ComodoConfig("/nonexistent/comodo.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        p = tmp_path / "comodo.yaml"
        p.write_text("{invalid: yaml: [}")
        with pytest.raises(yaml.YAMLError):
            ComodoConfig(str(p))

    def test_load_no_instruments(self, tmp_path):
        p = tmp_path / "comodo.yaml"
        p.write_text("global: {heartbeat: {interval: 1}}")
        with pytest.raises(ValueError, match="No instruments defined"):
            ComodoConfig(str(p))


class TestGlobalSettings:
    def test_global_settings(self, sample_config):
        assert sample_config.heartbeat_interval == 1.0
        assert sample_config.watchdog_interval == 1.0
        assert sample_config.watchdog_timeout == 5.0
        assert sample_config.instrument_setup_wait == 10.0


class TestInstruments:
    def test_raw_instruments(self, sample_config):
        assert set(sample_config.instruments.keys()) == {
            "furnace_centre", "furnace_left", "furnace_right",
            "pressure_downstream", "pressure_upstream", "mass_flow", "mass_spec",
        }

    def test_actuator_variables(self, sample_config):
        assert sample_config.actuator_variables == {
            "furnace_centre/temperature",
            "mass_flow/mass_flow",
        }

    def test_sensor_variables(self, sample_config):
        expected = {
            "furnace_centre/temperature",
            "furnace_left/temperature",
            "furnace_right/temperature",
            "pressure_downstream/pressure",
            "pressure_upstream/pressure",
            "mass_flow/mass_flow",
            "mass_flow/temperature",
            "mass_flow/pressure_upstream",
            "mass_flow/pressure_downstream",
            "mass_spec/mass_spec",
        }
        assert sample_config.sensor_variables == expected

    def test_actuator_instruments(self, sample_config):
        assert sample_config.actuator_instruments == {"furnace_centre", "mass_flow"}

    def test_sensor_instruments(self, sample_config):
        assert sample_config.sensor_instruments == {
            "furnace_left", "furnace_right",
            "pressure_downstream", "pressure_upstream", "mass_spec",
        }

    def test_controllable_variables(self, sample_config):
        by_name = {v["name"]: v for v in sample_config.controllable_variables}
        names = list(by_name.keys())
        assert names == [
            "furnace_centre/temperature",
            "mass_flow/mass_flow",
            "pressure_upstream/pressure",
        ]

        fct = by_name["furnace_centre/temperature"]
        assert fct["min"] == 0
        assert fct["max"] == 1000
        assert fct["step"] == 1
        assert fct["default_setpoint"] == 0
        assert fct["tolerance"] == 1.0

        mf = by_name["mass_flow/mass_flow"]
        assert mf["min"] == 0
        assert mf["max"] == 100
        assert mf["default_setpoint"] == 0
        assert mf["tolerance"] == 1.0

        pup = by_name["pressure_upstream/pressure"]
        assert pup["min"] == 0
        assert pup["max"] == 10
        assert pup["default_setpoint"] == 0
        assert pup["tolerance"] == 1.0

    def test_instrument_expected(self, sample_config):
        ie = sample_config.instrument_expected
        assert ie["furnace_centre"]["firmware"] == "carbolite_gero.tg3"
        assert ie["furnace_centre"]["device_address"] == "192.168.111.222"
        assert "temperature" in ie["furnace_centre"]["variables"]

        assert ie["mass_flow"]["firmware"] == "bronkhorst.el_flow_select"
        assert ie["mass_flow"]["device_address"] == "/dev/ttyUSB2"
        assert len(ie["mass_flow"]["variables"]) == 4

        assert ie["furnace_left"]["firmware"] == "carbolite_gero.tg3"
        assert ie["furnace_left"]["device_address"] == "192.168.111.224"


class TestPID:
    def test_pid_pairs_detected(self, sample_config):
        assert len(sample_config.pid_pairs) == 1
        pair = sample_config.pid_pairs[0]
        assert pair["actuator"] == "mass_flow/mass_flow"
        assert pair["sensor"] == "pressure_upstream/pressure"
        assert pair["k_p"] == 10.0
        assert pair["k_i"] == 1.0
        assert pair["k_d"] == 0.1
        assert pair["k_aw"] == 0.05
        assert pair["k_df"] == 0.01


class TestDefaultExperiment:
    def test_default_experiment(self, sample_config):
        rows = sample_config.default_experiment
        assert len(rows) == 1

        row = rows[0]
        assert row["time"] == 0

        for v in sample_config.controllable_variables:
            assert row[v["name"]] == v["default_setpoint"]
            assert row[f"{v['name']}_profile"] == "linear"


class TestSingleton:
    def test_get_before_load_raises(self):
        with pytest.raises(RuntimeError, match="not loaded"):
            get()

    def test_load_and_get(self, tmp_path):
        import shutil
        dest = tmp_path / "comodo.yaml"
        shutil.copy(FIXTURE_PATH, str(dest))
        cfg = load(str(dest))
        assert get() is cfg
