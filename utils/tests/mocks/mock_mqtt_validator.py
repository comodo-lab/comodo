"""Mock implementations for MQTT clients for testing."""

import pytest

import json
from unittest.mock import patch


@pytest.fixture
def mqtt_validator_mocks():
    """
    Unified fixture that patches:
        - utils.mqtt_validator.validate_message
    and exposes the mock as 'mqtt_val' in the test context.
    """
    with (
        patch("utils.mqtt_validator.validate_message") as mock_validate_message,
        patch("utils.mqtt_validator.print_and_publish_error") as mock_pap_error,
    ):
        # -----------------------
        # Mock validate_message to return the loaded JSON message
        # -----------------------
        mock_validate_message.side_effect = lambda topic, payload: json.loads(payload)

        # -----------------------
        # Expose mocks to tests
        # -----------------------
        yield {
            "validate_message": mock_validate_message,
            "print_and_publish_error": mock_pap_error,
        }
