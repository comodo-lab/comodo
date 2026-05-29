import pytest
from parse import load_spec


class TestLoadSpec:
    def test_load_spec(self):
        topic_map = load_spec("tests/file_fixtures/sample_asyncapi.yaml")
        assert "error/message/malformed" in topic_map
        assert topic_map["error/message/malformed"]["name"] == "errorMalformed"
        assert topic_map["error/message/malformed"]["schema"]["type"] == "object"
        assert topic_map["error/message/malformed"]["schema"]["required"] == [
            "topic",
            "error",
            "error_message",
        ]

        assert "error/message/invalid" in topic_map
        assert topic_map["error/message/invalid"]["name"] == "errorInvalid"
        assert (
            topic_map["error/message/invalid"]["schema"]["properties"]["error"]["enum"]
            == ["validation_error"]
        )

        assert "error/message/unexpected" in topic_map
        assert topic_map["error/message/unexpected"]["name"] == "errorUnexpected"
        assert topic_map["error/message/unexpected"]["schema"]["required"] == [
            "topic",
            "error",
        ]
