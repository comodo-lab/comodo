import json
import os
import yaml
from jinja2 import Environment, FileSystemLoader

from utils import mqtt_validator
from utils.mqtt_validator import validate_message

def generate_row_schema():
    # --------------------------------------------------------------------------
    # Load comodo config 

    with open("/app/comodo.yaml") as f:
        config = yaml.safe_load(f) or {}

    # --------------------------------------------------------------------------
    # Load template directory 

    env = Environment(loader=FileSystemLoader("/app/schemas"))
    template = env.get_template("experiment_schema.yaml.j2")

    # --------------------------------------------------------------------------
    # Fetch instruments and render 

    instruments = config.get("instruments", {})
    rendered = template.render(instruments=instruments)

    # --------------------------------------------------------------------------
    # Write out

    with open("/app/schemas/experiment_row.yaml", "w") as f:
        f.write(rendered)

    return
    try:
        with open(file_path) as f:
            data = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"ERROR: File not found - {file_path}")
    
    # AsyncAPI structural validation 
    try:
        validate_message("ui/start", data) # validate against experiment spec per asyncapi
    except (JSONDecodeError, ValidationError, UnexpectedTopicException) as e:
        raise e    

    # TODO: check acutators against generated experiment config AsyncAPI
    experiment_dict = loads(data)
    return experiment_dict
