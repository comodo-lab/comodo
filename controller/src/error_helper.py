import json
import textwrap

from utils import mqtt_clients as mqtt


def wrong_json(msg, e, source="controller"):
    """
    Publishes an error message when a JSON message cannot be decoded.
    """
    source = source.lower()
    error = f"Cannot decode {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        f"error/{source}",
        json.dumps({"error": error}),
    )


def missing_keys(msg, e, source="controller"):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    source = source.lower()
    error = f"Cannot decode {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        f"error/{source}",
        json.dumps({"error": error}),
    )


def incompatible_request(obj, msg, source="controller"):
    """
    Publishes an error message when the mqtt request is incompatible with the current controller* status.
    * When called from another source (other than the controller), this can be passed as a string.
    """
    if source == "controller":
        cant = "Cannot"
    else:
        cant = f"{source.capitalize()} cannot"
    error = f"Controller is {obj.status}. {cant} act on {msg.topic}"
    mqtt.MQTTPublisher.get_instance().publish(
        "error/" + source,
        json.dumps({"error": error}),
    )


def incompatible_uid(obj, msg, source="controller"):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    try:
        msg_uid = json.loads(msg.payload.decode("utf-8"))["uid"]
    except:
        msg_uid = "unknown"
    error = f"Current experiment is {obj.experiment_uid}. Cannot act on {msg.topic} for experiment {msg_uid}."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/" + source,
        json.dumps({"error": error}),
    )


def experiment_validation_error(error, uid):
    """
    Publishes an error message when the experiment configuration received from the ui fails validation.
    """
    mqtt.MQTTPublisher.get_instance().publish(
        "error/validator/failed",
        json.dumps(
            {
                "uid": uid,
                "valid": False,
                "error": str(error.args[0]),
            }
        ),
    )


def heartbeat_validation_error(msg, error):
    """
    Publishes an error message when a validation error occurs on a instrument's heartbeat.
    """
    p = msg.payload.decode("utf-8")
    t = msg.topic.split("heartbeat/instrument/")[1]
    error = f"Invalid heartbeat from {t}: {p}. {error.args[0]}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        f"error/heartbeat/validation",
        json.dumps({"error": error}),
    )


def unconfigured_instrument(msg, instrument_name):
    """
    Publishes a warning message when a instrument heartbeat is received and the instrument is not configured.
    """
    error = f"Instrument {instrument_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}"
    print(f"WARNING: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "warning/heartbeat",
        json.dumps({"warn": error}),
    )


def controller_timeout(uid, who_timedout, consequence):
    """
    Publishes an error message when a timeout occurs.
    """
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller/timeout",
        json.dumps(
            {
                "uid": uid,
                "error": f"Timed out waiting for {who_timedout}. {consequence}...",
            }
        ),
    )


def controller_state_incompatible_with_timer(uid, source, expected_state, state):
    """
    Publishes an error message when the state of the controller is not compatible with the current timer.
    """
    mqtt.MQTTPublisher.get_instance().publish(
        f"error/controller/timer/{source}",
        json.dumps(
            {
                "uid": uid,
                "error": f"Timer for {source} exited unexpectedly. The controller state was found to be {state} instead of {expected_state}.",
            }
        ),
    )
