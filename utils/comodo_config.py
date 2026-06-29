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


