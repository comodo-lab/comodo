import json
import time as t

from utils import mqtt_clients as mqtt
import utils.mqtt_validator as mqtt_val

import src.publish_error as pub_err


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a instrument.
    It expects a message compliant with the spec schema for that channel.
    """
    if "instruments" not in (msg.topic) or "heartbeat" not in msg.topic:
        pub_err.incompatible_topic(obj, msg, "heartbeat_callback")
        return

    try:
        message = mqtt_val.validate_message(msg.topic, msg.payload)
    except mqtt_val.MQTTValidationException as e:
        pub_err.heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        # maintain a clean slate for instruments before the awaiting_instruments state
        return

    instrument_name = msg.topic.split("/")[1]
    if instrument_name in obj.instrument_states:
        handle_instrument_heartbeat(obj, message, instrument_name)
    else:
        pub_err.unconfigured_instrument(msg, instrument_name)
        return


def handle_instrument_heartbeat(obj, heartbeat, instrument_name):
    # Update instrument state and setpoints
    obj.instrument_states[instrument_name]["last_contact"] = t.time()
    if not heartbeat_valid(obj, heartbeat, instrument_name):
        return
    obj.instrument_states[instrument_name]["state"] = heartbeat["state"]
    obj.instrument_states[instrument_name]["setpoints"] = heartbeat["setpoints"]
    obj.instrument_states[instrument_name]["config"] = heartbeat["config"]
    if obj.status == "awaiting_instruments":
        # Assert state and config match, otherwise stop experiment
        if heartbeat["state"]["status"] in ["initialising", "awaiting_experiment"]:
            return
        # Check if all instruments are ready and if so:
        # set the configured flag and publish ready event
        heartbeats_ready = all(
            (instrument["state"] or {}).get("status") in ["running"]
            for instrument in obj.instrument_states.values()
        )

        if heartbeats_ready and not obj.instruments_ready:
            obj.instruments_ready = True
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/event/ready",
                json.dumps({"experiment_id": obj.experiment_id}),
            )


def heartbeat_valid(obj, heartbeat, instrument_name):
    expected = obj.get_expected_heartbeat(instrument_name)
    # Tolerate experiment config miss-match if either is empty (allows for setting up periods)
    if (
        expected["experiment"] == {}
        or heartbeat["config"].get("experiment", {}).get("experiment_id", None) is None
    ):
        expected["experiment"] = heartbeat["config"].get("experiment", {})

    if heartbeat["config"] != expected:
        pub_err.invalid_instrument_config(
            instrument_name, expected, heartbeat["config"]
        )
        print("Stopping experiment...")
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/command/stop", json.dumps({"experiment_id": obj.experiment_id})
        )
        return False
    return True
