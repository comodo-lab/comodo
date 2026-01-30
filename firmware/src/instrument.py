import importlib
import pkgutil

class BaseInstrument:
    """
    Base class for all instruments

    This class is used to register all instruments and create them based on the input name.

    Attributes:
    """

    def create_instrument(instrument_name):
        # Dynamically import the instrument module based on the instrument_name (if it exists)
        try:
            module = importlib.import_module(f"src.instruments.{instrument_name}")
        except ModuleNotFoundError as e:
            # List available instrument plugins
            available_instruments = [name for _, name, _ in pkgutil.iter_modules(['instruments'])]
            print(f"Available instruments: {available_instruments}")

            # Raise error
            raise ValueError(f"Unknown instrument plugin: {instrument_name}") from e

        # Instantiate the instrument class from the imported module
        try:
            cls = module.Instrument
            return cls()
        except AttributeError as e:
            raise ValueError(f"Instrument plugin '{instrument_name}' does not have a 'Instrument' class") from e

    def __init__(self):
        """
        Initialisations that are safe when either hardware or simulation is used

        To be extended by subclasses, if needed.
        """
        
        pass

    def initialise(self):
        """
        Initialisations that are only safe when hardware is used
        """
        pass

    def get_measurement(self, state):
        """
        Get a measurement from the instrument
        """
        raise NotImplemented

    def simulate_get_measurement(self, state):
        """
        Get a simulated measurement, default implementation
        """

        setpoint = state.status['setpoint']
        value = state.measurement
        
        if setpoint is None:
            return 0
        
        difference = setpoint - value
        half_diff = difference / 2
            
        measurement = half_diff + value
        
        distance = abs(measurement - state.status["setpoint"])
        if distance < state.status["config"]["tolerance"]:
            state.client.publish(f"instrument/{state.config['INSTRUMENT_ID']}/setpoint_reached", "true")
            
        state.measurement = measurement
        return measurement

    def go_to_setpoint(self, setpoint):
        """
        Go to the setpoint
        """
        raise NotImplemented
    
    def simulate_go_to_setpoint(self, setpoint):
        """
        Go to the setpoint 
        """
        pass
