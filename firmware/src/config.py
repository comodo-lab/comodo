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
    "SIMULATE": True,
}


def load_config():
    """Load the default configuration and override using the environmentn

    Returns:
        dict: The configuration object
    """
    for key, value in config.items():
        config[key] = os.getenv(key, value)
    return config
