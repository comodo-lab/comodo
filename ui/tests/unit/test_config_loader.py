import pytest
import sys
import os

from src.config_loader import UiConfig, PID_DEFAULTS


class TestUiConfig:
    def test_params_from_simple_config(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        assert config.params == ["test_actuator/output"]

    def test_sensor_only_excluded_from_params(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        assert "test_sensor/reading" not in config.params

    def test_actuator_detection(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        dicts = config.param_dicts
        assert len(dicts) == 1
        assert dicts[0]["name"] == "test_actuator/output"

    def test_param_dicts_min_max(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        d = config.param_dicts[0]
        assert d["min"] == 0
        assert d["max"] == 10
        assert d["step"] == 1
        assert d["default_setpoint"] == 5

    def test_pid_target_detection(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid)
        assert "test_sensor/value" in config.params
        assert "test_spc/output" not in config.params

    def test_pid_actuator_in_instrument_dict(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid)
        instruments = config.ini_instrument_dict
        assert instruments == [
            {"name": "test_sensor/value", "key": "tolerance", "value": 0.5},
            {"name": "test_spc/output", "key": "tolerance", "value": 1.0},
        ]

    def test_pid_target_uses_sensor_range(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid)
        # The external sensor's range, not the actuator's (0-100)
        target = next(d for d in config.param_dicts if d["name"] == "test_sensor/value")
        assert target["min"] == 0
        assert target["max"] == 10
        assert target["default_setpoint"] == 2

    def test_ini_data_dict_structure(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        data = config.ini_data_dict
        assert len(data) == 1
        row = data[0]
        assert row.pop("id")
        assert row == {
            "time": 0,
            "test_actuator/output": 5,
            "test_actuator/output_profile": "linear",
        }

    def test_ini_data_dict_new_ids(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        assert config.ini_data_dict[0]["id"] != config.ini_data_dict[0]["id"]

    def test_ini_data_dict_pid_uses_external_sensor(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid)
        row = config.ini_data_dict[0]
        assert row["test_sensor/value"] == 2
        assert "test_spc/output" not in row

    def test_ini_data_dict_excludes_sensor_only(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        data = config.ini_data_dict
        for row in data:
            assert "test_sensor/reading" not in row

    def test_ini_instrument_dict(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        instruments = config.ini_instrument_dict
        assert instruments == [
            {"name": "test_sensor/reading", "key": "tolerance", "value": 1.0},
            {"name": "test_actuator/output", "key": "tolerance", "value": 0.5},
        ]

    def test_ini_spc_dict(self, sample_config_with_pid):
        config = UiConfig(sample_config_with_pid)
        assert config.ini_spc_dict == [
            {
                "name": "test_sensor-value--test_spc-output",
                "k_p": 10.0,
                "k_i": 1.0,
                "k_d": 0.1,
                "k_aw": 0.05,
                "k_df": 0.01,
                "max_rate": None,
            }
        ]

    def test_ini_spc_dict_max_rate(self, sample_config_with_pid):
        with open(sample_config_with_pid) as f:
            content = f.read()
        with open(sample_config_with_pid, "w") as f:
            f.write(content.replace("          K_DF: 0.01\n", "          K_DF: 0.01\n          MAX_RATE: 5.0\n"))
        assert UiConfig(sample_config_with_pid).ini_spc_dict[0]["max_rate"] == 5.0

    def test_ini_spc_dict_defaults_missing_values(self, sample_config_with_pid):
        with open(sample_config_with_pid) as f:
            content = f.read()
        with open(sample_config_with_pid, "w") as f:
            f.write(content.replace("          K_AW: 0.05\n", "").replace("          K_DF: 0.01\n", ""))
        config = UiConfig(sample_config_with_pid)
        row = config.ini_spc_dict[0]
        assert row["k_p"] == 10.0
        assert row["k_aw"] == PID_DEFAULTS["k_aw"]
        assert row["k_df"] == PID_DEFAULTS["k_df"]

    def test_ini_spc_dict_without_spcs(self, sample_config_yaml):
        assert UiConfig(sample_config_yaml).ini_spc_dict == []

    def test_ini_experiment_config(self, sample_config_yaml):
        config = UiConfig(sample_config_yaml)
        ec = config.ini_experiment_config
        assert len(ec) == 1
        assert ec[0]["name"] == "resolution"
        assert ec[0]["value"] == 1

    def test_missing_config_raises(self):
        with pytest.raises(FileNotFoundError):
            UiConfig("/nonexistent/comodo.yaml")

    def test_custom_config_path(self, sample_config_yaml):
        config = UiConfig(config_path=sample_config_yaml)
        assert len(config.params) > 0

    def test_real_comodo_yaml(self):
        real_path = os.path.join(os.path.dirname(__file__), "../../../comodo.yaml")
        if not os.path.exists(real_path):
            pytest.skip("comodo.yaml not found at repo root")
        config = UiConfig(real_path)
        # mass_flow is driven by an SPC targeting pressure/pressure
        assert config.params == ["furnace/temperature", "pressure/pressure"]
        instrument_names = [d["name"] for d in config.ini_instrument_dict]
        assert "mass_flow/mass_flow" in instrument_names
        assert "pressure/pressure" in instrument_names
