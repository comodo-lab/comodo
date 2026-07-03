import yaml

class ComodoConfig():
    def __init__(self, path="/app/comodo.yaml"):
        # Path to the config file
        self.path = path

        # Initialise the instance variables
        self.raw = {} # Raw: Parsed yaml config file
        
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

        global_params = self.raw.get('global')

        self.globals["heartbeat_interval"] = global_params.get('heartbeat').get('interval')
        self.globals["watchdog_interval"] = global_params.get('watchdog').get('interval')
        self.globals["watchdog_timeout"] = global_params.get('watchdog').get('timeout')
        self.globals["instrument_setup_wait"] = global_params.get('instrument_setup').get('wait')

        # Check that all global parameters are positive numbers
        for key, value in self.globals.items():
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"Global parameter '{key}' must be a positive number. Found: {value}")

        # Check that the watchdog timeout is greater than the watchdog interval
        if self.globals["watchdog_timeout"] <= self.globals["watchdog_interval"]:
            raise ValueError(f"Global parameter 'watchdog_timeout' must be greater than 'watchdog_interval'.")

    def populate_instruments(self):
        """
        Populate instruments from the configuration
        Expects to find firmware, address, and variables for each instrument
        """

        instruments_config = self.raw.get('instruments', {})
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
        instruments_config = self.raw.get('instruments', {})
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

    def get_default_experiment(self):
        """
        Returns the default experiment configuration.
        """

        # Iterate over the actuator's, get their default setpoints and return a dictionary of the default experiment
        default_experiment = [{'time': 0}]
        for actuator_key, actuator_data in self.actuators.items():
            default_experiment[0][actuator_key] = actuator_data.get('default_setpoint', None)

            # Add the profile (default linear)
            default_experiment[0][f'{actuator_key}_profile'] = 'linear'

        return default_experiment
