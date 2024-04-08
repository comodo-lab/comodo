import json
import pytest
from unittest.mock import mock_open, patch

from tests.tests_helper import *

from validation import *


@pytest.fixture
def invalid_experiments():
    invalid_experiments = []

    missing_uid = valid_experiment_dict()
    del missing_uid["uid"]
    invalid_experiments.append(json.dumps(missing_uid))

    negative_time = valid_experiment_dict()
    negative_time["experiment"][0]["time"] = -1
    invalid_experiments.append(json.dumps(negative_time))

    negative_temperature = valid_experiment_dict()
    negative_temperature["experiment"][0]["temperature"] = -1
    invalid_experiments.append(json.dumps(negative_temperature))

    return invalid_experiments


def test_valid_hard():
    experiment = validate_file(valid_experiment_path(), valid_schema_path())
    assert experiment == valid_experiment_dict()


def test_valid():
    experiment = validate_file_print_errors(
        valid_experiment_path(), valid_schema_path()
    )
    assert experiment == valid_experiment_dict()


def test_valid_soft():
    experiment, err = validate_file_soft(valid_experiment_path(), valid_schema_path())
    assert experiment, err == valid_experiment_dict()
    assert err is None


def test_invalid_json():
    try:
        experiment = validate_file(invalid_json_path(), valid_schema_path())
    except ValidationException as e:
        assert f"Error decoding JSON: {invalid_json_path()}" in e.args[0]
    else:
        assert False, "Should raise error if invalid experiment JSON"
    finally:
        assert "experiment" not in locals()
    try:
        experiment = validate_file(valid_experiment_path(), invalid_json_path())
    except ValidationException as e:
        assert f"Error decoding JSON: {invalid_json_path()}" in e.args[0]
    else:
        assert False, "Should raise error if invalid schema JSON"
    finally:
        assert "experiment" not in locals()


def test_invalid_experiment_content(invalid_experiments):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path(), "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            try:
                experiment = validate_file(invalid_experiment, valid_schema_path())
            except ValidationException as e:
                assert f"Validation errors:" in e.args[0]
            else:
                assert False, "Should raise error on invalid experiment config"
            finally:
                assert "experiment" not in locals()


def test_validate_file_print_errors(invalid_experiments, capsys):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path(), "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            try:
                experiment = validate_file_print_errors(
                    invalid_experiment, valid_schema_path()
                )
            except SystemExit:
                captured = capsys.readouterr()
                assert f"Validation errors:" in captured.out
            else:
                assert False, "Should raise error on invalid experiment config"
            finally:
                assert "experiment" not in locals()


def test_validate_file_soft(invalid_experiments):
    for invalid_experiment in invalid_experiments:
        with patch(
            "builtins.open",
            side_effect=[
                open(valid_schema_path(), "r"),
                mock_open(read_data=invalid_experiment).return_value,
            ],
        ):
            experiment, err = validate_file_soft(
                invalid_experiment, valid_schema_path()
            )
            assert f"Validation errors:" in err
            assert experiment is None
