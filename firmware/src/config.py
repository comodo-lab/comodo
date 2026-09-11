import json
import os

config = {
    "INSTRUMENT_NAME": "No name",
    "FIRMWARE": "None specified",
    "MQTT_USER": "comodo",
    "MQTT_PASS": "comodo",
    "MQTT_HOST": "rabbitmq",
    "HEARTBEAT_INTERVAL": 1000,
    "SIMULATE": True,
    "ADDRESS": "",
    "ACTIVE_VARIABLES": [],
    "DEFAULT_SETPOINTS": {},
    "SAFE_STOP_SETPOINTS": {},
}


def load_config():
    """
    Load the default configuration and override using the environment

    Returns:
        dict: The configuration object
    """
    # Create config dict
    for key, value in config.items():
        # Load booleans
        if key in ["SIMULATE"]:
            config[key] = os.getenv(key, str(value)).lower() in ["true", "1", "yes"]
        # Load lists and dicts
        elif key in ["ACTIVE_VARIABLES", "DEFAULT_SETPOINTS", "SAFE_STOP_SETPOINTS"]:
            loaded = json.loads(os.getenv(key, json.dumps(value)))
            if loaded is None:
                loaded = {}
            config[key] = loaded
        # Load anything else as string
        else:
            config[key] = os.getenv(key, value)
    # Re-pack active_variables with their intervals
    config["sensors"] = []
    for variable in config["ACTIVE_VARIABLES"]:
        # Get the reporting interval
        interval = int(config.get(f"INTERVAL_{variable.upper()}", 1000))
        # Add the variable to the sensors list
        config["sensors"].append({"name": variable, "interval": interval})

    return config
