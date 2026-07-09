import sys

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
    "DEVICE_ADDRESS": "",
    "ACTIVE_VARIABLES": [],
    "SENSORS": {},
    "HEARTBEAT": {},
}


def load_config():
    """
    Load the default configuration and override using the environmentn

    Returns:
        dict: The configuration object
    """
    # Create config dict
    for key, value in config.items():
        if key in ["SIMULATE"]:
            config[key] = os.getenv(key, str(value)).lower() in ["true", "1", "yes"]
        elif key in ["ACTIVE_VARIABLES"]:
            config[key] = json.loads(os.getenv(key, json.dumps(value)))
        else:
            config[key] = os.getenv(key, value)

    return config

def populate_heartbeat(state):
    """
    Populate the heartbeat object in the config based on the active variables and their intervals.

    Returns:
    """
    
    # Populate the SENSORS list based on ACTIVE_VARIABLES and the instrument's available variables
    for variable in state.config["ACTIVE_VARIABLES"]:
        # Ensure the variable is available in the instrument
        if variable not in state.instrument.available_variables:
            print(f"Warning: Variable '{variable}' is not available in instrument '{state.config['FIRMWARE']}'")
            continue

        # Ensure the variable is a sensor
        if "sensor" not in state.instrument.available_variables[variable]:
            continue

        # Get the reporting interval
        interval = int(state.config.get(f"INTERVAL_{variable.upper()}", 1000))

        # Add the variable to the SENSORS list
        config["SENSORS"][variable] = {
            "name": variable,
            "interval": interval,
        }

    # Create the heartbeat object
    config["HEARTBEAT"] = {
        "firmware": config["FIRMWARE"],
        "device_address": config["DEVICE_ADDRESS"],
        "simulate": config["SIMULATE"],
        "variables": config["ACTIVE_VARIABLES"],
    }
    return
