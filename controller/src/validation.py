import json
import jsonschema

import utils.mqtt_validator as mqtt_val


class ExperimentValidationError(Exception):
    """Custom exception for experiment validation errors."""

    def __init__(self, message):
        print(f"Experiment validation error: {message}")
        super().__init__(message)


def generate_row_schema(config):
    # --------------------------------------------------------------------------
    # Empty schema
    json_schema = {
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

    # --------------------------------------------------------------------------
    # Populate schema with actuator
    try:
        for driving_sensor in [a["driving_sensor"] for a in config.actuators.values()]:
            json_schema["required"].append(driving_sensor)
            json_schema["properties"][driving_sensor] = {
                "type": "number",
                "minimum": config.sensors[driving_sensor]["min"],
                "maximum": config.sensors[driving_sensor]["max"],
            }
            json_schema["properties"][f"{driving_sensor}_profile"] = {
                "type": "string",
                "enum": ["linear", "exponential", "logarithmic", "step"],
            }
    except KeyError as e:
        raise ExperimentValidationError(f"Wrong comodo yaml config: {e}")

    return json_schema


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
        mqtt_val.validate_message("ui/start", experiment_json)
    except mqtt_val.MQTTValidationException as e:
        raise ExperimentValidationError(f"Experiment validation failed: {e}")

    # --------------------------------------------------------------------------
    # Perform specific validation (compare instruments with comodo.yaml)

    json_schema = generate_row_schema(config)

    try:
        experiment_dict = json.loads(experiment_json)
        for row in experiment_dict["experiment_definition"]:
            jsonschema.validate(row, json_schema)
    except KeyError as e:
        raise ExperimentValidationError(f"Missing experiment definition: {e}")
    except jsonschema.ValidationError as e:
        raise ExperimentValidationError(f"Experiment row validation failed: {e}")

    # --------------------------------------------------------------------------
    # Check the live config is for instruments in comodo.yaml

    instruments_config = experiment_dict["config"].get("instruments", {})
    for instrument_name in instruments_config:
        if instrument_name not in config.instruments:
            raise ExperimentValidationError(
                f"Live config for unknown instrument '{instrument_name}'."
            )

    # --------------------------------------------------------------------------
    # Make sure all driving variables in the experiment have a tolerance defined in the live config

    for driving_sensor in [a["driving_sensor"] for a in config.actuators.values()]:
        instrument_name, variable = driving_sensor.split("/")
        tolerance = (
            instruments_config.get(instrument_name, {})
            .get(variable, {})
            .get("tolerance")
        )
        if not isinstance(tolerance, (int, float)):
            raise ExperimentValidationError(
                f"Missing tolerance for '{driving_sensor}' in the live config."
            )

    # --------------------------------------------------------------------------
    # Return validated dict

    return experiment_dict
