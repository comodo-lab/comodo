import json
import os

config = {
    "MQTT_USER": "comodo",
    "MQTT_PASS": "comodo",
    "MQTT_HOST": "rabbitmq",
    "INSTRUMENT_NAME": "No name",
    "FIRMWARE": "None specified",
    "ADDRESS": "",
    "SIMULATE": True,
    "ACTIVE_VARIABLES": [],
    "DEFAULT_SETPOINTS": {},
    "SAFE_STOP_SETPOINTS": {},
    "MEASUREMENT_INTERVALS": {},
    "HEARTBEAT_INTERVAL": 1000,
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
        elif key in [
            "ACTIVE_VARIABLES",
            "DEFAULT_SETPOINTS",
            "SAFE_STOP_SETPOINTS",
            "MEASUREMENT_INTERVALS",
        ]:
            loaded = json.loads(os.getenv(key, json.dumps(value)))
            if loaded is None:
                loaded = {}
            config[key] = loaded
        # Load anything else as string
        else:
            config[key] = os.getenv(key, value)

    return config
