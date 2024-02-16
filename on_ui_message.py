import json
from mqtt_clients import *
from error_helper import *

from controller_helper import data_path


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
        experiment = load_message(msg)
        uid = experiment["uid"]
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return

    if obj.status == "idle":
        if msg.topic == "ui/start":
            exp_file = f"{data_path}/tmp/experiment_{uid}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)
            client.publish(
                "controller/validate",
                json.dumps({"uid": uid, "file": exp_file}),
            )
        else:
            incompatible_request(obj, msg)
    else:
        if msg.topic == "ui/stop":
            if uid == obj.experiment_uid:
                client.publish(
                    "controller/stop",
                    json.dumps({"uid": uid}),
                )
            else:
                incompatible_uid(obj, msg)
        else:
            incompatible_request(obj, msg)
