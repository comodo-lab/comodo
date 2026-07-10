import json

import pytest
import yaml
from jsonschema import ValidationError, validate
from jinja2 import Template
from unittest.mock import mock_open, patch, MagicMock

from src.validation import validate_experiment


@pytest.fixture
def mock_actuator_instruments():
    return {
        "furnace_centre": {"variables": {"temperature": {"actuator": {"min": 0, "max": 1000}}}},
        "mass_spec":      {"variables": {"mass_spec":     {"actuator": {"min": 0, "max": 100}}}},
    }


@pytest.fixture
def valid_experiment_json():
    return json.dumps({
        "id": "test-123",
        "config": {"resolution": 0.1},
        "experiment_definition": [
            {"time": 0,  "furnace_centre/temperature": 500, "mass_spec/mass_spec": 50},
            {"time": 10, "furnace_centre/temperature": 800, "mass_spec/mass_spec": 80},
        ]
    })


def _load_payload(instruments):
    with open("/app/schemas/experiment_schema.yaml.j2") as f:
        rendered = Template(f.read()).render(instruments=instruments)
    return yaml.safe_load(rendered)["channels"]["experimentRow"]["messages"]["experimentRow"]["payload"]


def test_generated_row_schema_contains_actuators(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    assert payload["required"] == [
        "time", "furnace_centre/temperature", "mass_spec/mass_spec",
    ]
    assert payload["properties"]["furnace_centre/temperature"] == {
        "type": "number", "minimum": 0, "maximum": 1000,
    }
    assert payload["properties"]["mass_spec/mass_spec"] == {
        "type": "number", "minimum": 0, "maximum": 100,
    }


def test_generated_row_schema_excludes_sensors():
    instruments = {
        "furnace": {"variables": {"temp": {"actuator": {"min": 0, "max": 500}}}},
        "sensor":  {"variables": {"reading": {}}},
    }
    payload = _load_payload(instruments)

    assert "furnace/temp" in payload["required"]
    assert "sensor/reading" not in payload["required"]
    assert "sensor/reading" not in payload["properties"]


def test_generated_row_schema_has_profile_fields(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    assert "furnace_centre/temperature_profile" in payload["properties"]
    assert payload["properties"]["furnace_centre/temperature_profile"] == {
        "type": "string", "enum": ["linear", "exponential", "logarithmic", "step"],
    }
    assert "mass_spec/mass_spec_profile" in payload["properties"]


def test_generated_row_schema_has_additional_properties_false(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    assert payload.get("additionalProperties") is False


def test_generated_row_schema_validates_valid_row(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    validate(
        {"time": 5, "furnace_centre/temperature": 500, "mass_spec/mass_spec": 50},
        payload,
    )


def test_generated_row_schema_rejects_out_of_range(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    with pytest.raises(ValidationError):
        validate(
            {"time": 5, "furnace_centre/temperature": 9999, "mass_spec/mass_spec": 50},
            payload,
        )


def test_generated_row_schema_rejects_missing_required_field(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

    with pytest.raises(ValidationError):
        validate({"time": 5}, payload)


def test_generated_row_schema_rejects_wrong_instrument(mock_actuator_instruments):
    payload = _load_payload(mock_actuator_instruments)

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


def test_validate_experiment_valid(valid_experiment_json):
    with patch("builtins.open", mock_open(read_data=valid_experiment_json)):
        with patch("src.validation.generate_row_schema") as mock_gen:
            result = validate_experiment("/fake/path", MagicMock())

    assert result == json.loads(valid_experiment_json)


def test_validate_experiment_calls_generate_row_schema(valid_experiment_json):
    with patch("builtins.open", mock_open(read_data=valid_experiment_json)):
        with patch("src.validation.generate_row_schema") as mock_gen:
            validate_experiment("/fake/path", MagicMock())

    mock_gen.assert_called_once()


def test_validate_experiment_calls_validate_message_per_row(valid_experiment_json):
    experiment = json.loads(valid_experiment_json)
    n_rows = len(experiment["experiment_definition"])

    with patch("builtins.open", mock_open(read_data=valid_experiment_json)):
        with patch("src.validation.generate_row_schema"):
            with patch("src.validation.validate_message") as mock_val:
                validate_experiment("/fake/path", MagicMock())

    assert mock_val.call_count == 1 + n_rows
    mock_val.assert_any_call("ui/start", valid_experiment_json)
    for row in experiment["experiment_definition"]:
        mock_val.assert_any_call(
            "experiment/row", json.dumps(row), schema_name="experiment_row"
        )


def test_validate_experiment_structural_error_propagates(valid_experiment_json):
    def raiser(topic, payload, schema_name="asyncapi"):
        if topic == "ui/start":
            raise ValidationError("Bad experiment structure")

    with patch("builtins.open", mock_open(read_data=valid_experiment_json)):
        with patch("src.validation.generate_row_schema"):
            with patch("src.validation.validate_message", side_effect=raiser):
                with pytest.raises(ValidationError, match="Bad experiment structure"):
                    validate_experiment("/fake/path", MagicMock())


def test_validate_experiment_row_error_propagates(valid_experiment_json):
    def raiser(topic, payload, schema_name="asyncapi"):
        if topic == "experiment/row":
            raise ValidationError("Bad row data")

    with patch("builtins.open", mock_open(read_data=valid_experiment_json)):
        with patch("src.validation.generate_row_schema"):
            with patch("src.validation.validate_message", side_effect=raiser):
                with pytest.raises(ValidationError, match="Bad row data"):
                    validate_experiment("/fake/path", MagicMock())


def test_validate_experiment_file_not_found():
    with patch("builtins.open", side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError, match="ERROR: File not found"):
            validate_experiment("/nonexistent/path", MagicMock())


def test_validate_experiment_json_decode_error_propagates():
    with patch("builtins.open", mock_open(read_data="not valid json")):
        with patch("src.validation.validate_message"):
            with patch("src.validation.generate_row_schema"):
                with pytest.raises(json.JSONDecodeError):
                    validate_experiment("/fake/path", MagicMock())
