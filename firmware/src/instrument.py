import copy
import importlib
from abc import ABC, abstractmethod
from typing import ClassVar

import utils.mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val


def create_instrument(config):
    firmware = config["FIRMWARE"]
    if config["FIRMWARE"] == "generic_instrument" or not firmware:
        return GenericInstrument(config)

    # Import firmware module
    module_name = f"src.instruments.{firmware}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name == module_name:
            raise ValueError(f"Unknown instrument plugin: {firmware}") from e
        raise
    # Instantiate the instrument class from the imported module
    try:
        cls = module.Instrument
    except AttributeError as e:
        raise ValueError(
            f"Instrument plugin '{firmware}' does not have an 'Instrument' class"
        ) from e
    return cls(config)


class BaseInstrument(ABC):
    """
    Abstract base class for instruments.
    """

    # Available variables for the instrument, with their corresponding sensor and actuator parameters
    available_variables: ClassVar[dict[str, dict]] = {}

    def __init__(self, config):
        """
        Generic initialisation of all instruments. Subclasses should not override this method.
        Specific initialisation must be defined by subclasses in the initialise method.
        """
        self.config = config
        # Copy the class-level defaults so instances don't share (and mutate) a single dict.
        self.available_variables = copy.deepcopy(self.available_variables)
        self.setpoints = {var: None for var in self.config["DEFAULT_SETPOINTS"]}
        self.previous_measurements = {}
        self.load_live_config({})  # Sets default calibration
        if config["SIMULATE"] and config["EXTERNAL_ACTUATORS"]:
            self.ext_client = self.external_measurements_client()

        self.initialise()

    def external_measurement_cb(self, _client, msg, _obj=None):
        """
        Callback function to handle external sensor measurements.
        This function is called when a new measurement is received from an external sensor.
        """
        # Extract instrument/variable from topic
        _, ins, var, _ = msg.topic.split("/")
        params = mqtt_val.validate_message(msg.topic, msg.payload)
        measurement = params.get("value")
        self.previous_measurements[f"{ins}/{var}"] = measurement

    def external_measurements_client(self):
        """
        Creates a client subscribed to the external sensor measurements, which saves them
        into the previous_measurements dictionary.
        """
        topics = [
            f"instruments/{instrument_variable}/measurement"
            for instrument_variable in self.config["EXTERNAL_ACTUATORS"].values()
        ]
        return mqtt.MQTTClient(
            id=f"{self.config['INSTRUMENT_NAME']}_external",
            callback=self.external_measurement_cb,
            topics=topics,
            broker_address=self.config["MQTT_HOST"],
            user=self.config["MQTT_USER"],
            password=self.config["MQTT_PASS"],
            connection_timeout=60,
        )

    def default_sim(self, variable):
        """
        Converges the simulated value toward the setpoint by half the difference each tick.
        May be used in the simulate method of subclasses to provide a default simulation behaviour.
        """
        current = self.previous_measurements.get(variable, 0)
        target = self.setpoints.get(variable)
        if variable in self.config["EXTERNAL_ACTUATORS"]:
            ext_var = self.config["EXTERNAL_ACTUATORS"][variable]
            ext_value = self.previous_measurements.get(ext_var, 0)
            variable_base = 1  # Settling value at 0% of the external actuator
            variable_max = 200  # Settling value at 100% of the external actuator
            variable_gain = (variable_max - variable_base) / 100
            target = variable_base + variable_gain * ext_value
        if target is not None:
            new = current + (target - current) / 2
        else:
            new = current
        return new

    def measure_or_simulate(self, variable):
        """
        Get a measurement from the instrument or simulate the measurement if in simulation mode.
        Subclasses should not override this method, but should implement the `get_measurement` and
        `simulate` methods to provide specific behaviour.
        """
        # Only allow measuring variables that are available in the instrument.
        if variable not in self.available_variables:
            raise ValueError(
                f"Cannot measure '{variable}'. "
                "Variable not available in this instrument."
            )
        if self.config["SIMULATE"]:
            new_value = self.simulate(variable)
        else:
            raw_value = self.get_measurement(variable)
            new_value = self.calibrate(variable, raw_value)
        self.previous_measurements[variable] = new_value
        return new_value

    def set_and_go_to_setpoint(self, variable, setpoint):
        """
        Set the setpoint for a given variable and instruct actuators to go to that setpoint (if any).
        Subclasses should not override this method, but should implement the `go_to_setpoint` method
        to provide specific behaviour.
        """
        # Only allow setting setpoints for variables that are available in the instrument.
        if variable not in self.available_variables:
            raise ValueError(
                f"Cannot set setpoint for '{variable}'. "
                "Variable not available in this instrument."
            )
        # Reject setpoints outside the variable's range
        variable_range = self.config["VARIABLE_RANGES"].get(variable)
        if variable_range and not (
            variable_range["min"] <= setpoint <= variable_range["max"]
        ):
            raise ValueError(
                f"Setpoint {setpoint} for '{variable}' is outside its range "
                f"({variable_range['min']} to {variable_range['max']})."
            )
        self.setpoints[variable] = setpoint
        # If not in simulation mode, instruct the actuators to go to the setpoint.
        if not self.config["SIMULATE"]:
            # Only real actuators are instructed to go to setpoint
            if self.available_variables[variable].get("actuator") is not None:
                self.go_to_setpoint(variable, self.anti_calibrate(variable, setpoint))
            elif not variable in self.config["EXTERNAL_ACTUATORS"]:
                print(
                    f"WARNING: No actuator defined for '{variable}'. "
                    "Setpoint stored but not applied to any actuator."
                )

    def load_live_config(self, live_config):
        """
        Saves the live config (sent by the controller before an experiment) under `experiment`,
        where it is reported in the heartbeat. Each variable's calibration is completed with the defaults
        (an offset of 0 and a scaling of 1).

        Returns False (saving nothing) if a calibration has a value that is not a number,
        or a scaling of 0. Returns True otherwise.
        """
        live_config = dict(live_config)
        for var in self.config["ACTIVE_VARIABLES"]:
            variable_config = live_config.get(var, {})
            calibration = variable_config.get("calibration", {})
            # Check for invalid values
            for key, value in calibration.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    print(f"ERROR: Invalid calibration {key} for '{var}': {value}.")
                    return False
            if calibration.get("scaling") == 0:
                print(f"ERROR: Invalid calibration for '{var}': scaling is 0.")
                return False
            # Add defaults if missing
            live_config[var] = {
                **variable_config,
                "calibration": {
                    "offset": calibration.get("offset", 0),
                    "scaling": calibration.get("scaling", 1),
                },
            }
        # Save the rest of the config as passed
        for key, value in live_config.items():
            self.config["experiment"][key] = value

        return True

    def calibrate(self, variable, value):
        """
        Returns the calibrated value of a real measurement: `offset + scaling * value`.
        Non-numeric measurements (e.g. None, for a failed measurement) are returned as they are.
        """
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return value
        calibration = self.config["experiment"][variable]["calibration"]
        return calibration["offset"] + calibration["scaling"] * value

    def anti_calibrate(self, variable, setpoint):
        """
        Reverses the calibration for a given variable and setpoint.
        A sensor at such setpoint will then read the original setpoint after calibration.
        """
        calibration = self.config["experiment"][variable]["calibration"]
        return (setpoint - calibration["offset"]) / calibration["scaling"]

    def print_config(self):
        """
        Return a dictionary representation of the instrument's configuration.
        """
        printable_config = {}
        except_keys = ["MQTT_USER", "MQTT_PASS", "MQTT_HOST"]
        rename_keys = {"INSTRUMENT_NAME": "name", "ACTIVE_VARIABLES": "variables"}
        for key, value in self.config.items():
            if key not in except_keys:
                new_key = rename_keys.get(key, key.lower())
                printable_config[new_key] = value
        return printable_config

    @abstractmethod
    def initialise(self):
        """
        Initialise the instrument
        """

    @abstractmethod
    def simulate(self, variable):
        """
        Simulate the instrument approach to a setpoint for a given variable.
        For default simulation behaviour, subclasses can call the `default_sim` method.
        """

    @abstractmethod
    def get_measurement(self, variable):
        """
        Get a single measurement from the instrument for a given variable

        Returns:
            float: The measurement value
        """

    @abstractmethod
    def go_to_setpoint(self, variable, setpoint):
        """
        Set the setpoint for a given variable on the instrument.
        """


class GenericInstrument(BaseInstrument):
    """
    A generic instrument class that can be used for simulation purposes.
    It accepts any variable passed to it and simulates the behaviour of an instrument.
    """

    def initialise(self):
        # Make sure the instrument is in simulation mode.
        if not self.config["SIMULATE"]:
            raise ValueError("GenericInstrument must be used in simulation mode.")
        # Accept any variable passed in the configuration.
        for var in self.config.get("ACTIVE_VARIABLES", []):
            self.available_variables[var] = {"sensor": None, "actuator": None}

    def simulate(self, variable):
        # Use the default simulation behaviour to converge towards the setpoint.
        return self.default_sim(variable)

    def get_measurement(self, variable):
        raise NotImplementedError(
            f"GenericInstrument cannot provide a real measurement for {variable}. "
            "Please use a specific instrument subclass."
        )

    def go_to_setpoint(self, variable, setpoint):
        raise NotImplementedError(
            f"GenericInstrument cannot set a real setpoint for {variable}. "
            "Please use a specific instrument subclass."
        )
