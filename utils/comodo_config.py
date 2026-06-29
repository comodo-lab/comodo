import yaml

class ComodoConfig():
    def __init__(self, path="/app/comodo.yaml"):
        # Path to the config file
        self.path = path
        
        # Initialise the instance variables
        self.config = {} # Raw: Parsed yaml config file
        
        # Global Parameters
        self.heartbeat_interval = None
        self.watchdog_interval = None
        self.watchdog_timeout = None
        self.instrument_setup_wait = None
        
        # Instruments
        self.instruments = {} # Raw: Dict of instrument configurations
        self.expected_instruments = set() # Derived: Set of expected instrument configurations
        self.actuator_instruments = {} # Derived: Instruments with actuator capabilities
        self.sensor_instruments = {} # Derived: Instruments with only sensor capabilities
        
        # Variables
        self.actuator_variables = set() # Derived: Set of actuator variables
        self.sensor_variables = set() # Derived: Set of sensor variables
        self.setpoint_controllers = {} # Derived: Set of Sensor -> Actuator PID pairings

        # Setpoint Controller
        self.spc_config = {} # Raw: Dict of setpoint controller configurations
        
        # Default Experiment
        self.default_experiment = {} # Derived: default setpoints assembled into a single experiment row

    def load_config(self):
        """
        Loads the configuration from a YAML file and populates the instance variables.
        """
        
        # Load the YAML configuration file
        with open(self.path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Populate global parameters
        global_params = self.config.get('global')
        self.heartbeat_interval = global_params.get('heartbeat').get('interval')
        self.watchdog_interval = global_params.get('watchdog').get('interval')
        self.watchdog_timeout = global_params.get('watchdog').get('timeout')
        self.instrument_setup_wait = global_params.get('instrument_setup').get('wait')

        return self


