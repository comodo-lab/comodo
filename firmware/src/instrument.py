import importlib


class BaseInstrument:
    """
    Base class for all instruments

    This class is used to register all instruments and create them based on the input name.

    Attributes:
        variables: dict of variable names and parameters
    """

    variables = {}

    def create_instrument(instrument_name):
        try:
            module = importlib.import_module(f"src.instruments.{instrument_name}")
        except ModuleNotFoundError as e:
            raise ValueError(f"Unknown instrument plugin: {instrument_name}") from e

        # Instantiate the instrument class from the imported module
        try:
            cls = module.Instrument
            return cls()
        except AttributeError as e:
            raise ValueError(
                f"Instrument plugin '{instrument_name}' does not have a 'Instrument' class"
            ) from e

    def __init__(self):
        """
        Initialisations that are safe when either hardware or simulation is used

        To be extended by subclasses, if needed.
        """
        pass

    def initialise(self, state):
        """
        Initialisations that are only safe when hardware is used
        """
        pass

    def _default_sim(self, state, variable):
        """
        Default simulation: converge the simulated value toward the setpoint
        by half the difference each tick.
        """
        current = self._simulated.get(variable, 0)
        target = state.status["setpoints"].get(variable)
        if target is not None:
            current += (target - current) / 2
            self._simulated[variable] = current
        return current

    def get_measurement(self, state, variable):
        """
        Get a single measurement from the instrument for a given variable

        Returns:
            float: The measurement value
        """
        raise NotImplemented

    def go_to_setpoint(self, state, variable):
        """
        Set the setpoint for a given variable on the instrument

        Default implementation gates on actuator_param in the variables dict.
        Instruments that support writing should override this method.
        """
        var = self.variables.get(variable)
        if not var or "actuator_param" not in var:
            return
        raise NotImplemented
