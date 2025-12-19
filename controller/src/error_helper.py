import json
import textwrap

from utils.mqtt_clients import MQTTPublisher


def wrong_json(msg, e, source="controller"):
    """
    Publishes an error message when a JSON message cannot be decoded.
    """
    source = source.lower()
    error = f"Error decoding {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
    MQTTPublisher.get_instance().publish(
        f"error/{source}",
        json.dumps({"error": error}),
    )


def missing_keys(msg, e, source="controller"):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    source = source.lower()
    error = f"Error decoding {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}"
    MQTTPublisher.get_instance().publish(
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
    MQTTPublisher.get_instance().publish(
        "error/" + source,
        json.dumps({"error": error}),
    )


def incompatible_uid(obj, msg):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    msg_uid = json.loads(msg.payload.decode("utf-8"))["uid"]
    error = f"Current experiment is {obj.experiment_uid}. Cannot act on {msg.topic} for experiment {msg_uid}."
    MQTTPublisher.get_instance().publish(
        "error/controller",
        json.dumps({"error": error}),
    )


def experiment_validation_error(error, uid):
    """
    Publishes an error message when the experiment configuration received from the ui fails validation.
    """
    MQTTPublisher.get_instance().publish(
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
    Publishes an error message when a validation error occurs on a sensor's heartbeat.
    """
    p = msg.payload.decode("utf-8")
    t = msg.topic.split("heartbeat/sensor/")[1]
    MQTTPublisher.get_instance().publish(
        f"error/heartbeat/validation",
        json.dumps(
            {"error": f"Error validating heartbeat from {t}: {p}. {error.args[0]}"}
        ),
    )


def unconfigured_sensor(msg, sensor_name):
    """
    Publishes an error message when a sensor heartbeat is received and the sensor is not configured.
    """
    error = f"Sensor {sensor_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}"
    MQTTPublisher.get_instance().publish(
        "error/heartbeat",
        json.dumps({"error": error}),
    )


def controller_timeout(uid, who_timedout, consequence):
    """
    Publishes an error message when a timeout occurs.
    """
    MQTTPublisher.get_instance().publish(
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
    MQTTPublisher.get_instance().publish(
        f"error/controller/timer/{source}",
        json.dumps(
            {
                "uid": uid,
                "error": f"Timer for {source} exited unexpectedly. The controller state was found to be {state} instead of {expected_state}.",
            }
        ),
    )
