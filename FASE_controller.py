import time as t
from controller_state import *
from mqtt_clients import *
from on_ui_message import *

# Initialize controller state
state = cstate()

# Load MQTT clients
broker_address = "172.28.143.181"
user = "controller"
password = "7C6jX9m4AnYfMAd"
ui = MQTTClient(
    "ui",
    on_ui_message,
    "/ui/#",
    obj=state,
    broker_address=broker_address,
    user=user,
    password=password,
)
controller = MQTTClient(
    "controller",
    on_client_message,
    topics="/#",
    obj=state,
    broker_address=broker_address,
    user=user,
    password=password,
)

heartbeat = MQTTClient("heartbeat", on_client_message, topics="/heartbeat/#")
measurement = MQTTClient("measurement", on_client_message, topics="/measurement/#")

while True:
    controller.publish("/controller/heartbeat", f"{state}")
    t.sleep(1)

print(f"Exiting...")
