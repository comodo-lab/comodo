import json

import pytest
import yaml
import jsonschema
from unittest.mock import patch, MagicMock

from src.validation import (
    validate_experiment,
    generate_row_schema,
    ExperimentValidationError,
)
from utils.mqtt_validator import MQTTValidationException


class TestGenerateRowSchema:

    @pytest.fixture(autouse=True)
    def grs_mocks(self):

        mock_config = MagicMock()
        mock_config.actuators = {
            "I_A": {"driving_sensor": "I_A/V_A"},
            "I_C": {"driving_sensor": "I_B/V_B"},
        }
        mock_config.sensors = {
            "I_A/V_A": {"min": 1, "max": 10},
            "I_B/V_B": {"min": 2, "max": 20},
            "I_C/V_C": {"min": 3, "max": 30},
        }

        yield {
            "config": mock_config,
        }

    # ========================================

    def test_missing_driving_sensors(self, grs_mocks):
        config = grs_mocks["config"]
        config.actuators = {"I_A": {"some": "config"}}

        with pytest.raises(ExperimentValidationError) as e:
            generate_row_schema(grs_mocks["config"])

        assert e.value.args[0].startswith("Wrong comodo yaml config")

    def test_missing_sensor(self, grs_mocks):
        config = grs_mocks["config"]
        config.sensors = {"I_A": {"some": "config"}}

        with pytest.raises(ExperimentValidationError) as e:
            generate_row_schema(grs_mocks["config"])

        assert e.value.args[0].startswith("Wrong comodo yaml config")

    def test_expected_fields(self, grs_mocks):
        json_schema = generate_row_schema(grs_mocks["config"])

        # Check additionalProperties
        assert json_schema.get("additionalProperties") is False

        # Check required fields
        required_fields = json_schema.get("required", [])
        assert "time" in required_fields
        assert "I_A/V_A" in required_fields
        assert "I_B/V_B" in required_fields

        # Check time field properties
        properties = json_schema.get("properties", {})
        assert "time" in properties
        assert properties["time"] == {"type": "number", "minimum": 0}

        # Check driving sensor properties
        assert "I_A/V_A" in properties
        assert properties["I_A/V_A"] == {
            "type": "number",
            "minimum": 1,
            "maximum": 10,
        }
        assert "I_B/V_B" in properties
        assert properties["I_B/V_B"] == {"type": "number", "minimum": 2, "maximum": 20}

        # Check driving sensor profile properties
        assert properties["I_A/V_A_profile"] == {
            "type": "string",
            "enum": ["linear", "exponential", "logarithmic", "step"],
        }
        assert properties["I_B/V_B_profile"] == {
            "type": "string",
            "enum": ["linear", "exponential", "logarithmic", "step"],
        }

    def test_generated_row_schema_validates_valid_row(self, grs_mocks):
        json_schema = generate_row_schema(grs_mocks["config"])

        jsonschema.validate({"time": 5, "I_A/V_A": 5, "I_B/V_B": 10}, json_schema)

    def test_generated_row_schema_rejects_out_of_range(self, grs_mocks):
        json_schema = generate_row_schema(grs_mocks["config"])

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"time": 5, "I_A/V_A": 99, "I_B/V_B": 10}, json_schema)

    def test_generated_row_schema_rejects_missing_required_field(self, grs_mocks):
        json_schema = generate_row_schema(grs_mocks["config"])

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"time": 5}, json_schema)

    def test_generated_row_schema_rejects_wrong_instrument(self, grs_mocks):
        json_schema = generate_row_schema(grs_mocks["config"])

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"time": 5, "I_A/V_A": 5, "I_B/V_B": 10, "I_C/V_C": 0},
                json_schema,
            )


