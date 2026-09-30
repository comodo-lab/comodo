import time as t
import json

from utils import mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val

import src.publish_error as pub_err

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
        message = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.message_validation(e)
        return

    if msg.topic == "controller/timer/event/done":
        exp_id = message.get("experiment_id", "unknown")
        source = message.get("source", "unknown")
        if source != "instrument_setup":
            print(
                f"WARNING: Unexpected timer done event ignored (experiment_id: {exp_id})"
            )
        return

    try:
        if message["experiment_id"] != obj.experiment_id:
            pub_err.incompatible_uid(
                obj, msg, message["experiment_id"], "controller_timer"
            )
            return
    except KeyError as e:
        pub_err.missing_keys(msg, e)
        return

    if (
        msg.topic == "controller/timer/command/start"
        and message.get("source") == "instrument_setup"
    ):
        # Wait for instruments to be ready or timeout
        instrument_setup_wait = obj.config.globals["instrument_setup_wait"]
        if not instrument_setup_wait:
            err = "Instrument_setup_wait is not set in the config. It must be a positive number. Stopping experiment."
            pub_err.missing_keys(msg, KeyError(err))
            print("Stopping experiment...")
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/stop",
                json.dumps({"experiment_id": message["experiment_id"]}),
            )
            return
        t0 = t.time()
        while (not obj.instruments_ready) and obj.status == "awaiting_instruments":
            t.sleep(timer_check_frequency)
            if t.time() - t0 > instrument_setup_wait:
                pub_err.controller_timeout(message["experiment_id"], "instruments")
                print("Stopping experiment...")
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/command/stop",
                    json.dumps({"experiment_id": message["experiment_id"]}),
                )
                return
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/timer/event/done",
            json.dumps(
                {
                    "source": "instrument_setup",
                    "experiment_id": message["experiment_id"],
                    "instruments_configured": obj.instruments_ready,
                    "controller_status": obj.status,
                }
            ),
        )
    elif (
        msg.topic == "controller/timer/command/start"
        and message.get("source") == "setpoint"
    ):
        try:
            duration = message["duration"]
        except KeyError as e:
            pub_err.missing_keys(msg, e)
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
            pub_err.controller_state_incompatible_with_timer(
                message["experiment_id"], "setpoint", "running", obj.status
            )
        else:
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/timer/event/done",
                json.dumps(
                    {
                        "source": "setpoint",
                        "experiment_id": message["experiment_id"],
                        "controller_status": obj.status,
                    }
                ),
            )
    else:
        pub_err.incompatible_topic(obj, msg, "controller_timer")
