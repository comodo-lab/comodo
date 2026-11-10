import pytest

from utils.mqtt_validator import topic_entry


@pytest.fixture
def mock_topic_map():
    topic_map = {
        "test/topic": {
            "name": "test",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["test_str", "test_num"],
                "properties": {
                    "test_str": {"type": "string"},
                    "test_num": {"type": "number"},
                },
            },
        },
        "another/topic": {
            "name": "another",
            "schema": {
                "type": "object",
                "additionalProperties": True,
                "required": ["another_str", "another_num"],
                "properties": {
                    "another_str": {"type": "string"},
                    "another_num": {"type": "number"},
                },
            },
        },
        "wildcard/+/topic": {
            "name": "single_wildcard",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["wildcard_str", "wildcard_num"],
                "properties": {
                    "wildcard_str": {"type": "string"},
                    "wildcard_num": {"type": "number"},
                },
            },
        },
        "wildcard/topic/#": {
            "name": "multi_wildcard",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["wildcard_str", "wildcard_num"],
                "properties": {
                    "wildcard_str": {"type": "string"},
                    "wildcard_num": {"type": "number"},
                },
            },
        },
        "error/message/malformed": {
            "name": "errorMalformed",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error", "error_message"],
                "properties": {
                    "topic": {"type": "string"},
                    "error": {"type": "string", "enum": ["invalid_json"]},
                    "error_message": {"type": "string"},
                },
            },
        },
        "error/message/invalid": {
            "name": "errorInvalid",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error", "message"],
                "properties": {
                    "topic": {"type": "string"},
                    "channel": {"type": "string"},
                    "error": {"type": "string", "enum": ["validation_error"]},
                    "path": {"type": "array", "items": {"type": "string"}},
                    "message": {"type": "string"},
                },
            },
        },
        "error/message/unexpected": {
            "name": "errorUnexpected",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "error"],
                "properties": {
                    "topic": {"type": "string"},
                    "error": {"type": "string", "enum": ["unexpected_topic"]},
                },
            },
        },
    }
    return {
        address: topic_entry(entry["name"], entry["schema"])
        for address, entry in topic_map.items()
    }
