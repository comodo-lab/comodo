import json

def load_config():
    """ Load the configuration file from env.json

    Returns:
        dict: The configuration file
    """
    with open("env.json", "r") as f:
        config = json.loads(f.read())
    print(config)
    return config
