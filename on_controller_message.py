import json
import time as t
from controller_state import *
from controller_helper import *
from mqtt_clients import *
from validation import validate_file, ValidationException


def c_idle(client, msg, obj):
    """
    Callback for the controller when it is idle.

    It expects a "controller/validate" message containing a JSON object with a "file" key, which contains the path to the experiment file.

    The experiment file is then loaded, decoded, and validated against the experiment schema.

    If the experiment is valid, the experiment id is updated and the controller state and callback are updated to "starting".
    Otherwise, it resets to the idle state and publishes an error.
    """
    if msg.topic != "controller/validate":
        incompatible_request(obj, msg)
        return

    # Load and decode experiment file
    try:
        payload = load_message(msg)
        obj.exp_file = payload["file"]
        temp_uid = payload["uid"]
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return
    obj.status = "validating"
    # Validate experiment configuration
    try:
        exp_config = validate_file(obj.exp_file, obj.schema_path)
        obj.experiment_uid = exp_config["uid"]
        m = {
            "uid": obj.experiment_uid,
            "valid": True,
        }
        pub.publish("validator/passed", json.dumps(m))
        obj.exp_config = exp_config
        # Update state and callback of controller
        client.callback = c_starting
        pub.publish("controller/start", json.dumps({"uid": m["uid"]}))
    except ValidationException as e:
        m = {
            "uid": temp_uid,
            "valid": False,
            "error": str(e.args[0]),
        }
        pub.publish("error/validator/failed", json.dumps(m))
        obj.experiment_uid = None
        obj.status = "idle"


def c_starting(client, msg, obj):
    if msg.topic != "controller/start":
        if msg.topic == "controller/stop":
            c_stopping(client, msg, obj)
        else:
            incompatible_request(obj, msg)
        return

    obj.status = "starting"
    # Compute intermediate setpoints
    obj.setpoints = split_setpoints(
        obj.exp_config["experiment"], obj.exp_config["config"]["resolution"]
    )
    # Create list of sensors dicts with expected config values
    obj.sensors = {"configured": False}
    for sensor in obj.exp_config["config"]["sensors"]:
        obj.sensors[sensor["name"]] = {
            "last_contact": None,
            "config": {k: v for k, v in sensor.items() if k != "name"},
            "status": None,
            "setpoint": None,
        }
    # Update state and callback of controller
    obj.status = "awaiting_sensors"
    client.callback = c_ready
    pub.publish("timer/start/sensor_setup", json.dumps({"uid": obj.experiment_uid}))
    # Send sensor config
    for sensor in obj.exp_config["config"]["sensors"]:
        pub.publish(f"sensor/{sensor['name']}/setup", json.dumps(sensor))


def c_ready(client, msg, obj):
    if msg.topic != "controller/ready":
        if msg.topic == "controller/stop":
            c_stopping(client, msg, obj)
        else:
            incompatible_request(obj, msg)
        return

    obj.status = "ready"
    # Update experiment id and start experiment
    assign_serial_id(obj)
    # Update state and callback of controller
    client.callback = c_running
    pub.publish("controller/run", obj.id)


def c_running(client, msg, obj):
    if msg.topic != "controller/run":
        if msg.topic == "controller/stop":
            c_stopping(client, msg, obj)
        else:
            incompatible_request(obj, msg)
        return

    obj.status = "running"
    ### Send setpoints placeholder
    pass
    ###


def c_stopping(client, msg, obj):
    if msg.topic != "controller/stop":
        incompatible_request(obj, msg)
        return

    message = load_message(msg)
    if message["uid"] == obj.experiment_uid:
        obj.status = "stopping"
        ### Safe stop placeholder
        t.sleep(3)
        ###
        obj.status = "idle"
        obj.experiment_uid = None
        obj.adjusting = AdjustingDict()
        client.callback = c_idle
    else:
        incompatible_uid(obj, msg)
