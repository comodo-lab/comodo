import json
import os
import yaml
from jinja2 import Environment, FileSystemLoader

from utils import mqtt_validator
from utils.mqtt_validator import validate_message, MQTTValidationException


class ExperimentValidationError(Exception):
    """Custom exception for experiment validation errors."""

    def __init__(self, message):
        print(f"Experiment validation error: {message}")
        super().__init__(message)


def generate_row_schema(config):
    # --------------------------------------------------------------------------
    # Load template directory

    try:
        env = Environment(loader=FileSystemLoader("/app/schemas"))
        template = env.get_template("experiment_schema.yaml.j2")
    except FileNotFoundError:
        raise ExperimentValidationError("experiment_schema.yaml.j2 file not found")

    # --------------------------------------------------------------------------
    # Fetch instruments and render
    try:
        instruments = config.raw.get("instruments", {})
        rendered = template.render(instruments=instruments)
    except KeyError as e:
        raise ExperimentValidationError(f"Missing instruments in config: {e}")

    # --------------------------------------------------------------------------
    # Write rendered schema to file
    try:
        with open("/app/schemas/experiment_row.yaml", "w") as f:
            f.write(rendered)
    except Exception as e:
        raise ExperimentValidationError(f"Failed to write rendered schema: {e}")

    return


def validate_experiment(file_path, config):
    # --------------------------------------------------------------------------
    # Read experiment file

    try:
        with open(file_path) as f:
            experiment_json = f.read()
    except FileNotFoundError:
        raise ExperimentValidationError(f"Experiment file not found - {file_path}")

    # --------------------------------------------------------------------------
    # Perform structural validation (is message the right shape)

    try:
        validate_message("ui/start", experiment_json)
    except MQTTValidationException as e:
        raise ExperimentValidationError(f"Experiment validation failed: {e}")

    # --------------------------------------------------------------------------
    # Perform specific validation (compare instruments with comodo.yaml)

    try:
        generate_row_schema(config)
    except Exception as e:
        raise ExperimentValidationError(f"Failed to generate row schema: {e}")

    try:
        experiment_dict = json.loads(experiment_json)
        for row in experiment_dict["experiment_definition"]:
            validate_message(
                "experiment/row", json.dumps(row), schema_name="experiment_row"
            )
    except KeyError as e:
        raise ExperimentValidationError(f"Missing experiment definition: {e}")
    except MQTTValidationException as e:
        raise ExperimentValidationError(f"Experiment row validation failed: {e}")

    # --------------------------------------------------------------------------
    # Return validated dict

    return experiment_dict
