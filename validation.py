from typing import Dict, Any, Optional, Tuple
import json
import jsonschema
import textwrap


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
        raise ValidationException(f"Error: File not found - {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"Error decoding JSON: {schema_path}\n{textwrap.indent(str(e), '   ')}"
        )
    # Get data
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValidationException(f"Error: File not found - {file_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"Error decoding JSON: {file_path}\n{textwrap.indent(str(e), '   ')}"
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
        raise ValidationException(f"Error: File not found - {schema_path}")
    except json.JSONDecodeError as e:
        raise ValidationException(
            f"Error decoding JSON: {schema_path}\n{textwrap.indent(str(e), '   ')}"
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
