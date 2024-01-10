from validation import validate_experiment

experiment_path = "tests/file_fixtures/dummy_experiment.json"
schema_path = "experiment_schema.json"

# Validate experiment json against schema
experiment = validate_experiment(experiment_path, schema_path)

print(f"I am all good!")
