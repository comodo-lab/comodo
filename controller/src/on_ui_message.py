import os
import json
from jsonschema import ValidationError

from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, MQTTValidationException

from src.controller_helper import data_path
from src.error_helper import (
    incompatible_controller_status,
    wrong_json,
    missing_keys,
    incompatible_uid,
    experiment_validation_error,
)


def on_ui_message(client, msg, obj):
    """
    Handles the UI messages received by the controller, serving as an interface between the UI and the controller.
    It expects two types of messages (json formatted):
    - ui/start: to start an experiment
        The message should comply with the experiment schema.
        Can only be actioned if the controller is idle.
    - ui/stop: to stop the current experiment
        The message should contain the experiment's uid.
        Can only be actioned if the controller is not idle and the uid matches the current experiment's uid.

    Args:
        client: The ui MQTT client.
        msg: The MQTT message.
        obj: The controller state object.

    Returns:
        None
    """

    try:
        experiment = mqtt.load_message(msg)
        uid = experiment["id"]
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return

    if msg.topic == "ui/start":
        try:
            validate_message(msg.topic, msg.payload)
        except MQTTValidationException as e:
            experiment_validation_error(e, uid)
            return

    if obj.status == "idle":
        if msg.topic == "ui/start":
            if not os.path.exists(f"{data_path}/tmp"):
                os.makedirs(f"{data_path}/tmp")

            exp_file = f"{data_path}/tmp/experiment_{uid}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)

            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/validate",
                json.dumps({"id": uid, "file": exp_file}),
            )
        else:
            incompatible_controller_status(obj, msg)
    else:
        if msg.topic == "ui/stop":
            if uid == obj.experiment_uid:
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop",
                    json.dumps({"id": uid}),
                )
            else:
                incompatible_uid(obj, msg, uid, "controller")
        else:
            incompatible_controller_status(obj, msg)
