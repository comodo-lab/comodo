import json
from validation import *
import pytest
from unittest.mock import mock_open, patch


@pytest.fixture
def valid_experiment_path():
    return "tests/file_fixtures/dummy_experiment.json"

@pytest.fixture
def valid_schema_path():
    return "experiment_schema.json"

@pytest.fixture
def valid_experiment(valid_experiment_path):
    with open(valid_experiment_path, 'r') as f:
            data = json.load(f)
    return data

@pytest.fixture
def invalid_json():
    return "tests/file_fixtures/invalid_json.json"

@pytest.fixture
def invalid_experiment(valid_experiment):
    valid_experiment["experiment"][0]["time"]=-1
    return json.dumps(valid_experiment)

def test_valid(valid_experiment_path, valid_schema_path,valid_experiment):
    experiment = validate_experiment(valid_experiment_path, valid_schema_path)
    assert experiment == valid_experiment

def test_invalid_json(valid_experiment_path, valid_schema_path, invalid_json,capsys):
    try:
        experiment = validate_experiment(invalid_json, valid_schema_path)
    except SystemExit:
        captured = capsys.readouterr()
        assert f"Error decoding JSON: {invalid_json}" in captured.out
    finally:
        assert 'experiment' not in locals()
    try:
        experiment = validate_experiment(valid_experiment_path,invalid_json)
    except SystemExit:
        captured = capsys.readouterr()
        assert f"Error decoding JSON: {invalid_json}" in captured.out
    finally:
        assert 'experiment' not in locals()

def test_invalid_experiment_content(valid_schema_path, invalid_experiment,capsys):
    with patch("builtins.open", side_effect=[open(valid_schema_path, 'r'),
                                             mock_open(read_data=invalid_experiment).return_value]):
        try:
            experiment = validate_experiment(invalid_experiment, valid_schema_path)
        except SystemExit:
            captured = capsys.readouterr()
            assert f"Validation errors:" in captured.out
        finally:
            assert 'experiment' not in locals()
