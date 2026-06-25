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


def generate_row_schema():
    # --------------------------------------------------------------------------
    # Load comodo config
    with open("/app/comodo.yaml") as f:
        config = yaml.safe_load(f)

    # --------------------------------------------------------------------------
    # Load template directory
    env = Environment(loader=FileSystemLoader("/app/schemas"))
    template = env.get_template("experiment_schema.yaml.j2")

    # --------------------------------------------------------------------------
    # Fetch instruments and render
    rendered = template.render(instruments=config.get("instruments"))

    # --------------------------------------------------------------------------
    # Write rendered schema to file
    with open("/app/schemas/experiment_row.yaml", "w") as f:
        f.write(rendered)

    return


def validate_experiment(file_path):
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
        generate_row_schema()
    except Exception as e:
        raise ExperimentValidationError(f"Failed to generate row schema: {e}")

    try:
        experiment_dict = json.loads(experiment_json)
        for row in experiment_dict.get("experiment_definition"):
            validate_message(
                "experiment/row", json.dumps(row), schema_name="experiment_row"
            )
    except MQTTValidationException as e:
        raise ExperimentValidationError(f"Experiment row validation failed: {e}")

    # --------------------------------------------------------------------------
    # Return validated dict

    return experiment_dict
