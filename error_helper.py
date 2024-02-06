import json
import textwrap
from mqtt_clients import *


def wrong_json(msg, e):
    """
    Publishes an error message when a JSON message cannot be decoded.
    """
    error = f"Error decoding {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}"
    pub.publish(
        "error/controller",
        json.dumps({"error": error}),
    )


def missing_keys(msg, e):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    error = f"Error decoding {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}"
    pub.publish(
        "error/controller",
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
    pub.publish(
        "error/" + source,
        json.dumps({"error": error}),
    )


def incompatible_uid(obj, msg):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    msg_uid = json.loads(msg.payload.decode("utf-8"))["uid"]
    error = f"Current experiment is {obj.experiment_uid}. Cannot act on {msg.topic} for experiment {msg_uid}."
    pub.publish(
        "error/controller",
        json.dumps({"error": error}),
    )


def unconfigured_sensor(msg, sensor_name):
    """
    Publishes an error message when a sensor heartbeat is received and the sensor is not configured.
    """
    error = f"Sensor {sensor_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}"
    pub.publish(
        "error/controller",
        json.dumps({"error": error}),
    )
