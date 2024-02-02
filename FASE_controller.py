import time as t
from controller_state import *
from mqtt_clients import *
from on_ui_message import *
from on_controller_message import *
from on_heartbeat_message import *


# Initialize controller state
state = cstate()

# Load MQTT clients
ui = MQTTClient(
    id="ui",
    callback=on_ui_message,
    topics="ui/#",
    obj=state,
    broker_address=broker_address,
    user=user,
    password=password,
)
controller = MQTTClient(
    id="controller",
    callback=c_idle,
    topics="controller/#",
    obj=state,
    broker_address=broker_address,
    user=user,
    password=password,
)

heartbeat = MQTTClient(
    id="heartbeat",
    callback=on_heartbeat_message,
    topics="heartbeat/sensor/#",
    obj=state,
    broker_address=broker_address,
    user=user,
    password=password,
)
measurement = MQTTClient("measurement", on_client_message, topics="measurement/#")

while True:
    pub.publish("heartbeat/controller", f"{state}")
    t.sleep(1)

print(f"Exiting...")
