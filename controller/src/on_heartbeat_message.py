import json
import time as t
from jsonschema import ValidationError

from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, MQTTValidationException

from src.error_helper import (
    incompatible_topic,
    wrong_json,
    heartbeat_validation_error,
    unconfigured_instrument,
)


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a instrument.
    It expects a message compliant with the spec schema for that channel.
    """
    if "instruments" not in (msg.topic) or "heartbeat" not in msg.topic:
        incompatible_topic(obj, msg, "heartbeat_callback")
        return

    try:
        validate_message(msg.topic, msg.payload)
    except MQTTValidationException as e:
        heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        return

    instrument_name = msg.topic.split("/")[1]
    payload = json.loads(msg.payload)
    if instrument_name in obj.instruments:
        handle_instrument_heartbeat(obj, payload, instrument_name)
    elif instrument_name in obj.sensor_instruments:
        return
    else:
        unconfigured_instrument(msg, instrument_name)
        return


def handle_instrument_heartbeat(obj, heartbeat, instrument_name):
    obj_instrument = obj.instruments[instrument_name]
    obj_instrument["last_contact"] = t.time()
    if obj.status == "awaiting_instruments":
        # Assert state and config match, otherwise stop experiment
        if heartbeat["state"] == "idle":
            return
        expected = obj.config.get_expected_heartbeat(instrument_name)
        if heartbeat["config"] != expected:
            e = (
                f"Instrument '{instrument_name}' misconfigured. "
                f"Expected {expected}, received {heartbeat['config']}."
            )

            print(f"ERROR: {e} Stopping experiment.")

            mqtt.MQTTPublisher.get_instance().publish(
                "error/instrument",
                json.dumps({"code": "configuration", "message": e}),
            )
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/stop", json.dumps({"id": obj.experiment_uid})
            )
            return

        # Update instrument state and setpoints
        obj_instrument["state"] = heartbeat["state"]
        obj_instrument["setpoints"] = heartbeat["setpoints"]
        obj_instrument["config"] = heartbeat["config"]

        # Check if all instruments are ready (not idle) and if so:
        # set the configured flag and publish ready event

        heartbeats_ready = True
        for instrument in obj.instruments.values():
            if instrument["state"] in [None, "idle", "error"]:
                heartbeats_ready = False
                break

        if heartbeats_ready and not obj.instruments_ready:
            obj.instruments_ready = True
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/event/ready",
                json.dumps({"experiment_id": obj.experiment_uid}),
            )
    else:
        # Update instrument state and setpoints
        obj_instrument["state"] = heartbeat["state"]
        obj_instrument["setpoints"] = heartbeat["setpoints"]
        obj_instrument["config"] = heartbeat["config"]
