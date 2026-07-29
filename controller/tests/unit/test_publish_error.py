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


class TestErrorHelper:
    @pytest.fixture
    def eh_mocks(self, mock_state):
        mock_cstate = mock_state("end")
        mock_msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"id": "test_uid"}).encode("utf-8"),
        )

        yield {
            "cstate": mock_cstate,
            "msg": mock_msg,
        }

    def test_wrong_json(self, message_bus, capsys, eh_mocks):
        exp_err = f"Cannot decode {eh_mocks['msg'].topic} message, wrong JSON: \n   Invalid JSON: line 1 column 1 (char 0)"

        pe.wrong_json(eh_mocks["msg"], json.JSONDecodeError("Invalid JSON", "", 0))

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "malformed_json"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_missing_keys(self, message_bus, capsys, eh_mocks):
        exp_err = f"Cannot decode {eh_mocks['msg'].topic} message, missing: \n   'id'"

        pe.missing_keys(eh_mocks["msg"], KeyError("id"))

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "missing_key"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_incompatible_controller_status(self, message_bus, capsys, eh_mocks):
        exp_err = f"Controller status is {eh_mocks['cstate'].status}. Cannot act on {eh_mocks['msg'].topic}."

        pe.incompatible_controller_status(eh_mocks["cstate"], eh_mocks["msg"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_controller_status"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_incompatible_topic(self, message_bus, capsys, eh_mocks):
        exp_err = f"The test caller cannot act on {eh_mocks['msg'].topic}."

        pe.incompatible_topic(eh_mocks["cstate"], eh_mocks["msg"], "test_caller")

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/test_caller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_topic"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_incompatible_uid(self, message_bus, capsys, eh_mocks):
        exp_err = f"Current experiment is {eh_mocks['cstate'].experiment_uid}. Test caller cannot act on {eh_mocks['msg'].topic} for experiment 567."

        pe.incompatible_uid(eh_mocks["cstate"], eh_mocks["msg"], 567, "test_caller")

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/test_caller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_uid"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_experiment_validation_error(self, message_bus, capsys, eh_mocks):
        eve = ExperimentValidationError("Invalid experiment configuration.")
        exp_err = f"Validation failed for UID:test_uid. Error detials: ExperimentValidationError: Invalid experiment configuration."

        pe.experiment_validation_error(eve, "test_uid")

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        p = json.loads(messages[0].payload)
        assert p["code"] == "experiment_validation"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_heartbeat_validation_error(self, message_bus, capsys, eh_mocks):
        mqttve = MQTTValidationException("Invalid heartbeat format.")
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err = 'Invalid heartbeat from test_inst: {"bad": "info"}. Invalid heartbeat format.'

        pe.heartbeat_validation_error(msg, mqttve)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/heartbeat"
        p = json.loads(messages[0].payload)
        assert p["code"] == "heartbeat_validation"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_unconfigured_instrument(self, message_bus, capsys, eh_mocks):
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err = 'Instrument test_inst is not configured. Unexpected heartbeat message:\n    ins/test_inst/hb  {"bad": "info"}'

        pe.unconfigured_instrument(msg, "test_inst")

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/heartbeat"
        p = json.loads(messages[0].payload)
        assert p["code"] == "unconfigured_instrument"
        assert p["message"] == exp_err

        assert f"WARNING: {exp_err}" in capsys.readouterr().out

    def test_controller_timeout(self, message_bus, capsys, eh_mocks):
        exp_err = "Timed out waiting for instruments. Stopping..."

        pe.controller_timeout("test_uid", "instruments", "Stopping")

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "timeout"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_controller_state_incompatible_with_timer(
        self, message_bus, capsys, eh_mocks
    ):
        exp_err = "Timer for instrument_setup exited unexpectedly. The controller state was found to be running instead of awaiting_instruments."

        pe.controller_state_incompatible_with_timer(
            "test_uid", "instrument_setup", "awaiting_instruments", "running"
        )

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "timer_error"
        assert p["message"] == exp_err

        assert f"ERROR: {exp_err}" in capsys.readouterr().out
