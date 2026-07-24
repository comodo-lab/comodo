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


def generate_row_schema(config, output_file="/app/schemas/experiment_row.yaml"):
    # --------------------------------------------------------------------------
    # Empty schema
    schema = {
        "channels": {
            "experimentRow": {
                "address": "experiment/row",
                "messages": {
                    "experimentRow": {
                        "payload": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["time"],
                            "properties": {
                                "time": {
                                    "type": "number",
                                    "minimum": 0,
                                }
                            },
                        }
                    }
                },
            }
        }
    }

    payload = schema["channels"]["experimentRow"]["messages"]["experimentRow"][
        "payload"
    ]

    # --------------------------------------------------------------------------
    # Populate schema with actuator
    try:
        for driving_sensor in [a["driving_sensor"] for a in config.actuators.values()]:
            payload["required"].append(driving_sensor)
            payload["properties"][driving_sensor] = {
                "type": "number",
                "minimum": config.sensors[driving_sensor]["min"],
                "maximum": config.sensors[driving_sensor]["max"],
            }
            payload["properties"][f"{driving_sensor}_profile"] = {
                "type": "string",
                "enum": ["linear", "exponential", "logarithmic", "step"],
            }
    except KeyError as e:
        raise ExperimentValidationError(f"Wrong comodo yaml config: {e}")

    # --------------------------------------------------------------------------
    # Write rendered schema to file
    try:
        with open(output_file, "w") as f:
            yaml.safe_dump(schema, f, sort_keys=False)
    except Exception as e:
        raise ExperimentValidationError(f"Failed to write row schema: {e}")

    return schema


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
