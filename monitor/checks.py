import json
from jsonschema import validate, ValidationError
from utils import mqtt_clients

def check_payload_json_validity(topic, payload):
    try:
        json.loads(payload)
        return True
    except json.JSONDecodeError as e:
        error_payload = {
            "topic": topic,
            "error": "invalid_json",
            "error_message": str(e)
        }
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/malformed",
            json.dumps(error_payload)
        )
        return None

def check_topic_expected(entry, topic):
    if entry is None:
        error_payload = {
            'topic': topic,
            'error': 'unexpected_topic'
        }
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/unexpected",
            json.dumps(error_payload)
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
        error_payload = {
            "topic": topic,
            "channel": entry["name"],
            "error": "validation_error",
            "path": list(e.absolute_path) if e.absolute_path else None,
            "message": e.message,
        }
        mqtt_clients.MQTTPublisher.get_instance().publish(
            "error/message/invalid",
            json.dumps(error_payload)
        )
        return False
