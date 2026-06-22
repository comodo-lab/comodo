import json
import textwrap

from utils import mqtt_clients as mqtt


def wrong_json(msg, e):
    """
    Publishes an error message when a JSON message cannot be decoded.
    """
    error = f"Cannot decode {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps({"code": "malformed_json", "message": error}),
    )


def missing_keys(msg, e):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    error = f"Cannot decode {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps({"code": "missing_key", "message": error}),
    )


def incompatible_request(caller, obj, msg):
    """
    Publishes an error message when the mqtt request is incompatible with the current controller status.
    """
    topic = f"error/{caller.lower()}"
    error = f"Controller:{caller} cannot act on {msg.topic}. Controller status is {obj.status}."
    mqtt.MQTTPublisher.get_instance().publish(
        topic,
        json.dumps({"code": "incompatible_request", "message": error}),
    )


def incompatible_uid(caller, obj, msg, msg_uid):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    topic = f"error/{caller.lower()}"
    error = f"Current experiment is {obj.experiment_uid}. Controller:{caller} cannot act on {msg.topic} for experiment {msg_uid}."
    mqtt.MQTTPublisher.get_instance().publish(
        topic,
        json.dumps({"code": "incompatible_uid", "message": error}),
    )


def experiment_validation_error(error, uid=0):
    """
    Publishes an error message when the experiment configuration received from the ui fails validation.
    """
    error_msg = f"{type(error).__name__}: {error}"
    print(f"ERROR: {error_msg}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/validator",
        json.dumps({"code": "experiment_validation", "message": error_msg})
    )


def heartbeat_validation_error(msg, error):
    """
    Publishes an error message when a validation error occurs on a instrument's heartbeat.
    """
    p = msg.payload.decode("utf-8")
    t = msg.topic.split("/")[1]
    error = f"Invalid heartbeat from {t}: {p}. {error.args[0]}"
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/heartbeat",
        json.dumps({"code": "heartbeat_validation", "message": error}),
    )


def unconfigured_instrument(msg, instrument_name):
    """
    Publishes a warning message when a instrument heartbeat is received and the instrument is not configured.
    """
    error = f"Instrument {instrument_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}"
    print(f"WARNING: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/heartbeat",
        json.dumps({"code": "unconfigured_instrument", "message": error}),
    )


def controller_timeout(uid, who_timedout, consequence):
    """
    Publishes an error message when a timeout occurs.
    """
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps({"code": "timeout", "message": f"Timed out waiting for {who_timedout}. {consequence}..."}),
    )


def controller_state_incompatible_with_timer(uid, source, expected_state, state):
    """
    Publishes an error message when the state of the controller is not compatible with the current timer.
    """
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps({"code": "timer_error", "message": f"Timer for {source} exited unexpectedly. The controller state was found to be {state} instead of {expected_state}."}),
    )
