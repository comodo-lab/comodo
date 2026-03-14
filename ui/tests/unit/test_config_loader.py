import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from config_loader import ComodoConfig


class TestComodoConfig:
    def test_params_from_simple_config(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        assert config.params == ["test_actuator/output"]

    def test_sensor_only_excluded_from_params(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        assert "test_sensor/reading" not in config.params

    def test_actuator_detection(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        dicts = config.param_dicts
        assert len(dicts) == 1
        assert dicts[0]["name"] == "test_actuator/output"

    def test_param_dicts_min_max(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        d = config.param_dicts[0]
        assert d["min"] == 5
        assert d["max"] == 45
        assert d["step"] == 1

    def test_pid_target_detection(self, sample_config_with_pid):
        config = ComodoConfig(sample_config_with_pid)
        assert "pressure/value" in config.params
        # flow/rate is a PID-output actuator — not in designer, only in instrument setup
        assert "flow/rate" not in config.params

    def test_pid_actuator_in_instrument_dict(self, sample_config_with_pid):
        config = ComodoConfig(sample_config_with_pid)
        names = [d["name"] for d in config.ini_instrument_dict]
        assert "flow/rate" in names
        assert "pressure/value" in names

    def test_pid_target_uses_sensor_range(self, sample_config_with_pid):
        config = ComodoConfig(sample_config_with_pid)
        pressure_dict = next(d for d in config.param_dicts if d["name"] == "pressure/value")
        assert pressure_dict["min"] == 0
        assert pressure_dict["max"] == 10

    def test_ini_data_dict_structure(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        data = config.ini_data_dict
        assert len(data) == 3
        assert [r["time"] for r in data] == [0, 30, 60]
        for row in data:
            assert "test_actuator/output" in row
            assert "test_actuator/output_profile" in row
            assert row["test_actuator/output_profile"] == "linear"

    def test_ini_data_dict_excludes_sensor_only(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        data = config.ini_data_dict
        for row in data:
            assert "test_sensor/reading" not in row

    def test_ini_instrument_dict(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        instruments = config.ini_instrument_dict
        assert len(instruments) == 1
        assert instruments[0] == {"name": "test_actuator/output", "tolerance": 1.0}

    def test_ini_experiment_config(self, sample_config_yaml):
        config = ComodoConfig(sample_config_yaml)
        ec = config.ini_experiment_config
        assert len(ec) == 1
        assert ec[0]["name"] == "resolution"
        assert ec[0]["value"] == 1

    def test_missing_config_raises(self):
        with pytest.raises(FileNotFoundError):
            ComodoConfig("/nonexistent/comodo.yaml")

    def test_custom_config_path(self, sample_config_yaml):
        config = ComodoConfig(config_path=sample_config_yaml)
        assert len(config.params) > 0

    def test_real_comodo_yaml(self):
        """Integration test against the real comodo.yaml in the repo."""
        real_path = os.path.join(os.path.dirname(__file__), "../../../comodo.yaml")
        if not os.path.exists(real_path):
            pytest.skip("comodo.yaml not found at repo root")
        config = ComodoConfig(real_path)
        # Pressure upstream is the PID target — appears in designer
        assert "pressure_upstream/pressure" in config.params
        # mass_flow is PID-controlled automatically — not in designer
        assert "mass_flow/mass_flow" not in config.params
        # mass_flow still appears in instrument setup for tolerance tracking
        instrument_names = [d["name"] for d in config.ini_instrument_dict]
        assert "mass_flow/mass_flow" in instrument_names
        assert "pressure_upstream/pressure" in instrument_names
        # Sensor-only variables should not appear anywhere
        assert "pressure_downstream/pressure" not in config.params
        assert "mass_flow/temperature" not in config.params
