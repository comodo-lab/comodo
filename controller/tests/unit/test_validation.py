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
        with patch("builtins.open") as mock_open:
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
                "open": mock_open,
                "config": mock_config,
            }

    # ========================================

    def test_missing_driving_sensors(self, grs_mocks):
        config = grs_mocks["config"]
        config.actuators = {"I_A": {"some": "config"}}

        with pytest.raises(ExperimentValidationError) as e:
            generate_row_schema(grs_mocks["config"])

        assert e.value.args[0].startswith("Wrong comodo yaml config")
        grs_mocks["open"].assert_not_called()

    def test_missing_sensor(self, grs_mocks):
        config = grs_mocks["config"]
        config.sensors = {"I_A": {"some": "config"}}

        with pytest.raises(ExperimentValidationError) as e:
            generate_row_schema(grs_mocks["config"])

        assert e.value.args[0].startswith("Wrong comodo yaml config")
        grs_mocks["open"].assert_not_called()

    def test_write_error(self, grs_mocks):
        mock_open = grs_mocks["open"]
        mock_open.side_effect = Exception("Write error")

        with pytest.raises(ExperimentValidationError) as e:
            generate_row_schema(grs_mocks["config"])

        assert e.value.args[0].startswith("Failed to write row schema")
        mock_open.assert_called_once_with("/app/schemas/experiment_row.yaml", "w")

    def test_expected_fields(self, grs_mocks):
        mock_open = grs_mocks["open"]

        schema = generate_row_schema(grs_mocks["config"])

        mock_open.assert_called_once_with("/app/schemas/experiment_row.yaml", "w")
        handle = mock_open.return_value.__enter__.return_value
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        assert schema == yaml.safe_load(written_content)

        assert "channels" in schema
        assert "experimentRow" in schema["channels"]
        assert "messages" in schema["channels"]["experimentRow"]
        assert "experimentRow" in schema["channels"]["experimentRow"]["messages"]
        payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
            "payload"
        ]

        # Check additionalProperties
        assert payload.get("additionalProperties") is False

        # Check required fields
        required_fields = payload.get("required", [])
        assert "time" in required_fields
        assert "I_A/V_A" in required_fields
        assert "I_B/V_B" in required_fields

        # Check time field properties
        properties = payload.get("properties", {})
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
        schema = generate_row_schema(grs_mocks["config"])
        payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
            "payload"
        ]

        jsonschema.validate(
            {"time": 5, "I_A/V_A": 5, "I_B/V_B": 10},
            payload,
        )

    def test_generated_row_schema_rejects_out_of_range(self, grs_mocks):
        schema = generate_row_schema(grs_mocks["config"])
        payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
            "payload"
        ]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"time": 5, "I_A/V_A": 99, "I_B/V_B": 10},
                payload,
            )

    def test_generated_row_schema_rejects_missing_required_field(self, grs_mocks):
        schema = generate_row_schema(grs_mocks["config"])
        payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
            "payload"
        ]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"time": 5}, payload)

    def test_generated_row_schema_rejects_wrong_instrument(self, grs_mocks):
        schema = generate_row_schema(grs_mocks["config"])
        payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
            "payload"
        ]

        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"time": 5, "I_A/V_A": 5, "I_B/V_B": 10, "I_C/V_C": 0},
                payload,
            )


class TestValidateExperiment:

    @pytest.fixture(autouse=True)
    def ve_mocks(self):
        with (
            patch("builtins.open") as mock_open,
            patch("src.validation.generate_row_schema") as mock_gen,
            patch("src.validation.validate_message") as mock_val,
        ):
            valid_experiment_json = json.dumps(
                {
                    "id": "test-123",
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
            mock_val.return_value = None
            mock_config = MagicMock()

            yield {
                "experiment": valid_experiment_json,
                "open": mock_open,
                "generate_row_schema": mock_gen,
                "validate_message": mock_val,
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

    def test_raises_on_row_schema_generation_failure(self, ve_mocks):
        ve_mocks["generate_row_schema"].side_effect = Exception(
            "Schema generation failed"
        )

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Failed to generate row schema" in str(e.value)
        assert "Schema generation failed" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["validate_message"].assert_called_once_with(
            "ui/start", ve_mocks["experiment"]
        )
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])

    def test_raises_on_missing_experiment_definition(self, ve_mocks):
        ve_mocks["open"].return_value.__enter__.return_value.read.return_value = (
            json.dumps({"id": "test-123", "config": {"resolution": 0.1}})
        )

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Missing experiment definition" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])

    def test_raises_on_row_validation_failure(self, ve_mocks):
        ve_mocks["validate_message"].side_effect = [
            None,  # First call for "ui/start" passes
            MQTTValidationException(
                "Invalid row 1"
            ),  # Second call for "experiment/row" fails
        ]

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", ve_mocks["config"])

        assert "Experiment row validation failed" in str(e.value)
        assert "Invalid row 1" in str(e.value)
        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])
        assert (
            ve_mocks["validate_message"].call_count == 2
        ), "Expected 1 call for ui/start, and 1 for experiment row failure"

    def test_valid_experiment(self, ve_mocks):
        result = validate_experiment("/fake/path", ve_mocks["config"])

        ve_mocks["open"].assert_called_once_with("/fake/path")
        ve_mocks["generate_row_schema"].assert_called_once_with(ve_mocks["config"])
        assert (
            ve_mocks["validate_message"].call_count == 3
        ), "Expected 1 call for ui/start, and 2 for experiment rows"

        assert result == json.loads(ve_mocks["experiment"])
