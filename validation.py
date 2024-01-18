from typing import Dict, Any, Optional, Tuple
import json
import jsonschema
import textwrap


class ValidationException(Exception):
    """
    Custom exception class for validation errors.
    """


def validate_experiment_hard(experiment_path: str, schema_path: str) -> Dict[str, Any]:
    """
    Validates an experiment JSON file against a schema, and raises a ValidationException if there are any errors.

    Args:
        experiment_path: The path to the experiment JSON file.
        schema_path: The path to the schema JSON file.

    Returns:
        The validated experiment data.
    """
    # Get schema
    try:
        with open(schema_path, "r") as f:
            schema = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"Error: File not found - {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"Error decoding JSON: {schema_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Get experiment
    try:
        with open(experiment_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"Error: File not found - {experiment_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"Error decoding JSON: {experiment_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Validate experiment json against schema
    try:
        jsonschema.validate(instance=data, schema=schema)
        return data
    except jsonschema.ValidationError as e:
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        raise ValidationException(
            f"Validation errors:\n"
            + "\n".join([f"\t{error.json_path} -> {error.message}" for error in errors])
        )


def validate_experiment(experiment_path: str, schema_path: str) -> Dict[str, Any]:
    """
    Uses validate_experiment_hard to validate an experiment JSON file against a schema.
    Instead of raising an exception, it prints a more human friendly message to the console and exits the program.

    Args:
        experiment_path: The path to the experiment JSON file.
        schema_path: The path to the schema JSON file.

    Returns:
        The validated experiment data.
    """
    try:
        exp_config = validate_experiment_hard(experiment_path, schema_path)
        return exp_config
    except ValidationException as e:
        print(e.args[0])
        exit(1)


def validate_experiment_soft(
    experiment_path: str, schema_path: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Uses validate_experiment_hard to validate an experiment JSON file against a schema.
    Instead of raising an exception, it returns any validation error messages in a tuple.

    Args:
        experiment_path: The path to the experiment configuration file.
        schema_path: The path to the schema file.

    Returns:
        A tuple containing the validated experiment configuration and any validation error message.
        If the validation is successful, the experiment configuration is returned along with None.
        If there is a validation error, None is returned along with the error message.
    """
    try:
        exp_config = validate_experiment_hard(experiment_path, schema_path)
        return exp_config, None
    except ValidationException as e:
        return None, str(e.args[0])
