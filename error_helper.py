import json
import textwrap
from mqtt_clients import *


def wrong_json(msg, e):
    """
    Publishes an error message when a JSON message cannot be decoded.
    """
    pub.publish(
        "error/controller",
        f"Error decoding {msg.topic} message, wrong JSON: \n{textwrap.indent(str(e), '   ')}",
    )


def missing_keys(msg, e):
    """
    Publishes an error message when the key trying to be accessed is missing.
    """
    pub.publish(
        "error/controller",
        f"Error decoding {msg.topic} message, missing: \n{textwrap.indent(str(e), '   ')}",
    )


def incompatible_request(obj, msg, source="controller"):
    """
    Publishes an error message when the mqtt request is incompatible with the current controller* status.
    * When called from another source (other than the controller), this can be passed as a string.
    """
    source = source.lower()
    pub.publish(
        "error/" + source,
        f"{source.capitalize()} is {obj.status}. Cannot act on {msg.topic}",
    )


def incompatible_uid(obj, msg):
    """
    Publishes an error message when the experiment uid in the mqtt request does not match the current experiment's uid.
    """
    msg_uid = json.loads(msg.payload.decode("utf-8"))["uid"]
    pub.publish(
        "error/controller",
        f"Current experiment is {obj.experiment_uid}. Cannot act on {msg.topic} for experiment {msg_uid}.",
    )


def unconfigured_sensor(msg, sensor_name):
    """
    Publishes an error message when a sensor heartbeat is received and the sensor is not configured.
    """
    pub.publish(
        "error/controller",
        f"Sensor {sensor_name} is not configured. Unexpected heartbeat message:\n    {msg.topic}  {msg.payload.decode('utf-8')}",
    )
