import json
from jsonschema import validate, ValidationError
from utils import mqtt_clients

def check_payload_json_validity(topic, payload):
    try:
        json.loads(payload)
        return True
    except json.JSONDecodeError as e:
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/malformed",
            json.dumps({"code": "invalid_json", "message": str(e)})
        )
        return None

def check_topic_expected(entry, topic):
    if entry is None:
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/unexpected",
            json.dumps({"code": "unexpected_topic", "message": f"Unexpected topic: {topic}"})
        )
        return False
    return True

def check_message_valid(entry, topic, payload):
    try:
        validate(
            json.loads(payload),
            entry["schema"]
        )
        return True
    except ValidationError as e:
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/invalid",
            json.dumps({"code": "validation_error", "message": e.message})
        )
        return False
