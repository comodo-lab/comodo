import json
import time as t
from controller_state import *
from error_helper import *
from mqtt_clients import *
from validation import validate_dict, ValidationException


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a sensor.
    It expects a message compliant with the schema defined in the schema_sensor_heartbeat.json file.
    """
    if "heartbeat/sensor/" not in (msg.topic):
        incompatible_request(obj, msg, source="heartbeat")
        return

    try:
        p = load_message(msg)
        sensor = validate_dict(p, obj.schema_sensor_heartbeat_path)
    except json.JSONDecodeError as e:
        wrong_json(msg, e, source="heartbeat")
        return
    except KeyError as e:
        missing_keys(msg, e, source="heartbeat")
        return
    except ValidationException as e:
        heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        return

    if sensor["name"] not in obj.sensors:
        unconfigured_sensor(msg, sensor["name"])
        return

    obj_sensor = obj.sensors[sensor["name"]]

    obj_sensor["last_contact"] = t.time()
    if obj.status == "awaiting_sensors":
        if sensor["config"] != obj_sensor["config"]:
            return

        obj_sensor["status"] = sensor["status"]
        obj_sensor["setpoint"] = sensor["setpoint"]
        obj_sensor["config"] = sensor["config"]
        if all(
            obj.sensors[s]["status"] == "no_setpoint"
            for s in obj.sensors
            if s != "configured"
        ):
            obj.sensors["configured"] = True
            pub.publish("controller/ready", json.dumps({"uid": obj.experiment_uid}))
    else:
        obj_sensor["status"] = sensor["status"]
        obj_sensor["setpoint"] = sensor["setpoint"]
        obj_sensor["config"] = sensor["config"]
