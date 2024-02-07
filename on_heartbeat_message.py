import json
import time as t
from controller_state import *
from error_helper import *
from mqtt_clients import *


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a sensor.
    It expects a message with the structure:
    {
        "name": "sensor_name",          # string
        "status": "sensor_status",      # "awaiting_config", "awaiting_setpoint", "adjusting", "ready", "error"
        "setpoint": "sensor_setpoint",  # float
        "config": { "p": float, "i": float, "d": float, "tolerance": float }
    }
    """
    if "heartbeat/sensor/" not in (msg.topic):
        incompatible_request(obj, msg, source="heartbeat")
        return

    try:
        p = load_message(msg)
        s_name = p["name"]
        s_status = p["status"]
        s_setpoint = p["setpoint"]
        s_config = p["config"]

    except json.JSONDecodeError as e:
        wrong_json(msg, e, source="heartbeat")
        return
    except KeyError as e:
        missing_keys(msg, e, source="heartbeat")
        return

    if s_name not in obj.sensors:
        unconfigured_sensor(msg, s_name)
        return

    obj_sensor = obj.sensors[s_name]

    obj_sensor["last_contact"] = t.time()
    if obj.status == "awaiting_sensors":
        if s_config != obj_sensor["config"]:
            return

        obj_sensor["status"] = s_status
        obj_sensor["setpoint"] = s_setpoint
        obj_sensor["config"] = s_config
        if all(
            obj.sensors[s]["status"] == "awaiting_setpoint"
            for s in obj.sensors
            if s != "configured"
        ):
            obj.sensors["configured"] = True
            pub.publish("controller/ready", json.dumps({"uid": obj.experiment_uid}))
    else:
        obj_sensor["status"] = s_status
        obj_sensor["setpoint"] = s_setpoint
        obj_sensor["config"] = s_config
