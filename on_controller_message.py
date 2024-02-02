import json
import time as t
from controller_state import *
from controller_helper import *
from mqtt_clients import *
from validation import validate_experiment_soft


def c_idle(client, msg, obj):
    if msg.topic != "controller/validate":
        return

    # Load and decode experiment file
    try:
        obj.exp_file = load_message(msg)["file"]
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return
    obj.status = "validating"
    # Validate experiment configuration
    exp_config, err = validate_experiment_soft(obj.exp_file, obj.schema_path)
    if err == None:
        obj.experiment_uid = exp_config["uid"]
        m = {
            "uid": obj.experiment_uid,
            "valid": True,
        }
        pub.publish("controller/validator/passed", json.dumps(m))
        obj.exp_config = exp_config
        # Update state and callback of controller
        client.callback = c_starting
        pub.publish("controller/start", json.dumps({"uid": m["uid"]}))
    else:
        m = {
            "uid": obj.experiment_uid,
            "valid": False,
            "error": err,
        }
        pub.publish("controller/validator/failed", json.dumps(m))
        obj.experiment_uid = None
        obj.status = "idle"


def c_starting(client, msg, obj):
    if msg.topic != "controller/start":
        if msg.topic == "controller/stop":
            c_stopping(client, msg, obj)
        # else:
        #     incompatible_request(obj, msg)
        return

    obj.status = "starting"
    obj.sensors = {"ready": False}
    # Send sensor config
    for sensor in obj.exp_config["config"]["sensors"]:
        pub.publish(f"controller/setup/{sensor['name']}", json.dumps(sensor))
    # Compute intermediate setpoints
    obj.setpoints = split_setpoints(
        obj.exp_config["experiment"], obj.exp_config["config"]["resolution"]
    )
    ### This needs to be a separate function!!
    # Wait for sensors to be ready or timeout
    t0 = t.time()
    while not obj.sensors["ready"]:
        t.sleep(0.1)
        if t.time() - t0 > 10:
            pub.publish(
                "controller/error",
                f"Timed out waiting for sensors. Exiting...",
            )
            client.callback = c_stopping
            c_stopping(client, internal_stop_msg(obj.experiment_uid), obj)
            return
    # Update experiment id and start experiment
    assign_serial_id(obj)
    # Update state and callback of controller
    client.callback = c_running
    pub.publish("controller/run", obj.id)


def c_running(client, msg, obj):
    if msg.topic == "controller/run":
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
