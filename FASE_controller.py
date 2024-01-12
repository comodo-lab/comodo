from validation import validate_experiment
from mqtt_clients import *
from controller_state import *
import json

experiment_path = "tests/file_fixtures/dummy_experiment.json"
schema_path = "experiment_schema.json"

# Initialize controller state
state = cstate()

# Load MQTT clients
controller = MQTTClient("controller", on_controller_message, topics="/#", obj=state)
ui = MQTTClient("ui", on_ui_message, "/ui/#", obj=state)
heartbeat = MQTTClient("heartbeat", on_heartbeat_message, topics="/heartbeat/#")
measurement = MQTTClient("measurement", on_measurement_message, topics="/measurement/#")

# Validate experiment json against schema
experiment = validate_experiment(experiment_path, schema_path)

while True:
    controller.publish("/controller", f"{state}")
    t.sleep(1)

print(f"Exiting...")
