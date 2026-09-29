import copy
import importlib
from abc import ABC, abstractmethod
from typing import ClassVar


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
        self.initialise()

    def default_sim(self, variable):
        """
        Converges the simulated value toward the setpoint by half the difference each tick.
        May be used in the simulate method of subclasses to provide a default simulation behaviour.
        """
        current = self.previous_measurements.get(variable, 0)
        target = self.setpoints.get(variable)
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
            new_value = self.get_measurement(variable)
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
        self.setpoints[variable] = setpoint
        # If not in simulation mode, instruct the actuators to go to the setpoint.
        if not self.config["SIMULATE"]:
            # Only real actuators are instructed to go to setpoint
            if self.available_variables[variable].get("actuator") is not None:
                self.go_to_setpoint(variable, setpoint)
            elif not variable in self.config["EXTERNAL_ACTUATORS"]:
                print(
                    f"WARNING: No actuator defined for '{variable}'. "
                    "Setpoint stored but not applied to any actuator."
                )

    def print_config(self):
        """
        Return a dictionary representation of the instrument's configuration.
        """
        printable_config = {}
        printable_config["name"] = self.config["INSTRUMENT_NAME"]
        printable_config["firmware"] = self.config["FIRMWARE"]
        printable_config["address"] = self.config["ADDRESS"]
        printable_config["simulate"] = self.config["SIMULATE"]
        printable_config["variables"] = self.config["ACTIVE_VARIABLES"]
        printable_config["default_setpoints"] = self.config["DEFAULT_SETPOINTS"]
        printable_config["safe_stop_setpoints"] = self.config["SAFE_STOP_SETPOINTS"]
        printable_config["measurement_intervals"] = self.config["MEASUREMENT_INTERVALS"]
        printable_config["heartbeat_interval"] = self.config["HEARTBEAT_INTERVAL"]
        printable_config["experiment"] = self.config["experiment"]
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
