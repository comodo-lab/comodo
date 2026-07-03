import json
import time as t
from json import JSONDecodeError
from jsonschema import ValidationError

from utils import mqtt_clients as mqtt
from utils.mqtt_validator import validate_message, UnexpectedTopicException

from src.error_helper import (
    incompatible_request,
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
        incompatible_request("Heartbeat", obj, msg)
        return

    try:
        validate_message(msg.topic, msg.payload)
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except ValidationError as e:
        heartbeat_validation_error(msg, e)
        return
    except UnexpectedTopicException as e:
        return

    if obj.status in ["idle", "validating", "starting"]:
        return

    instrument_name = msg.topic.split("/")[1]
    payload_json = json.loads(msg.payload)
    if instrument_name in obj.instruments:
        _handle_instrument_heartbeat(obj, payload_json, instrument_name)
    else:
        unconfigured_instrument(msg, instrument_name)
        return

def _handle_instrument_heartbeat(obj, payload_json, instrument_name):
    obj_instrument = obj.instruments[instrument_name]
    obj_instrument["last_contact"] = t.time()
    if obj.status == "awaiting_instruments":
        # Assert state and config match, otherwise stop experiment
        if payload_json["state"] == "idle":
            return
        if payload_json["config"] != obj_instrument["config"]:
            e = (
                f"Instrument '{instrument_name}' misconfigured. "
                f"Expected {obj_instrument['config']}, received {payload_json['config']}."
            )

            print(f"ERROR: {e} Stopping experiment.")

            mqtt.MQTTPublisher.get_instance().publish(
                "error/sensor",
                json.dumps({"code": "configuration", "message": e}),
            )
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/stop", json.dumps({"id": obj.experiment_uid})
            )
            return

        # Update instrument state and setpoints
        obj_instrument["state"] = payload_json["state"]
        obj_instrument["setpoints"] = payload_json["setpoints"]
        obj_instrument["config"] = payload_json["config"]

        # Check if all instruments are ready (not idle) and if so:
        # set the configured flag and publish ready event
        if all(
            obj.instruments[s]["state"] not in [None, "idle"]
            for s in obj.instruments
            if s != "configured"
        ):
            if not obj.instruments["configured"]:
                obj.instruments["configured"] = True
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/event/ready", json.dumps({"experiment_id": obj.experiment_uid})
                )
    else:
        # Update instrument state and setpoints
        obj_instrument["state"] = payload_json["state"]
        obj_instrument["setpoints"] = payload_json["setpoints"]
        obj_instrument["config"] = payload_json["config"]
