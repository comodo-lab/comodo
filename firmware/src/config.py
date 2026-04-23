import sys
import json
import os

DEFAULT_CONFIG = {
    "INSTRUMENT_ID": "No name",
    "FIRMWARE": "None specified",
    "MQTT_USER": "comodo",
    "MQTT_PASS": "comodo",
    "MQTT_HOST": "rabbitmq",
    "HEARTBEAT_INTERVAL": 1000,
    "MEASUREMENT_INTERVAL": 1000,
    "SIMULATE": False,
    "DEVICE_ADDRESS": None,
    "TEMPERATURE_SCALE": None,
    "TEMPERATURE_READ_SCALE": None,
    "TEMPERATURE_WRITE_SCALE": None
}

def load_config():
    """Load the default configuration and override using the environment

    Returns:
        dict: The configuration object
    """
    config = DEFAULT_CONFIG.copy()
    for key in config:
        val = os.getenv(key)
        if val is not None:
            if key == "SIMULATE":
                val = val.lower() == "true"
            config[key] = val
    
    # Fallback to SIMULATE_SENSORS if SIMULATE is not set or its default
    if os.getenv("SIMULATE_SENSORS"):
        config["SIMULATE"] = os.getenv("SIMULATE_SENSORS").lower() == "true"

    return config
