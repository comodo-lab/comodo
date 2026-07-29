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


def incompatible_controller_status(obj, msg):
    """
    Publishes an error message when the mqtt request is incompatible with the current controller status.
    """
    topic = f"error/controller"
    error = f"Controller status is {obj.status}. Cannot act on {msg.topic}."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        topic,
        json.dumps({"code": "incompatible_controller_status", "message": error}),
    )


def incompatible_topic(obj, msg, caller):
    """
    Publishes an error message when the mqtt topic is incompatible with the caller that received the message.
    """
    caller = caller.lower()
    topic = f"error/{caller}"
    error = f"The {caller.replace('_', ' ')} cannot act on {msg.topic}."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        topic,
        json.dumps({"code": "incompatible_topic", "message": error}),
    )


def incompatible_uid(obj, msg, msg_uid, caller):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    topic = f"error/{caller.lower()}"
    caller = caller.lower().replace("_", " ")
    caller = caller[0].upper() + caller[1:]
    error = f"Current experiment is {obj.experiment_uid}. {caller} cannot act on {msg.topic} for experiment {msg_uid}."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        topic,
        json.dumps({"code": "incompatible_uid", "message": error}),
    )


def experiment_validation_error(error, uid):
    """
    Publishes an error message when the experiment configuration received from the ui fails validation.
    """
    error_msg = f"Validation failed for UID:{uid}. Error detials: {type(error).__name__}: {error}"
    print(f"ERROR: {error_msg}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/validator",
        json.dumps({"code": "experiment_validation", "message": error_msg}),
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
    error = f"Timed out waiting for {who_timedout}. {consequence}..."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps(
            {
                "code": "timeout",
                "message": error,
            }
        ),
    )


def controller_state_incompatible_with_timer(uid, source, expected_state, state):
    """
    Publishes an error message when the state of the controller is not compatible with the current timer.
    """
    error = f"Timer for {source} exited unexpectedly. The controller state was found to be {state} instead of {expected_state}."
    print(f"ERROR: {error}")
    mqtt.MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps(
            {
                "code": "timer_error",
                "message": error,
            }
        ),
    )
