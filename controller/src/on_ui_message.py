import json
import os

from utils import mqtt_clients as mqtt

from src.controller_helper import data_path, send_default_setpoints
from src.error_helper import (
    wrong_json,
    missing_keys,
    incompatible_request,
    incompatible_uid,
)


def on_ui_message(client, msg, obj):
    """
    Handles the UI messages received by the controller, serving as an interface between the UI and the controller.
    Topics handled (json formatted):
    - ui/start:    Start a new experiment (only when idle)
    - ui/stop:     Stop the current experiment (any non-idle state)
    - ui/pause:    Pause a running experiment
    - ui/resume:   Resume a paused experiment (advances to next scheduled setpoint)
    - ui/setpoint: Apply a global setpoint override while paused

    Args:
        client: The ui MQTT client.
        msg: The MQTT message.
        obj: The controller state object.

    Returns:
        None
    """

    try:
        experiment = mqtt.load_message(msg)
        uid = experiment["uid"]
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return

    publisher = mqtt.MQTTPublisher.get_instance()

    if msg.topic == "ui/start":
        if obj.status != "idle":
            incompatible_request(obj, msg)
            return
        if not os.path.exists(f"{data_path}/tmp"):
            os.makedirs(f"{data_path}/tmp")
        exp_file = f"{data_path}/tmp/experiment_{uid}.json"
        with open(exp_file, "w") as f:
            json.dump(experiment, f)
        publisher.publish("controller/validate", json.dumps({"uid": uid, "file": exp_file}))

    elif msg.topic == "ui/stop":
        if obj.status == "idle":
            incompatible_request(obj, msg)
            return
        if uid != obj.experiment_uid:
            incompatible_uid(obj, msg)
            return
        send_default_setpoints(obj)
        publisher.publish("controller/stop", json.dumps({"uid": uid}))

    elif msg.topic == "ui/pause":
        if obj.status != "running":
            incompatible_request(obj, msg)
            return
        if uid != obj.experiment_uid:
            incompatible_uid(obj, msg)
            return
        publisher.publish("controller/pause", json.dumps({"uid": uid}))

    elif msg.topic == "ui/resume":
        if obj.status != "paused":
            incompatible_request(obj, msg)
            return
        if uid != obj.experiment_uid:
            incompatible_uid(obj, msg)
            return
        publisher.publish("controller/resume", json.dumps({"uid": uid}))

    elif msg.topic == "ui/setpoint":
        if obj.status not in ["paused", "idle"]:
            incompatible_request(obj, msg)
            return
        if obj.status == "paused" and uid != obj.experiment_uid:
            incompatible_uid(obj, msg)
            return
        
        setpoints = experiment.get("setpoints", {})
        for full_id, value in setpoints.items():
            # Extract base instrument ID (e.g., 'mass_flow' from 'mass_flow/mass_flow')
            base_id = full_id.split("/")[0]
            publisher.publish(
                f"instrument/{base_id}/setpoint",
                json.dumps({base_id: value}),
            )

    else:
        incompatible_request(obj, msg)
