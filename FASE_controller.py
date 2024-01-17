import time as t
from controller_state import *
from mqtt_clients import *
from on_ui_message import *

# Initialize controller state
state = cstate()

# Load MQTT clients
ui = MQTTClient("ui", on_ui_message, "/ui/#", obj=state)
controller = MQTTClient("controller", on_client_message, topics="/#", obj=state)

while True:
    controller.publish("/controller/heartbeat", f"{state}")
    t.sleep(1)

print(f"Exiting...")
