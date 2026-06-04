from typing import Dict, Any, Optional, Tuple
import json
import jsonschema
import textwrap

from utils.message_spec import load_spec as load_message_spec


_EXPERIMENT_SCHEMA = None


def _get_experiment_schema():
    global _EXPERIMENT_SCHEMA
    if _EXPERIMENT_SCHEMA is None:
        _EXPERIMENT_SCHEMA = load_message_spec(
            "/app/messageSpec.yaml"
        )["ui/start"]["schema"]
    return _EXPERIMENT_SCHEMA


class ValidationException(Exception):
    """
    Custom exception class for validation errors.
    """


def validate_file(file_path: str, schema_path: str) -> Dict[str, Any]:
    """
    Validates a JSON file against a schema, and raises a ValidationException if there are any errors.

    Args:
        file_path: The path to the JSON file.
        schema_path: The path to the schema JSON file.

    Returns:
        The validated data from the loaded json.
    """
    # Get schema
    try:
        with open(schema_path, "r") as f:
            schema = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"ERROR: File not found - {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"ERROR: Cannot decode JSON: {schema_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Get data
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"ERROR: File not found - {file_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"ERROR: Cannot decode JSON: {file_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Validate json data against schema
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


def validate_file_print_errors(file_path: str, schema_path: str) -> Dict[str, Any]:
    """
    Uses validate_file to validate a JSON file against a schema.
    Instead of raising an exception, it prints a more human friendly message to the console and exits the program.

    Args:
        file_path: The path to the JSON file.
        schema_path: The path to the schema JSON file.

    Returns:
        The validated data from the loaded json.
    """
    try:
        data = validate_file(file_path, schema_path)
        return data
    except ValidationException as e:
        print(e.args[0])
        exit(1)


def validate_file_soft(
    file_path: str, schema_path: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Uses validate_file to validate a JSON file against a schema.
    Instead of raising an exception, it returns any validation error messages in a tuple.

    Args:
        file_path: The path to the JSON file.
        schema_path: The path to the schema JSON file.

    Returns:
        A tuple containing the validated data from the loaded json and any validation error message.
        If the validation is successful, the tuple will be: data,None
        If there is a validation error, the tuple will be: None,errors
    """
    try:
        data = validate_file(file_path, schema_path)
        return data, None
    except ValidationException as e:
        return None, str(e.args[0])


def validate_experiment_dict(data: Dict[str, Any], actuator_variables: set) -> Dict[str, Any]:
    """
    Validates experiment data structure and actuator completeness.

    Structural validation is performed against the AsyncAPI-derived schema
    from messageSpec.yaml. Additional checks enforce non-empty experiment
    definition, numeric non-negative time per row, and exhaustive actuator
    coverage (every column maps to a known actuator, every actuator appears).

    Args:
        data: The experiment data dict.
        actuator_variables: Set of valid actuator variable identifiers (e.g. "furnace_centre/temperature").

    Returns:
        The validated data dict.

    Raises:
        ValidationException: If any validation check fails.
    """
    # AsyncAPI structural validation (id, config, experiment_definition types and required fields)
    try:
        jsonschema.validate(data, _get_experiment_schema())
    except jsonschema.ValidationError as e:
        raise ValidationException(str(e))

    exp_def = data.get("experiment_definition", [])

    # Additional: non-empty (AsyncAPI schema allows zero-length arrays)
    if not exp_def:
        raise ValidationException("Experiment must have a non-empty 'experiment_definition' array")

    # Additional: each row must have numeric non-negative time
    for i, row in enumerate(exp_def):
        time_val = row.get("time")
        if not isinstance(time_val, (int, float)):
            raise ValidationException(
                f"Row {i} in experiment_definition must have a numeric 'time' key"
            )
        if time_val < 0:
            raise ValidationException(f"Row {i} in experiment_definition has negative 'time'")

    # Collect all non-time columns across all rows
    columns = set()
    for row in exp_def:
        for key in row:
            if key != "time":
                columns.add(key)

    # Check all columns are known actuator variables
    for col in columns:
        if col not in actuator_variables:
            raise ValidationException(
                f"Column '{col}' is not a known actuator variable. "
                f"Valid actuators: {sorted(actuator_variables)}"
            )

    # Check every actuator is present in the experiment columns
    missing = actuator_variables - columns
    if missing:
        raise ValidationException(
            f"Actuator(s) missing from experiment columns: {sorted(missing)}"
        )

    return data


def validate_experiment_file(file_path: str, actuator_variables: set) -> Dict[str, Any]:
    """
    Loads and validates an experiment JSON file against actuator-based validation.

    Args:
        file_path: Path to the experiment JSON file.
        actuator_variables: Set of valid actuator variable identifiers.

    Returns:
        The validated data dict.

    Raises:
        ValidationException: If file cannot be loaded or validation fails.
    """
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"ERROR: File not found - {file_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"ERROR: Cannot decode JSON: {file_path}\n{textwrap.indent(str(e), '   ')}"
        )
    return validate_experiment_dict(data, actuator_variables)


def validate_dict(dict_to_validate: Dict[str, Any], schema_path: str) -> Dict[str, Any]:
    """
    Validates a pre-loaded dict against a schema, and raises a ValidationException if there are any errors.

    Args:
        dict_to_validate: The dict object to validate.
        schema_path: The path to the schema JSON file.

    Returns:
        The validated dict.
    """
    # Get schema
    try:
        with open(schema_path, "r") as f:
            schema = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"ERROR: File not found - {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"ERROR: Cannot decode JSON: {schema_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Validate dict against schema
    try:
        jsonschema.validate(instance=dict_to_validate, schema=schema)
        return dict_to_validate
    except jsonschema.ValidationError as e:
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(dict_to_validate))
        raise ValidationException(
            f"Validation errors:\n"
            + "\n".join([f"\t{error.json_path} -> {error.message}" for error in errors])
        )
