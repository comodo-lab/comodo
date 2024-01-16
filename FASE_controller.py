import time as t
from mqtt_clients import *
from controller_state import *

# Initialize controller state
state = cstate()

# Load MQTT clients
controller = MQTTClient("controller", on_controller_message, topics="/#", obj=state)
ui = MQTTClient("ui", on_ui_message, "/ui/#", obj=state)
heartbeat = MQTTClient("heartbeat", on_heartbeat_message, topics="/heartbeat/#")
measurement = MQTTClient("measurement", on_measurement_message, topics="/measurement/#")

while True:
    controller.publish("/controller/heartbeat", f"{state}")
    t.sleep(1)

print(f"Exiting...")
