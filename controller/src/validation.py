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

def validate_experiment(file_path):
    # --------------------------------------------------------------------------
    # Read experiment file
    
    try:
        with open(file_path) as f:
            experiment_json = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"ERROR: File not found - {file_path}")

    # --------------------------------------------------------------------------
    # Perform structural validation (is message the right shape)

    validate_message("ui/start", experiment_json)

    # --------------------------------------------------------------------------
    # Perform specific validation (compare instruments with comodo.yaml)

    generate_row_schema()

    experiment_dict = json.loads(experiment_json)
    for row in experiment_dict.get("experiment_definition"):
        validate_message(
            "experiment/row",
            json.dumps(row),
            schema_name="experiment_row"
        )

    # --------------------------------------------------------------------------
    # Return validated dict

    return experiment_dict
