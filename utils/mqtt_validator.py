import json, yaml
from jsonschema import validate, ValidationError
from utils import mqtt_clients
from paho.mqtt.client import topic_matches_sub


class MQTTValidationException(Exception):

    def __init__(self, message):
        print(f"MQTT validation error: {message}")
        super().__init__(message)


schemas = {"asyncapi": "/schemas/mqtt_schema.yaml"}


def match_topic(topic, topic_map):
    for address, entry in topic_map.items():
        if topic_matches_sub(address, topic):
            return entry
    return None


def load_spec(schema_name="asyncapi"):
    # --------------------------------------------------------------------------
    # Load the schema

    path = schemas.get(schema_name, schema_name)
    with open(path) as f:
        spec = yaml.safe_load(f)

    # --------------------------------------------------------------------------
    # Get the channels

    channels = spec.get("channels", {})

    # --------------------------------------------------------------------------
    # Build the topic map

    topic_map = {}
    for ch_name, ch_def in channels.items():
        address = ch_def.get("address")
        if not address:
            continue
        messages = ch_def.get("messages", {})
        if not messages:
            continue
        first_msg = next(iter(messages.values()))
        topic_map[address] = {"name": ch_name, "schema": first_msg.get("payload", {})}
    return topic_map


def validate_message(topic, payload, schema_name="asyncapi", combine_exceptions=True):
    """
    Validates an incoming MQTT message against a schema

    The default schema is the one defined in the AsyncAPI specification

    Parameters:
        topic (str): The MQTT topic of the message
        payload (str): The payload of the message as a string
        schema_name (str): The name of the schema to validate against (default: "asyncapi")
        combine_exceptions (bool): If true (default), it raises only MQTTValidationException. Otherwise, it raises the original exception.
            The controller, for example, only needs to catch MQTTValidationException. Monitor, on the other hand, wants to get the original exceptions.

    Raises:
        combine_exception=True:
            MQTTValidationException: If the message fails validation in any way (invalid topic, invalid JSON, or schema validation failure)
        combine_exception=False:
            MQTTValidationException: If the topic is not expected according to the schema.
            json.JSONDecodeError: If the payload is not valid JSON.
            ValidationError: If the message does not conform to the schema.
    """
    # Check that the topic is in the register defined by the AsyncAPI spec
    entry = check_topic_expected(schema_name, topic)

    # Check the validity of the JSON payload
    try:
        loaded_payload = check_payload_json_validity(payload)
    except json.JSONDecodeError as e:
        if combine_exceptions:
            raise MQTTValidationException(
                f"Invalid JSON payload for topic '{topic}': {e}"
            )
        else:
            raise e

    # Perform message validation against the AsyncAPI schema
    try:
        check_message_valid(entry, loaded_payload)
    except ValidationError as e:
        if combine_exceptions:
            offending_key = (
                ".".join(str(p) for p in e.absolute_path)
                if e.absolute_path
                else "<root>"
            )
            raise MQTTValidationException(
                f"Message failed validation against schema for '{topic}': {e.message}."
                f" Failed check: {e.validator}, Offending key: {offending_key}"
            )
        else:
            raise e

    return loaded_payload


def check_topic_expected(schema_name, topic):
    """
    Loads the spec and checks if the topic is expected.

    Input:
        schema_name (str): The name of the schema to validate against
        topic (str): The MQTT topic of the message

    Returns:
        dict: The entry from the spec corresponding to the topic if it is expected.

    Raises:
        MQTTValidationException: If the topic is not expected according to the schema
    """
    # Load the spec
    topic_map = load_spec(schema_name)
    # Get the entry from the spec
    entry = match_topic(topic, topic_map)
    if entry is None:
        raise MQTTValidationException(f"Unexpected topic: {topic}")
    return entry


def check_payload_json_validity(payload):
    """
    Checks the validity of the JSON payload

    Raises:
        json.JSONDecodeError: If the payload is not valid JSON
    """
    return json.loads(payload)


def check_message_valid(entry, loaded_payload):
    """
    Validates the message payload against the schema defined in the spec

    Raises:
        ValidationError: If the message does not conform to the schema
    """
    validate(loaded_payload, entry["schema"])


def print_and_publish_error(topic, error):
    """
    Prints and publishes an error message when a validation error occurs on an mqtt message.
    """
    print(f"ERROR: {str(error)}")
    mqtt_clients.MQTTPublisher.get_instance().publish(
        topic, json.dumps({"code": "message_validation", "message": str(error)})
    )
