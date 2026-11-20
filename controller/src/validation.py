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


def validate_calibration(variable, calibration):
    """
    Returns the variable's calibration, with missing keys filled in with the defaults
    (no calibration): an offset of 0 and a scaling of 1.
    Raises an ExperimentValidationError if it is not in the form
    {"offset": number, "scaling": number}, with a non-zero scaling.
    """
    expected = 'Expected {"offset": number, "scaling": number}.'
    if not isinstance(calibration, dict):
        raise ExperimentValidationError(
            f"Invalid calibration for '{variable}': {calibration}. {expected}"
        )
    unknown = [key for key in calibration if key not in ["offset", "scaling"]]
    if unknown:
        raise ExperimentValidationError(
            f"Unknown calibration key(s) {', '.join(unknown)} for '{variable}'. {expected}"
        )
    calibration = {"offset": 0, "scaling": 1, **calibration}
    for key, value in calibration.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ExperimentValidationError(
                f"Invalid calibration {key} for '{variable}': {value}. Expected a number."
            )
    if calibration["scaling"] == 0:
        raise ExperimentValidationError(
            f"Invalid calibration scaling for '{variable}': it can't be 0."
        )
    return calibration


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
    # Check the live config is for instruments in comodo.yaml, and their variables.

    instruments_config = experiment_dict["config"].setdefault("instruments", {})
    for instrument_name, instrument_config in instruments_config.items():
        if instrument_name not in config.instruments:
            raise ExperimentValidationError(
                f"Live config for unknown instrument '{instrument_name}'."
            )
        variables = config.instruments[instrument_name]["variables"]
        for key, value in instrument_config.items():
            if key in variables and not isinstance(value, dict):
                raise ExperimentValidationError(
                    f"Invalid live config for variable '{instrument_name}/{key}': "
                    f"{value}. Expected an object."
                )

    # --------------------------------------------------------------------------
    # Validate the calibrations, and complete them with the defaults for every variable.

    for instrument_name, instrument in config.instruments.items():
        instrument_config = instruments_config.setdefault(instrument_name, {})
        for variable in instrument["variables"]:
            variable_config = instrument_config.setdefault(variable, {})
            variable_config["calibration"] = validate_calibration(
                f"{instrument_name}/{variable}", variable_config.get("calibration", {})
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
    # Check the live config has PID values for exactly the SPCs in comodo.yaml

    spcs_config = experiment_dict["config"].get("spcs", {})
    for spc_id in spcs_config:
        if spc_id not in config.spcs:
            raise ExperimentValidationError(
                f"Live config for unknown setpoint controller '{spc_id}'."
            )
    missing = [spc_id for spc_id in config.spcs if spc_id not in spcs_config]
    if missing:
        raise ExperimentValidationError(
            f"Missing PID config for setpoint controller(s) {', '.join(missing)} "
            "in the live config."
        )

    # --------------------------------------------------------------------------
    # Return validated dict

    return experiment_dict
