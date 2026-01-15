import sys

board = sys.platform
if board == "rp2":
    # Micropython imports
    import ujson as json
elif board == "linux":
    # Python imports
    import json
import os


def load_config():
    """Load the configuration file from env.json

    Returns:
        dict: The configuration file
    """
    with open("env.json", "r") as f:
        config = json.loads(f.read())

        for key, value in config.items():
            config[key] = os.getenv(key, value)

    return config
