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

        # Populate variables
        self.populate_sensors_actuators_spcs()

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

    def populate_sensors_actuators_spcs(self):
        """
        Populates the sensors and actuators from the configuration.
        Iterates through each instrument and its variables, creating a unique key for each variable in the format "instrument_name/variable_name". Omits any Setpoint Controller linked variables.
        """

        # Build a first pass of sensors and actuators from the instruments and their variables, including SPC linked variables which will be popped later
        instruments_config = self.config.get('instruments', {})
        for instrument_name, instrument_data in instruments_config.items():
            for variable_name, variable_data in instrument_data.get('variables', []).items():
                # Create a unique key for each variable
                key = f"{instrument_name}/{variable_name}"

                # If there is a relevant tag, add the variable to the appropriate dictionary
                if 'sensor' in variable_data:
                    self.sensors[key] = variable_data['sensor'].copy()
                if 'actuator' in variable_data:
                    self.actuators[key] = variable_data['actuator'].copy()

                # If the variable is linked to a Setpoint Controller (SPC), add it to the SPCs dictionary
                if 'setpoint_controller' in variable_data:
                    data = variable_data['setpoint_controller'].copy()
                    data["actuator"] = key
                    self.spcs.append(data)
