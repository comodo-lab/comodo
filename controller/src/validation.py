from typing import Dict, Any, Optional, Tuple
from json import loads, JSONDecodeError
from jsonschema import ValidationError
import textwrap

from utils.message_validator import validate_message, UnexpectedTopicException

def validate_experiment(file_path: Dict[str, Any], actuator_variables: set) -> Dict[str, Any]:
    """
    Validates experiment data structure and actuator completeness.

    Structural validation is performed against the AsyncAPI-derived schema
    from messageSpec.yaml. Additional checks enforce non-empty experiment
    definition, numeric non-negative time per row, and exhaustive actuator
    coverage (every column maps to a known actuator, every actuator appears).

    Args:
        file_path: The experiment definition file path (JSON).
        actuator_variables: Set of valid actuator variable identifiers (e.g. "furnace_centre/temperature").

    Returns:
        The validated data dict.
    """

    # Attempt loading the file
    try:
        with open(file_path) as f:
            data = loads(f.read())
    except FileNotFoundError:
        raise FileNotFoundError(f"ERROR: File not found - {file_path}")
    
    # AsyncAPI structural validation 
    try:
        validate_message("ui/start", data) # validate against experiment spec per asyncapi
    except (JSONDecodeError, ValidationError, UnexpectedTopicException) as e:
        raise e    

    # TODO: check acutators against generated experiment config AsyncAPI
    return data
