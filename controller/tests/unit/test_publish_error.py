import pytest
import json
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
)

import src.publish_error as pe
from src.validation import ExperimentValidationError
from utils.mqtt_validator import MQTTValidationException


class TestPrintAndPublish:
    def test_prints_and_publishes_default_err(self, message_bus, capsys):
        topic = "test/topic"
        code = "test_code"
        message = "This is a test error message."

        pe.print_and_publish(topic, code, message)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == topic
        p = json.loads(messages[0].payload)
        assert p["code"] == code
        assert p["message"] == message

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {message}"

    def test_prints_and_publishes_uses_type(self, message_bus, capsys):
        topic = "test/topic"
        code = "test_code"
        message = "This is a test error message."
        type = "WARNING"

        pe.print_and_publish(topic, code, message, type=type)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == topic
        p = json.loads(messages[0].payload)
        assert p["code"] == code
        assert p["message"] == message

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"WARNING: {message}"


class TestPublishError:
    @pytest.fixture
    def pe_mocks(self, mock_state):
        with patch("src.publish_error.print_and_publish") as mock_pap:
            mock_cstate = mock_state("end")
            mock_msg = MockMessage(
                topic="controller/command/run",
                payload=json.dumps({"id": "test_uid"}).encode("utf-8"),
            )

            yield {
                "print_and_publish": mock_pap,
                "cstate": mock_cstate,
                "msg": mock_msg,
            }

    def test_message_validation(self, pe_mocks):
        exp_err = "Invalid message format."

        pe.message_validation(MQTTValidationException(exp_err))

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="message_validation",
            message=exp_err,
        )

    def test_missing_keys(self, pe_mocks):
        exp_err = f"Cannot decode {pe_mocks['msg'].topic} message, missing: \n   'id'"

        pe.missing_keys(pe_mocks["msg"], KeyError("id"))

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="missing_key",
            message=exp_err,
        )

    def test_missing_keys(self, pe_mocks):
        exp_err = f"Cannot decode {pe_mocks['msg'].topic} message, missing: \n   'id'"

        pe.missing_keys(pe_mocks["msg"], KeyError("id"))

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="missing_key",
            message=exp_err,
        )

    def test_incompatible_controller_status(self, pe_mocks):
        exp_err = f"Controller status is {pe_mocks['cstate'].status}. Cannot act on {pe_mocks['msg'].topic}."

        pe.incompatible_controller_status(pe_mocks["cstate"], pe_mocks["msg"])

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="incompatible_controller_status",
            message=exp_err,
        )

    def test_incompatible_topic(self, pe_mocks):
        exp_err = f"The test caller cannot act on {pe_mocks['msg'].topic}."

        pe.incompatible_topic(pe_mocks["cstate"], pe_mocks["msg"], "test_caller")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/test_caller",
            code="incompatible_topic",
            message=exp_err,
        )

    def test_incompatible_uid(self, pe_mocks):
        exp_err = f"Current experiment is {pe_mocks['cstate'].experiment_uid}. Test caller cannot act on {pe_mocks['msg'].topic} for experiment 567."

        pe.incompatible_uid(pe_mocks["cstate"], pe_mocks["msg"], 567, "test_caller")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/test_caller",
            code="incompatible_uid",
            message=exp_err,
        )

    def test_experiment_validation_error(self, pe_mocks):
        eve = ExperimentValidationError("Invalid experiment configuration.")
        exp_err = f"Validation failed for UID:test_uid. Error detials: ExperimentValidationError: Invalid experiment configuration."

        pe.experiment_validation_error(eve, "test_uid")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/validator",
            code="experiment_validation",
            message=exp_err,
        )

    def test_heartbeat_validation_error(self, pe_mocks):
        mqttve = MQTTValidationException("Invalid heartbeat format.")
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err = 'Invalid heartbeat from test_inst: {"bad": "info"}. Invalid heartbeat format.'

        pe.heartbeat_validation_error(msg, mqttve)

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/heartbeat",
            code="heartbeat_validation",
            message=exp_err,
        )

    def test_unconfigured_instrument(self, pe_mocks):
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err = 'Instrument test_inst is not configured. Unexpected heartbeat message:\n    ins/test_inst/hb  {"bad": "info"}'

        pe.unconfigured_instrument(msg, "test_inst")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/heartbeat",
            code="unconfigured_instrument",
            message=exp_err,
            type="WARNING",
        )

    def test_controller_timeout(self, pe_mocks):
        exp_err = "Timed out waiting for instruments."

        pe.controller_timeout("test_uid", "instruments")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="timeout",
            message=exp_err,
        )

    def test_controller_state_incompatible_with_timer(self, pe_mocks):
        exp_err = "Timer for instrument_setup exited unexpectedly. The controller state was found to be running instead of awaiting_instruments."

        pe.controller_state_incompatible_with_timer(
            "test_uid", "instrument_setup", "awaiting_instruments", "running"
        )

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="timer_error",
            message=exp_err,
        )

    def test_invalid_instrument_config(self, pe_mocks):
        exp_err = "Instrument 'test_inst' misconfigured. Expected: {'key': 'value'}; Received: {'key': 'wrong_value'}."

        pe.invalid_instrument_config(
            "test_inst", {"key": "value"}, {"key": "wrong_value"}
        )

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/instrument",
            code="configuration",
            message=exp_err,
        )

    def test_database_error(self, pe_mocks):
        exp_err = "Could not dump influx database: ConnectionError"

        pe.database_error("Could not dump influx database: ConnectionError")

        pe_mocks["print_and_publish"].assert_called_once_with(
            topic="error/controller",
            code="influx_error",
            message=exp_err,
        )
