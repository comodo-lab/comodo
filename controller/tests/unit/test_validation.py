import json

import pytest
import yaml
from jsonschema import ValidationError, validate
from jinja2 import Template
from unittest.mock import mock_open, patch, MagicMock

from src.validation import validate_experiment, ExperimentValidationError
from utils.mqtt_validator import MQTTValidationException


class TestGenerateRowSchema:

    @pytest.fixture
    def mock_actuator_instruments(self):
        return {
            "furnace_centre": {
                "variables": {"temperature": {"actuator": {"min": 0, "max": 1000}}}
            },
            "mass_spec": {
                "variables": {"mass_spec": {"actuator": {"min": 0, "max": 100}}}
            },
        }

    @staticmethod
    def load_payload(instruments):
        with open("/app/schemas/experiment_schema.yaml.j2") as f:
            rendered = Template(f.read()).render(instruments=instruments)
        return yaml.safe_load(rendered)["channels"]["experimentRow"]["messages"][
            "experimentRow"
        ]["payload"]

    @pytest.fixture
    def mock_payload(self, mock_actuator_instruments):
        return TestGenerateRowSchema.load_payload(mock_actuator_instruments)

    # ========================================

    def test_generated_row_schema_contains_actuators(self, mock_payload):
        payload = mock_payload

        assert payload["required"] == [
            "time",
            "furnace_centre/temperature",
            "mass_spec/mass_spec",
        ]
        assert payload["properties"]["furnace_centre/temperature"] == {
            "type": "number",
            "minimum": 0,
            "maximum": 1000,
        }
        assert payload["properties"]["mass_spec/mass_spec"] == {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
        }

    def test_generated_row_schema_excludes_sensors(self):
        instruments = {
            "furnace": {"variables": {"temp": {"actuator": {"min": 0, "max": 500}}}},
            "sensor": {"variables": {"reading": {}}},
        }
        payload = TestGenerateRowSchema.load_payload(instruments)

        assert "furnace/temp" in payload["required"]
        assert "sensor/reading" not in payload["required"]
        assert "sensor/reading" not in payload["properties"]

    def test_generated_row_schema_has_profile_fields(self, mock_payload):
        payload = mock_payload

        assert "furnace_centre/temperature_profile" in payload["properties"]
        assert payload["properties"]["furnace_centre/temperature_profile"] == {
            "type": "string",
            "enum": ["linear", "exponential", "logarithmic", "step"],
        }
        assert "mass_spec/mass_spec_profile" in payload["properties"]

    def test_generated_row_schema_has_additional_properties_false(self, mock_payload):
        payload = mock_payload

        assert payload.get("additionalProperties") is False

    def test_generated_row_schema_validates_valid_row(self, mock_payload):
        payload = mock_payload

        validate(
            {"time": 5, "furnace_centre/temperature": 500, "mass_spec/mass_spec": 50},
            payload,
        )

    def test_generated_row_schema_rejects_out_of_range(self, mock_payload):
        payload = mock_payload

        with pytest.raises(ValidationError):
            validate(
                {
                    "time": 5,
                    "furnace_centre/temperature": 9999,
                    "mass_spec/mass_spec": 50,
                },
                payload,
            )

    def test_generated_row_schema_rejects_missing_required_field(self, mock_payload):
        payload = mock_payload

        with pytest.raises(ValidationError):
            validate({"time": 5}, payload)

    def test_generated_row_schema_rejects_wrong_instrument(self, mock_payload):
        payload = mock_payload

        with pytest.raises(ValidationError):
            validate(
                {
                    "time": 5,
                    "furnace_centre/temperature": 500,
                    "mass_spec/mass_spec": 50,
                    "unknown/thing": 0,
                },
                payload,
            )


class TestValidateExperiment:

    @pytest.fixture
    def valid_experiment_json(self):
        return json.dumps(
            {
                "id": "test-123",
                "config": {"resolution": 0.1},
                "experiment_definition": [
                    {
                        "time": 0,
                        "furnace_centre/temperature": 500,
                        "mass_spec/mass_spec": 50,
                    },
                    {
                        "time": 10,
                        "furnace_centre/temperature": 800,
                        "mass_spec/mass_spec": 80,
                    },
                ],
            }
        )

    @pytest.fixture(autouse=True)
    def validate_experiment_mocks(self, valid_experiment_json):
        with (
            patch("builtins.open") as mock_open,
            patch("src.validation.generate_row_schema") as mock_gen,
            patch("src.validation.validate_message") as mock_val,
        ):
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

    def test_raises_on_missing_file(self, validate_experiment_mocks):
        mocks = validate_experiment_mocks
        mocks["open"].side_effect = FileNotFoundError()

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/nonexistent/path", mocks["config"])

        assert "Experiment file not found" in str(e.value)

    def test_raises_on_invalid_structure(self, validate_experiment_mocks):
        mocks = validate_experiment_mocks
        mocks["validate_message"].side_effect = MQTTValidationException(
            "Invalid structure"
        )

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", mocks["config"])

        assert "Experiment validation failed" in str(e.value)
        assert "Invalid structure" in str(e.value)
        mocks["open"].assert_called_once_with("/fake/path")
        mocks["generate_row_schema"].assert_not_called()

    def test_raises_on_row_schema_generation_failure(self, validate_experiment_mocks):
        mocks = validate_experiment_mocks
        mocks["generate_row_schema"].side_effect = Exception("Schema generation failed")

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", mocks["config"])

        assert "Failed to generate row schema" in str(e.value)
        assert "Schema generation failed" in str(e.value)
        mocks["open"].assert_called_once_with("/fake/path")
        mocks["validate_message"].assert_called_once_with(
            "ui/start", mocks["experiment"]
        )
        mocks["generate_row_schema"].assert_called_once_with(mocks["config"])

    def test_raises_on_row_validation_failure(self, validate_experiment_mocks):
        mocks = validate_experiment_mocks
        mocks["validate_message"].side_effect = [
            None,  # First call for "ui/start" passes
            MQTTValidationException(
                "Invalid row 1"
            ),  # Second call for "experiment/row" fails
        ]

        with pytest.raises(ExperimentValidationError) as e:
            validate_experiment("/fake/path", mocks["config"])

        assert "Experiment row validation failed" in str(e.value)
        assert "Invalid row 1" in str(e.value)
        mocks["open"].assert_called_once_with("/fake/path")
        mocks["generate_row_schema"].assert_called_once_with(mocks["config"])
        assert (
            mocks["validate_message"].call_count == 2
        ), "Expected 1 call for ui/start, and 1 for experiment row failure"

    def test_valid_experiment(self, validate_experiment_mocks):
        mocks = validate_experiment_mocks

        result = validate_experiment("/fake/path", mocks["config"])

        mocks["open"].assert_called_once_with("/fake/path")
        mocks["generate_row_schema"].assert_called_once_with(mocks["config"])
        assert (
            mocks["validate_message"].call_count == 3
        ), "Expected 1 call for ui/start, and 2 for experiment rows"

        assert result == json.loads(mocks["experiment"])
