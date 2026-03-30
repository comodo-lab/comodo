import sys

import json
import os

config = {
    "INSTRUMENT_ID": "No name",
    "FIRMWARE": "None specified",
    "MQTT_USER": "comodo",
    "MQTT_PASS": "comodo",
    "MQTT_HOST": "rabbitmq",
    "HEARTBEAT_INTERVAL": 1000,
    "MEASUREMENT_INTERVAL": 1000,
    "SIMULATE": True
}

def load_config():
    """Load the default configuration and override using the environment

    Returns:
        dict: The configuration object
    """
    for key, value in config.items():
        val = os.getenv(key, value)
        if key == "SIMULATE" and isinstance(val, str):
            val = val.lower() == "true"
        config[key] = val
    
    # Fallback to SIMULATE_SENSORS if SIMULATE is not set or its default
    if os.getenv("SIMULATE_SENSORS"):
        config["SIMULATE"] = os.getenv("SIMULATE_SENSORS").lower() == "true"

    return config
