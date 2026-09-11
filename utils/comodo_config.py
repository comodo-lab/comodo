import yaml


def find_missing_params(dict_obj, required_params):
    """
    Tries to find required parameters in the given dictionary.
    Required parameters are specified as a list of strings, where each string is a dot-separated path to the parameter in the nested dictionary.
    For example, "global.heartbeat.interval" would look for dict_obj["global"]["heartbeat"]["interval"].

    Returns None if all required parameters are present, otherwise returns string with the concatenated missing parameters.
    """
    missing_params = []
    for param in required_params:
        try:
            # Navigate through the nested dictionary using the dot notation
            keys = param.split(".")
            value = dict_obj
            for k in keys:
                value = value[k]
        except KeyError:
            missing_params.append(param)

    if missing_params == []:
        return None

    if len(missing_params) > 1:
        missing_str = "', '".join(missing_params[:-1])
        missing_str = f"'{missing_str}' and '{missing_params[-1]}' parameters"
    else:
        missing_str = f"'{missing_params[0]}' parameter"
    return missing_str


class ComodoConfig:
    def __init__(self, path="/app/comodo.yaml"):
        # Path to the config file
        self.path = path

        # Initialise the instance variables
        self.raw = {}  # Raw: Parsed yaml config file

        # Global Parameters
        self.globals = {
            "heartbeat_interval": None,
            "watchdog_interval": None,
            "watchdog_timeout": None,
            "instrument_setup_wait": None,
        }

        # Instruments and their variables
        self.instruments = {}
        self.sensors = {}
        self.actuators = {}
        self.spcs = {}

    def load(self):
        """
        Loads the configuration from a YAML file and populates the instance variables.
        """
        # Load the YAML configuration file
        with open(self.path, "r") as f:
            self.raw = yaml.safe_load(f)

        # Populate global parameters
        self.populate_globals()

        # Populate instruments
        self.populate_instruments()

        # Populate variables
        self.populate_sensors_actuators_spcs()

        return self

    def populate_globals(self):
        """
        Populate global parameters from the configuration
        """
        # Check for required global parameters and raise KeyError if any are missing
        req_params = [
            "global.heartbeat.interval",
            "global.watchdog.interval",
            "global.watchdog.timeout",
            "global.instrument_setup.wait",
        ]
        missing_params = find_missing_params(self.raw, req_params)
        if missing_params:
            raise KeyError(f"Missing {missing_params} in configuration.")

        glob = self.raw["global"]
        # Populate the globals dictionary with the values from the configuration
        self.globals["heartbeat_interval"] = glob["heartbeat"]["interval"]
        self.globals["watchdog_interval"] = glob["watchdog"]["interval"]
        self.globals["watchdog_timeout"] = glob["watchdog"]["timeout"]
        self.globals["instrument_setup_wait"] = glob["instrument_setup"]["wait"]

        # Check that all global parameters are positive numbers
        for key, value in self.globals.items():
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(
                    f"Global parameter '{key}' must be a positive number. Found: {value}"
                )

        # Check that the watchdog timeout is greater than the watchdog interval
        if self.globals["watchdog_timeout"] <= self.globals["watchdog_interval"]:
            raise ValueError(
                f"Global parameter 'watchdog_timeout' must be greater than 'watchdog_interval'."
            )

    def populate_instruments(self):
        """
        Populate instruments from the configuration
        Expects to find firmware, address, and variables for each instrument
        """
        try:
            instruments_config = self.raw["instruments"]
        except KeyError:
            raise KeyError(f"Missing 'instruments' section in configuration.")

        for instrument_name, instrument_data in instruments_config.items():
            req_params = ["firmware", "address", "variables"]
            missing_params = find_missing_params(instrument_data, req_params)
            if missing_params:
                raise KeyError(
                    f"Missing {missing_params} for instrument '{instrument_name}' in configuration."
                )
            if len(instrument_data["variables"]) == 0:
                raise ValueError(
                    f"Instrument '{instrument_name}' must have at least one variable defined."
                )

        for instrument_name, instrument_data in instruments_config.items():
            self.instruments[instrument_name] = {
                "firmware": instrument_data["firmware"],
                "address": instrument_data["address"],
                "simulate": instrument_data.get("simulate", False),
                "variables": instrument_data["variables"],
                "default_setpoints": {
                    var_name: var_data["default_setpoint"]
                    for var_name, var_data in instrument_data["variables"].items()
                    if var_data.get("default_setpoint") is not None
                },
                "safe_stop_setpoints": {
                    var_name: var_data["actuator"]["safe_stop_setpoint"]
                    for var_name, var_data in instrument_data["variables"].items()
                    if var_data.get("actuator", {}).get("safe_stop_setpoint")
                    is not None
                },
                "measurement_intervals": {
                    var_name: var_data["sensor"]["interval"]
                    for var_name, var_data in instrument_data["variables"].items()
                    if var_data.get("sensor", {}).get("interval") is not None
                },
            }

    def populate_sensors_actuators_spcs(self):
        """
        Populates the sensors, actuators and setpoint controllers from the configuration.
        Iterates through each instrument and its variables, creating a unique key for each variable in the format "instrument_name/variable_name".
        """
        for instrument_name, instrument_data in self.instruments.items():
            for variable_name, variable_data in instrument_data["variables"].items():
                # Create a unique key for each variable
                var_key = f"{instrument_name}/{variable_name}"

                missing_params = find_missing_params(variable_data, ["min", "max"])
                if missing_params:
                    raise KeyError(
                        f"Missing {missing_params} for variable '{var_key}' in configuration."
                    )

                # If there is a relevant tag, add the variable to the appropriate dictionary
                if "sensor" in variable_data:
                    self.sensors[var_key] = variable_data["sensor"].copy()
                    self.sensors[var_key]["min"] = variable_data["min"]
                    self.sensors[var_key]["max"] = variable_data["max"]
                    if "unit" in variable_data:
                        self.sensors[var_key]["unit"] = variable_data["unit"]
                    if "default_setpoint" in variable_data:
                        self.sensors[var_key]["default_setpoint"] = variable_data[
                            "default_setpoint"
                        ]
                    if "tolerance" in variable_data:
                        self.sensors[var_key]["tolerance"] = variable_data["tolerance"]
                if "actuator" in variable_data:
                    self.actuators[var_key] = variable_data["actuator"].copy()
                    self.actuators[var_key]["driving_sensor"] = var_key
                # If the variable is linked to a Setpoint Controller (SPC), add it to the SPCs dictionary
                if "setpoint_controller" in variable_data:
                    if "actuator" not in variable_data:
                        raise KeyError(
                            "SPC can only be linked to a variable with an 'actuator' in configuration."
                            f" Variable '{var_key}' does not have an 'actuator' defined."
                        )
                    spc_data = variable_data["setpoint_controller"].copy()
                    missing_params = find_missing_params(spc_data, ["external_sensor"])
                    if missing_params:
                        raise KeyError(
                            f"Missing {missing_params} for SPC linked to variable '{var_key}' in configuration."
                        )
                    self.actuators[var_key]["driving_sensor"] = spc_data[
                        "external_sensor"
                    ]
                    spc_data["actuator"] = var_key
                    spc_sensor = spc_data["external_sensor"]
                    spc_id = f"{spc_sensor}--{var_key}".replace("/", "-")
                    self.spcs[spc_id] = spc_data

        # Make sure each actuator has a safe_stop_setpoint, and each driving sensor is defined with a default_setpoint and tolerance
        for actuator_key, actuator_data in self.actuators.items():
            if "safe_stop_setpoint" not in actuator_data:
                raise KeyError(
                    f"Actuator '{actuator_key}' does not have a 'safe_stop_setpoint' defined."
                )
            driving_sensor_key = actuator_data["driving_sensor"]
            if driving_sensor_key not in self.sensors:
                raise KeyError(
                    f"Driving sensor '{driving_sensor_key}' for actuator '{actuator_key}' not found in sensors."
                )
            if "default_setpoint" not in self.sensors[driving_sensor_key]:
                raise KeyError(
                    f"Driving sensor '{driving_sensor_key}' for actuator '{actuator_key}' does not have a 'default_setpoint' defined."
                )
            if "tolerance" not in self.sensors[driving_sensor_key]:
                raise KeyError(
                    f"Driving sensor '{driving_sensor_key}' for actuator '{actuator_key}' does not have a 'tolerance' defined."
                )

    def get_expected_heartbeat(self, instrument_name):
        """
        Returns the expected heartbeat config for a given instrument.
        Constructs the canonical heartbeat config shape from the instrument's
        comodo.yaml data, matching what the firmware should publish.
        """
        try:
            inst = self.instruments[instrument_name]
        except KeyError:
            raise KeyError(
                f"Instrument '{instrument_name}' not found in configuration."
            )

        return {
            "name": instrument_name,
            "firmware": inst["firmware"],
            "address": inst["address"],
            "simulate": inst["simulate"],
            "variables": list(inst["variables"].keys()),
            "default_setpoints": inst["default_setpoints"],
            "safe_stop_setpoints": inst["safe_stop_setpoints"],
            "measurement_intervals": inst["measurement_intervals"],
            "heartbeat_interval": self.globals["heartbeat_interval"] * 1000,
        }

    def get_default_experiment(self):
        """
        Iterates over the actuators to generate the default experiment.
        The experiment is expected to configure the setpoints that drive each actuator.
        For regular actuators, this is the setpoint for the same variable's sensor.
        For SPC controlled actuators, this is the setpoint for the SPC's external sensor.

        Returns a list of dicts with one element, the row for time 0, with the default setpoints and profiles.
        """
        row = {"time": 0}
        for actuator_key, actuator_data in self.actuators.items():
            setpoint_key = actuator_data["driving_sensor"]
            row[setpoint_key] = self.sensors[setpoint_key]["default_setpoint"]
            row[f"{setpoint_key}_profile"] = actuator_data.get("profile", "linear")

        default_experiment = [row]

        return default_experiment
