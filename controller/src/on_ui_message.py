import os
import json
from jsonschema import ValidationError

from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, MQTTValidationException

from src.controller_helper import data_path
import src.publish_error as pe


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
        experiment = validate_message(msg.topic, msg.payload)
    except MQTTValidationException as e:
        pe.message_validation(e)
        return

    if msg.topic == "ui/start":
        if obj.status == "idle":
            if not os.path.exists(f"{data_path}/tmp"):
                os.makedirs(f"{data_path}/tmp")

            exp_file = f"{data_path}/tmp/experiment_{experiment['id']}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)

            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/validate",
                json.dumps({"id": experiment["id"], "file": exp_file}),
            )
        else:
            pe.incompatible_controller_status(obj, msg)
    elif msg.topic == "ui/stop":
        if obj.status != "idle":
            if experiment["id"] == obj.experiment_uid:
                print("Stopping experiment...")
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop",
                    json.dumps({"id": experiment["id"]}),
                )
            else:
                pe.incompatible_uid(obj, msg, experiment["id"], "controller")
        else:
            pe.incompatible_controller_status(obj, msg)
    else:
        pe.incompatible_topic(obj, msg)
