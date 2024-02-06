import json
import time as t
from controller_state import *
from error_helper import *
from mqtt_clients import *


def on_heartbeat_message(client, msg, obj):
    if "heartbeat/sensor/" not in (msg.topic):
        incompatible_request(obj, msg, source="heartbeat")
        return

    p = load_message(msg)
    if p["name"] not in obj.sensors:
        unconfigured_sensor(obj, p["name"])
        return

    obj.sensors[p["name"]]["last_contact"] = t.time()
    obj.sensors[p["name"]]["status"] = p["status"]
    obj.sensors[p["name"]]["setpoint"] = p["setpoint"]
    if obj.status == "awaiting_sensors":
        if p["config"] != obj.sensors[p["name"]]["config"]:
            return
        else:
            obj.sensors[p["name"]]["config"] = p["config"]
        if all([obj.sensors[s]["status"] == "awaiting_setpoint" for s in obj.sensors]):
            obj.sensors["ready"] = True
            pub.publish("controller/ready", json.dumps({"uid": obj.experiment_uid}))
    else:
        obj.sensors[p["name"]]["config"] = p["config"]
