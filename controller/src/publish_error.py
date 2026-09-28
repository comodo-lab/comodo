import json
import textwrap

from utils import mqtt_clients as mqtt
from utils import mqtt_validator as mqtt_val


def print_and_publish(topic, code, message, type="ERROR"):
    print(f"{type}: {message}")
    mqtt.MQTTPublisher.get_instance().publish(
        topic, json.dumps({"code": code, "message": message})
    )


def message_validation(error):
    """
    Publishes an error message when a validation error occurs on an mqtt message.
    """
    mqtt_val.print_and_publish_error(
        topic="error/controller",
        message=str(error),
    )


def missing_keys(msg, e):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    print_and_publish(
        topic="error/controller",
        code="missing_key",
        message=f"Cannot decode {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}",
    )


def incompatible_controller_status(obj, msg):
    """
    Publishes an error message when the mqtt request is incompatible with the current controller status.
    """
    print_and_publish(
        topic="error/controller",
        code="incompatible_controller_status",
        message=f"Controller status is {obj.status}. Cannot act on {msg.topic}.",
    )


def incompatible_topic(obj, msg, caller):
    """
    Publishes an error message when the mqtt topic is incompatible with the caller that received the message.
    """
    caller = caller.lower()
    print_and_publish(
        topic=f"error/{caller}",
        code="incompatible_topic",
        message=f"The {caller.replace('_', ' ')} cannot act on {msg.topic}.",
    )


def incompatible_uid(obj, msg, msg_uid, caller):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    caller_txt = caller.lower().replace("_", " ")
    caller_txt = caller_txt[0].upper() + caller_txt[1:]
    print_and_publish(
        topic=f"error/{caller}",
        code="incompatible_uid",
        message=f"Current experiment is {obj.experiment_id}. {caller_txt} cannot act on {msg.topic} for experiment {msg_uid}.",
    )


def experiment_validation_error(error, uid):
    """
    Publishes an error message when the experiment configuration received from the ui fails validation.
    """
    print_and_publish(
        topic="error/validator",
        code="experiment_validation",
        message=f"Validation failed for UID:{uid}. Error detials: {type(error).__name__}: {error}",
    )


def heartbeat_validation_error(msg, error):
    """
    Publishes an error message when a validation error occurs on a instrument's heartbeat.
    """
    p = msg.payload.decode("utf-8")
    i = msg.topic.split("/")[1]
    print_and_publish(
        topic="error/heartbeat",
        code="heartbeat_validation",
        message=f"Invalid heartbeat from {i}: {p}. {error.args[0]}",
    )


def unconfigured_instrument(msg, instrument_name):
    """
    Publishes a warning message when a instrument heartbeat is received and the instrument is not configured.
    """
    print_and_publish(
        topic="error/heartbeat",
        code="unconfigured_instrument",
        message=f"Instrument {instrument_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}",
        type="WARNING",
    )


def controller_timeout(uid, who_timedout):
    """
    Publishes an error message when a timeout occurs.
    """
    print_and_publish(
        topic="error/controller",
        code="timeout",
        message=f"Timed out waiting for {who_timedout}.",
    )


def controller_state_incompatible_with_timer(uid, source, expected_state, state):
    """
    Publishes an error message when the state of the controller is not compatible with the current timer.
    """
    print_and_publish(
        topic="error/controller",
        code="timer_error",
        message=f"Timer for {source} exited unexpectedly. The controller state was found to be {state} instead of {expected_state}.",
    )


def invalid_instrument_config(instrument_name, expected, received):
    e = f"Instrument '{instrument_name}' misconfigured. Expected: {expected}; Received: {received}."
    print_and_publish(
        topic="error/instrument",
        code="configuration",
        message=e,
    )


def database_error(error):
    print_and_publish(
        topic="error/controller",
        code="influx_error",
        message=error,
    )
