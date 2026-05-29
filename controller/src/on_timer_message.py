import os
import time as t
import json

from utils import mqtt_clients as mqtt

from src.error_helper import (
    incompatible_uid,
    wrong_json,
    missing_keys,
    controller_timeout,
    controller_state_incompatible_with_timer,
    incompatible_request,
)

timer_check_frequency = 0.1


def on_timer_message(client, msg, obj):
    """
    Callback function for the timer MQTT client.
    The timer client is used to de-couple the waiting times that the controller needs to wait,
    but keeps the controller callback available, as opposed to using time.sleep() in the controller,
    which would block the callback.
    The timer client is used to wait for the instruments to be ready before starting the experiment,
    and to wait for the setpoint duration before moving to the next setpoint.
    """
    try:
        message = mqtt.load_message(msg)
        if message["experiment_id"] != obj.experiment_uid:
            incompatible_uid(obj, msg, message["experiment_id"])
            return
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except KeyError as e:
        missing_keys(msg, e)
        return

    if msg.topic == "controller/timer/start/instrument_setup":
        # Wait for instruments to be ready or timeout
        instrument_setup_wait = float(os.getenv("INSTRUMENT_SETUP_WAIT", 10))
        t0 = t.time()
        while (
            not obj.instruments["configured"]
        ) and obj.status == "awaiting_instruments":
            t.sleep(timer_check_frequency)
            if t.time() - t0 > instrument_setup_wait:
                controller_timeout(message["experiment_id"], "instruments", "Stopping")
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop", json.dumps({"id": message["experiment_id"]})
                )
                return
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/timer/done/instrument_setup",
            json.dumps(
                {
                    # experiment uid changes when all instruments get configured, so have to use obj.experiment_uid, not message["experiment_id"]
                    "experiment_id": obj.experiment_uid,
                    "instruments_configured": obj.instruments["configured"],
                    "controller_status": obj.status,
                }
            ),
        )
    elif msg.topic == "controller/timer/start/setpoint":
        try:
            duration = message["duration"]
        except KeyError as e:
            missing_keys(msg, e)
            return
        # Start timer for setpoint
        t0 = t.time()
        while obj.status == "running":
            t.sleep(timer_check_frequency)
            if t.time() - t0 > duration:
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/run",
                    json.dumps({"experiment_id": message["experiment_id"]}),
                )
                return
        if obj.status != "stopping":
            controller_state_incompatible_with_timer(
                message["experiment_id"], "setpoint", "running", obj.status
            )
        else:
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/timer/done/setpoint",
                json.dumps({"experiment_id": message["experiment_id"], "controller_status": obj.status}),
            )
    elif msg.topic.startswith("controller/timer/done/"):
        return
    else:
        incompatible_request(obj, msg)
