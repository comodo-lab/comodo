import json, yaml
from jsonschema import validate, ValidationError
from utils import mqtt_clients
from paho.mqtt.client import topic_matches_sub

class UnexpectedTopicException(Exception):
    pass

schemas = {
    "asyncapi": "/app/schemas/mqtt_schema.yaml",
    "experiment_row": "/app/schemas/experiment_row.yaml",
}

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

def validate_message(topic, payload, schema_name="asyncapi"):
    """
    Validates an incoming MQTT message against a schema

    The default schema is the one defined in the AsyncAPI specification

    Parameters:
        topic (str): The MQTT topic of the message
        payload (str): The payload of the message as a string
        schema_name (str): The name of the schema to validate against (default: "asyncapi")

    Raises:
        UnexpectedTopicException: If the topic is not defined in the AsyncAPI specification
        json.JSONDecodeError: If the payload is not valid JSON
        jsonschema.ValidationError: If the payload does not conform to the schema
    """

    # --------------------------------------------------------------------------
    # Load the specified specification

    topic_map = load_spec(schema_name)

    # Get the entry from the spec
    entry = match_topic(topic, topic_map)

    # --------------------------------------------------------------------------
    # Run checks

    try:
        # Check that the topic is in the register defined by the AsyncAPI spec
        check_topic_expected(entry, topic)

        # Check the validity of the JSON payload
        check_payload_json_validity(topic, payload)

        # Perform message validation against the AsyncAPI schemea
        check_message_valid(entry, topic, payload)
    except Exception as e:
        raise e

def check_payload_json_validity(topic, payload):
    try:
        json.loads(payload)
    except json.JSONDecodeError as e:
        raise e

def check_topic_expected(entry, topic):
    if entry is None:
        raise UnexpectedTopicException(f"Unexpected topic: {topic}")

def check_message_valid(entry, topic, payload):
    try:
        validate(
            json.loads(payload),
            entry["schema"]
        )
    except ValidationError as e:
        raise e
