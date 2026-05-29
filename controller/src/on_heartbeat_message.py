import json
import time as t

from utils import mqtt_clients as mqtt

from src.error_helper import (
    incompatible_request,
    wrong_json,
    missing_keys,
    heartbeat_validation_error,
    unconfigured_instrument,
)
from src.validation import validate_dict, ValidationException


def on_heartbeat_message(client, msg, obj):
    """
    Callback for the controller when it receives a heartbeat message from a instrument.
    It expects a message compliant with the schema defined in the schema_instrument_heartbeat.json file.
    """
    if "instruments/" not in (msg.topic) or "/heartbeat" not in msg.topic:
        incompatible_request(obj, msg)
        return

    try:
        p = mqtt.load_message(msg)
        instrument = validate_dict(p, obj.schema_instrument_heartbeat_path)
    except json.JSONDecodeError as e:
        wrong_json(msg, e)
        return
    except ValidationException as e:
        heartbeat_validation_error(msg, e)
        return

    if obj.status in ["idle", "validating", "starting"]:
        return

    if instrument["name"] not in obj.instruments:
        unconfigured_instrument(msg, instrument["name"])
        return

    obj_instrument = obj.instruments[instrument["name"]]

    obj_instrument["last_contact"] = t.time()
    if obj.status == "awaiting_instruments":
        if instrument["status"] == "awaiting_config":
            return
        if instrument["config"] != obj_instrument["config"]:
            e = (
                f"Instrument '{instrument['name']}' misconfigured. "
                f"Expected {obj_instrument['config']}, received {instrument['config']}."
            )
            print(f"ERROR: {e} Stopping experiment.")
            mqtt.MQTTPublisher.get_instance().publish(
                f"error/sensor/configuration",
                json.dumps({"error": e}),
            )
            mqtt.MQTTPublisher.get_instance().publish(
                "controller/command/stop", json.dumps({"id": obj.experiment_uid})
            )
            return

        obj_instrument["status"] = instrument["status"]
        obj_instrument["setpoint"] = instrument["setpoint"]
        obj_instrument["config"] = instrument["config"]
        if all(
            obj.instruments[s]["status"] not in [None, "awaiting_config"]
            for s in obj.instruments
            if s != "configured"
        ):
            if not obj.instruments["configured"]:
                obj.instruments["configured"] = True
                mqtt.MQTTPublisher.get_instance().publish(
                    "controller/event/ready", json.dumps({"experiment_id": obj.experiment_uid})
                )
    else:
        obj_instrument["status"] = instrument["status"]
        obj_instrument["setpoint"] = instrument["setpoint"]
        obj_instrument["config"] = instrument["config"]
