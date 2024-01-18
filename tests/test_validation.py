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
    with open(valid_experiment_path, "r") as f:
        data = json.load(f)
    return data


@pytest.fixture
def invalid_json():
    return "tests/file_fixtures/invalid_json.json"


@pytest.fixture
def invalid_experiments(valid_experiment):
    invalid_experiments = []

    missing_uid = json.loads(json.dumps(valid_experiment))
    del missing_uid["uid"]
    invalid_experiments.append(json.dumps(missing_uid))

    negative_time = json.loads(json.dumps(valid_experiment))
    negative_time["experiment"][0]["time"] = -1
    invalid_experiments.append(json.dumps(negative_time))

    negative_temperature = json.loads(json.dumps(valid_experiment))
    negative_temperature["experiment"][0]["temperature"] = -1
    invalid_experiments.append(json.dumps(negative_temperature))

    return invalid_experiments


def test_valid_hard(valid_experiment_path, valid_schema_path, valid_experiment):
    experiment = validate_experiment_hard(valid_experiment_path, valid_schema_path)
    assert experiment == valid_experiment


def test_valid(valid_experiment_path, valid_schema_path, valid_experiment):
    experiment = validate_experiment(valid_experiment_path, valid_schema_path)
    assert experiment == valid_experiment


def test_valid_soft(valid_experiment_path, valid_schema_path, valid_experiment):
    experiment, err = validate_experiment_soft(valid_experiment_path, valid_schema_path)
    assert experiment, err == valid_experiment
    assert err is None


def test_invalid_json(valid_experiment_path, valid_schema_path, invalid_json, capsys):
    try:
        experiment = validate_experiment_hard(invalid_json, valid_schema_path)
    except ValidationException as e:
        assert f"Error decoding JSON: {invalid_json}" in e.args[0]
    else:
        assert False, "Should raise error if invalid experiment JSON"
    finally:
        assert "experiment" not in locals()
    try:
        experiment = validate_experiment_hard(valid_experiment_path, invalid_json)
    except ValidationException as e:
        assert f"Error decoding JSON: {invalid_json}" in e.args[0]
    else:
        assert False, "Should raise error if invalid schema JSON"
    finally:
        assert "experiment" not in locals()


def test_invalid_experiment_content(valid_schema_path, invalid_experiments, capsys):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path, "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            try:
                experiment = validate_experiment_hard(
                    invalid_experiment, valid_schema_path
                )
            except ValidationException as e:
                assert f"Validation errors:" in e.args[0]
            else:
                assert False, "Should raise error on invalid experiment config"
            finally:
                assert "experiment" not in locals()


def test_validate_experiment(valid_schema_path, invalid_experiments, capsys):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path, "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            try:
                experiment = validate_experiment(invalid_experiment, valid_schema_path)
            except SystemExit:
                captured = capsys.readouterr()
                assert f"Validation errors:" in captured.out
            else:
                assert False, "Should raise error on invalid experiment config"
            finally:
                assert "experiment" not in locals()


def test_validate_experiment_soft(valid_schema_path, invalid_experiments, capsys):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path, "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            experiment, err = validate_experiment_soft(
                invalid_experiment, valid_schema_path
            )
            assert f"Validation errors:" in err
            assert experiment is None
