import json
import time as t

from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, MQTTValidationException

import src.publish_error as pe


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a instrument.
    It expects a message compliant with the spec schema for that channel.
    """
    if "instruments" not in (msg.topic) or "heartbeat" not in msg.topic:
        pe.incompatible_topic(obj, msg, "heartbeat_callback")
        return

    try:
        validate_message(msg.topic, msg.payload)
    except MQTTValidationException as e:
        pe.heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        # maintain a clean slate for instruments before the awaiting_instruments state
        return

    instrument_name = msg.topic.split("/")[1]
    payload = json.loads(msg.payload)
    if instrument_name in obj.instrument_states.keys():
        handle_instrument_heartbeat(obj, payload, instrument_name)
    else:
        pe.unconfigured_instrument(msg, instrument_name)
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
        if heartbeat["state"] == "idle":
            return
        # Check if all instruments are ready (not idle) and if so:
        # set the configured flag and publish ready event

        heartbeats_ready = all(
            instrument["state"] in ["ready", "adjusting"]
            for instrument in obj.instrument_states.values()
        )

        if heartbeats_ready and not obj.instruments_ready:
            obj.instruments_ready = True
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/event/ready",
                json.dumps({"experiment_id": obj.experiment_uid}),
            )


def heartbeat_valid(obj, heartbeat, instrument_name):
    expected = obj.config.get_expected_heartbeat(instrument_name)

    if heartbeat["config"] != expected:
        e = (
            f"Instrument '{instrument_name}' misconfigured. "
            f"Expected: {expected}; Received: {heartbeat['config']}."
        )

        print(f"ERROR: {e} Stopping experiment.")

        mqtt.MQTTPublisher.get_instance().publish(
            "error/instrument",
            json.dumps({"code": "configuration", "message": e}),
        )
        mqtt.MQTTPublisher.get_instance().publish(
            "controller/command/stop", json.dumps({"id": obj.experiment_uid})
        )
        return False
    return True
