import copy
from unittest.mock import patch

import pytest

from tests.conftest import (
    firmware_env,
    mock_load_config,
)

import src.config as config


class TestConfig:
    @pytest.fixture
    def config_mocks(self, firmware_env):
        environment = firmware_env.copy()

        def m_getenv(key, default=None):
            return environment.get(key, default)

        with patch("src.config.os.getenv", side_effect=m_getenv) as mock_getenv:
            yield {
                "env": environment,
                "getenv": mock_getenv,
                "loaded_config": mock_load_config(firmware_env),
                "default_config": copy.deepcopy(config.config),
            }

    def test_load_config(self, config_mocks):
        result = config.load_config()

        assert result == config_mocks["loaded_config"]

    def test_load_config_uses_defaults_when_environment_is_unset(self, config_mocks):
        config_mocks["env"].clear()

        result = config.load_config()

        assert result == config_mocks["default_config"]

    def test_load_config_parses_environment_values(self, config_mocks):
        config_mocks["env"].update(
            {
                "SIMULATE": "false",
                "ACTIVE_VARIABLES": '["flow"]',
                "DEFAULT_SETPOINTS": '{"flow": 2.5}',
                "SAFE_STOP_SETPOINTS": '{"flow": 0}',
                "MEASUREMENT_INTERVALS": '{"flow": 0.5}',
                "HEARTBEAT_INTERVAL": "2.5",
                "experiment": '{"id": "experiment-1"}',
            }
        )

        result = config.load_config()

        assert result["SIMULATE"] is False
        assert result["ACTIVE_VARIABLES"] == ["flow"]
        assert result["DEFAULT_SETPOINTS"] == {"flow": 2.5}
        assert result["SAFE_STOP_SETPOINTS"] == {"flow": 0}
        assert result["MEASUREMENT_INTERVALS"] == {"flow": 0.5}
        assert result["HEARTBEAT_INTERVAL"] == 2.5
        assert result["experiment"] == {"id": "experiment-1"}

    @pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "Yes"])
    def test_load_config_parses_truthy_simulate_values(self, config_mocks, value):
        config_mocks["env"]["SIMULATE"] = value

        assert config.load_config()["SIMULATE"] is True

    @pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "anything"])
    def test_load_config_parses_falsy_simulate_values(self, config_mocks, value):
        config_mocks["env"]["SIMULATE"] = value

        assert config.load_config()["SIMULATE"] is False

    def test_load_config_converts_json_null_values_to_empty_dicts(self, config_mocks):
        json_keys = [
            "ACTIVE_VARIABLES",
            "DEFAULT_SETPOINTS",
            "SAFE_STOP_SETPOINTS",
            "MEASUREMENT_INTERVALS",
            "experiment",
        ]
        for key in json_keys:
            config_mocks["env"][key] = "null"

        result = config.load_config()

        assert all(result[key] == {} for key in json_keys)

    def test_load_config_raises_for_invalid_json(self, config_mocks):
        config_mocks["env"]["DEFAULT_SETPOINTS"] = "not-json"

        with pytest.raises(ValueError):
            config.load_config()

    def test_load_config_raises_for_invalid_numeric_value(self, config_mocks):
        config_mocks["env"]["HEARTBEAT_INTERVAL"] = "not-a-number"

        with pytest.raises(ValueError):
            config.load_config()
