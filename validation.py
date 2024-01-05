import json
import jsonschema
import textwrap

def validate_experiment(experiment_path, schema_path):
    # Get schema
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found - {schema_path}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {schema_path}")
        print(f"{textwrap.indent(str(e),'   ')}")
        exit(1)

    # Get experiment
    try:
        with open(experiment_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found - {experiment_path}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {experiment_path}")
        print(f"{textwrap.indent(str(e),'   ')}")
        exit(1)

    # Validate experiment json against schema
    try:
        jsonschema.validate(instance=data, schema=schema)
        return data
    except jsonschema.ValidationError as e:
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        print(f"Validation errors:")
        for error in errors:
            print(f"\t{error.json_path} -> {error.message}")
        exit(1)