class TestValidateExperiment:

    @pytest.fixture(autouse=True)
    def ve_mocks(self, mqtt_validator_mocks):
        with (
            patch("builtins.open") as mock_open,
            patch("src.validation.generate_row_schema") as mock_gen,
            patch("src.validation.jsonschema.validate") as mock_json_validate,
        ):
            valid_experiment_json = json.dumps(
                {
                    "temp_id": "test-123",
                    "config": {"resolution": 0.1},
                    "experiment_definition": [
                        {
                            "time": 0,
                            "I_A/V_A": 500,
                            "I_B/V_B": 50,
                        },
                        {
                            "time": 10,
                            "I_A/V_A": 800,
                            "I_B/V_B": 80,
                        },
                    ],
                }
            )
            mock_open.return_value.__enter__.return_value.read.return_value = (
                valid_experiment_json
            )
            mock_gen.return_value = None
            mock_config = MagicMock()

            yield {
                "experiment": valid_experiment_json,
                "open": mock_open,
                "generate_row_schema": mock_gen,
                "validate_message": mqtt_validator_mocks["validate_message"],
                "json_validate": mock_json_validate,
                "config": mock_config,
            }

    # ========================================

    def test_raises_on_missing_file(self, ve_mocks):
        ve_mocks["open"].side_effect = FileNotFoundError()

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/nonexistent/path", ve_mocks["config"])

        assert "Experiment file not found" in str(e.value)

    def test_raises_on_invalid_structure(self, ve_mocks):
        ve_mocks["validate_message"].side_effect = MQTTValidationException(
            "Invalid structure"
        )

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Experiment validation failed" in str(e.value)
        assert "Invalid structure" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_not_called()

    def test_raises_on_missing_experiment_definition(self, ve_mocks):
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps({"temp_id": "test-123", "config": {"resolution": 0.1}})
        )

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Missing experiment definition" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])

    def test_raises_on_row_validation_failure(self, ve_mocks):
        ve_mocks["json_validate"].side_effect = [
            jsonschema.ValidationError("Invalid row 1")
        ]

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Experiment row validation failed" in str(e.value)
        assert "Invalid row 1" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])
        ve_mocks["validate_message"].assert_called_once_with(
            "ui/start", ve_mocks["experiment"]
        )
        ve_mocks["json_validate"].assert_called_once_with(
            {"time": 0, "I_A/V_A": 500, "I_B/V_B": 50}, None
        )

    def test_valid_experiment(self, ve_mocks):
        result = validate_experiment("/fake/path", ve_mocks["config"])

        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])
        ve_mocks["validate_message"].assert_called_once_with(
            "ui/start", ve_mocks["experiment"]
        )
        assert ve_mocks["json_validate"].call_args_list == [
            (({"time": 0, "I_A/V_A": 500, "I_B/V_B": 50}, None),),
            (({"time": 10, "I_A/V_A": 800, "I_B/V_B": 80}, None),),
        ]

        assert result == json.loads(ve_mocks["experiment"])

    def test_valid_instruments_live_config(self, ve_mocks):
        experiment = json.loads(ve_mocks["experiment"])
        experiment["config"]["instruments"] = {"I_A": {"offset": 273}}
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps(experiment)
        )
        ve_mocks["config"].instruments = {"I_A": {}, "I_B": {}}

        result = validate_experiment("/fake/path", ve_mocks["config"])

        assert result["config"]["instruments"] == {"I_A": {"offset": 273}}

    def test_raises_on_unknown_instrument_live_config(self, ve_mocks):
        experiment = json.loads(ve_mocks["experiment"])
        experiment["config"]["instruments"] = {"I_C": {"offset": 273}}
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps(experiment)
        )
        ve_mocks["config"].instruments = {"I_A": {}, "I_B": {}}

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Live config for unknown instrument 'I_C'" in str(e.value)

    def test_raises_on_missing_tolerance_in_live_config(self, ve_mocks):
        experiment = json.loads(ve_mocks["experiment"])
        experiment["config"]["instruments"] = {"I_A": {"offset": 273}}
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps(experiment)
        )
        ve_mocks["config"].instruments = {"I_A": {}}
        ve_mocks["config"].actuators = {"I_A": {"driving_sensor": "I_A/V_A"}}
        ve_mocks["config"].sensors = {"I_A/V_A": {}}

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Missing tolerance for 'I_A/V_A' in the live config" in str(e.value)

    def test_valid_spcs_live_config(self, ve_mocks):
        experiment = json.loads(ve_mocks["experiment"])
        experiment["config"]["spcs"] = {"I_A-V_A--I_B-V_B": {"pid": {"k_p": 1.0}}}
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps(experiment)
        )
        ve_mocks["config"].spcs = {"I_A-V_A--I_B-V_B": {}}

        result = validate_experiment("/fake/path", ve_mocks["config"])

        assert result["config"]["spcs"] == {"I_A-V_A--I_B-V_B": {"pid": {"k_p": 1.0}}}

    def test_raises_on_unknown_spc_live_config(self, ve_mocks):
        experiment = json.loads(ve_mocks["experiment"])
        experiment["config"]["spcs"] = {"I_C-V_C--I_B-V_B": {"pid": {"k_p": 1.0}}}
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps(experiment)
        )
        ve_mocks["config"].spcs = {"I_A-V_A--I_B-V_B": {}}

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Live config for unknown setpoint controller 'I_C-V_C--I_B-V_B'" in str(
            e.value
        )

    def test_raises_on_missing_spc_live_config(self, ve_mocks):
        ve_mocks["config"].spcs = {"I_A-V_A--I_B-V_B": {}}

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert (
            "Missing PID config for setpoint controller(s) I_A-V_A--I_B-V_B "
            "in the live config" in str(e.value)
        )
