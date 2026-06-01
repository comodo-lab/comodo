import json
import time as t
import jsonschema

from utils import mqtt_clients as mqtt
from utils.message_spec import load_spec as load_message_spec

from src.error_helper import (
    incompatible_request,
    wrong_json,
    heartbeat_validation_error,
    unconfigured_instrument,
)

INSTRUMENT_HEARTBEAT_SCHEMA = load_message_spec(
    "/app/messageSpec.yaml"
)["instruments/+/heartbeat"]["schema"]


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a instrument.
    It expects a message compliant with the spec schema for that channel.
    """
    if "instruments/" not in (msg.topic) or "/heartbeat" not in msg.topic:
        incompatible_request(obj, msg)
        return

    try:
        instrument = mqtt.load_message(msg)
        jsonschema.validate(instrument, INSTRUMENT_HEARTBEAT_SCHEMA)
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except jsonschema.ValidationError as e:
        heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        return

    instrument_name = msg.topic.split("/")[1]
    if instrument_name not in obj.instruments:
        unconfigured_instrument(msg, instrument_name)
        return

    obj_instrument = obj.instruments[instrument_name]

    obj_instrument["last_contact"] = t.time()
    if obj.status == "awaiting_instruments":
        if instrument["state"] == "idle":
            return
        if instrument["config"] != obj_instrument["config"]:
            e = (
                f"Instrument '{instrument_name}' misconfigured. "
                f"Expected {obj_instrument['config']}, received {instrument['config']}."
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

        obj_instrument["state"] = instrument["state"]
        obj_instrument["setpoints"] = instrument["setpoints"]
        obj_instrument["config"] = instrument["config"]
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
        obj_instrument["state"] = instrument["state"]
        obj_instrument["setpoints"] = instrument["setpoints"]
        obj_instrument["config"] = instrument["config"]
