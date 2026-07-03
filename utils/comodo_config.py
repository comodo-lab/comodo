import yaml

class ComodoConfig():
    def __init__(self, path="/app/comodo.yaml"):
        # Path to the config file
        self.path = path
        
        # Initialise the instance variables
        self.config = {} # Raw: Parsed yaml config file
        
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
        self.spcs = []
        
        

    def load(self):
        """
        Loads the configuration from a YAML file and populates the instance variables.
        """
        
        # Load the YAML configuration file
        with open(self.path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Populate global parameters
        self.populate_globals()

        # Populate instruments
        self.populate_instruments()

        return self

    def populate_globals(self):
        global_params = self.config.get('global')
        self.globals["heartbeat_interval"] = global_params.get('heartbeat').get('interval')
        self.globals["watchdog_interval"] = global_params.get('watchdog').get('interval')
        self.globals["watchdog_timeout"] = global_params.get('watchdog').get('timeout')
        self.globals["instrument_setup_wait"] = global_params.get('instrument_setup').get('wait')
        
    def populate_instruments(self):
        """
        Populate instruments from the configuration
        Expects to find firmware, address, and variables for each instrument
        """

        instruments_config = self.config.get('instruments', {})
        for instrument_name, instrument_data in instruments_config.items():
            self.instruments[instrument_name] = {
                "firmware": instrument_data.get('firmware', None),
                "address": instrument_data.get('address', None),
            }
            for variable in instrument_data.get('variables', []):
                self.instruments[instrument_name].setdefault('variables', []).append(variable)

