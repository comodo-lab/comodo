import os
import json

from utils import mqtt_clients as mqtt
import utils.mqtt_validator as mqtt_val

from src.controller_helper import data_path
import src.publish_error as pub_err


def on_ui_message(client, msg, obj):
    """
    Handles the UI messages received by the controller, serving as an interface between the UI and the controller.
    It expects three types of messages (json formatted):
    - ui/start: to start an experiment
        The message should comply with the experiment schema.
        Can only be actioned if the controller is idle.
    - ui/stop: to stop the current experiment
        The message should contain the experiment's uid.
        Can only be actioned if the controller is not idle and the uid matches the current experiment's uid.
    - ui/reset: to reset the instruments and setpoint controllers (e.g. to clear a safe stop)
        Can only be actioned if the controller is idle, so it doesn't reset a running experiment.

    Args:
        client: The ui MQTT client.
        msg: The MQTT message.
        obj: The controller state object.

    Returns:
        None
    """

    try:
        experiment = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.message_validation(e)
        return

    if msg.topic == "ui/start":
        if obj.status == "idle":
            if not os.path.exists(f"{data_path}/tmp"):
                os.makedirs(f"{data_path}/tmp")

            exp_file = f"{data_path}/tmp/experiment_{experiment['temp_id']}.json"
            with open(exp_file, "w") as f:
                json.dump(experiment, f)

            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/validate",
                json.dumps({"temp_id": experiment["temp_id"], "file": exp_file}),
            )
        else:
            pub_err.incompatible_controller_status(obj, msg)
    elif msg.topic == "ui/stop":
        if obj.status != "idle":
            if experiment.get("experiment_id") == obj.experiment_id:
                print("Stopping experiment...")
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop",
                    json.dumps({"experiment_id": obj.experiment_id}),
                )
            else:
                pub_err.incompatible_uid(
                    obj, msg, experiment.get("experiment_id"), "controller"
                )
        else:
            pub_err.incompatible_controller_status(obj, msg)
    elif msg.topic == "ui/reset":
        if obj.status == "idle":
            print("Resetting the instruments and setpoint controllers...")
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/reset", json.dumps({"source": "ui"})
            )
        else:
            pub_err.incompatible_controller_status(obj, msg)
    else:
        pub_err.incompatible_topic(obj, msg)
