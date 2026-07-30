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
    def pe_mocks(self, message_bus, mock_state):
        mock_cstate = mock_state("end")
        mock_msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"id": "test_uid"}).encode("utf-8"),
        )

        def get_decoded_bus_messages(topic=None):
            return message_bus.get_messages(topic=topic, decoded=True)

        yield {
            "cstate": mock_cstate,
            "msg": mock_msg,
            "messages": get_decoded_bus_messages,
        }

    def test_message_validation(self, capsys, pe_mocks):
        exp_err = "Invalid message format."

        pe.message_validation(MQTTValidationException(exp_err))

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "message_validation"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert captured[0] == f"MQTT validation error: {exp_err}"
        assert captured[1] == f"ERROR: {exp_err}"

    def test_wrong_json(self, capsys, pe_mocks):
        exp_err_l1 = f"Cannot decode {pe_mocks['msg'].topic} message, wrong JSON: "
        exp_err_l2 = "   Invalid JSON: line 1 column 1 (char 0)"

        pe.wrong_json(pe_mocks["msg"], json.JSONDecodeError("Invalid JSON", "", 0))

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "malformed_json"
        assert p["message"] == exp_err_l1 + "\n" + exp_err_l2

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert captured[0] == f"ERROR: {exp_err_l1}"
        assert captured[1] == exp_err_l2

    def test_missing_keys(self, capsys, pe_mocks):
        exp_err_l1 = f"Cannot decode {pe_mocks['msg'].topic} message, missing: "
        exp_err_l2 = "   'id'"

        pe.missing_keys(pe_mocks["msg"], KeyError("id"))

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "missing_key"
        assert p["message"] == exp_err_l1 + "\n" + exp_err_l2

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert captured[0] == f"ERROR: {exp_err_l1}"
        assert captured[1] == exp_err_l2

    def test_incompatible_controller_status(self, capsys, pe_mocks):
        exp_err = f"Controller status is {pe_mocks['cstate'].status}. Cannot act on {pe_mocks['msg'].topic}."

        pe.incompatible_controller_status(pe_mocks["cstate"], pe_mocks["msg"])

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_controller_status"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {exp_err}"

    def test_incompatible_topic(self, capsys, pe_mocks):
        exp_err = f"The test caller cannot act on {pe_mocks['msg'].topic}."

        pe.incompatible_topic(pe_mocks["cstate"], pe_mocks["msg"], "test_caller")

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/test_caller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_topic"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {exp_err}"

    def test_incompatible_uid(self, capsys, pe_mocks):
        exp_err = f"Current experiment is {pe_mocks['cstate'].experiment_uid}. Test caller cannot act on {pe_mocks['msg'].topic} for experiment 567."

        pe.incompatible_uid(pe_mocks["cstate"], pe_mocks["msg"], 567, "test_caller")

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/test_caller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "incompatible_uid"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {exp_err}"

    def test_experiment_validation_error(self, capsys, pe_mocks):
        eve = ExperimentValidationError("Invalid experiment configuration.")
        exp_err = f"Validation failed for UID:test_uid. Error detials: ExperimentValidationError: Invalid experiment configuration."

        pe.experiment_validation_error(eve, "test_uid")

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        p = json.loads(messages[0].payload)
        assert p["code"] == "experiment_validation"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert (
            captured[0]
            == f"Experiment validation error: Invalid experiment configuration."
        )

        assert captured[1] == f"ERROR: {exp_err}"

    def test_heartbeat_validation_error(self, capsys, pe_mocks):
        mqttve = MQTTValidationException("Invalid heartbeat format.")
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err = 'Invalid heartbeat from test_inst: {"bad": "info"}. Invalid heartbeat format.'

        pe.heartbeat_validation_error(msg, mqttve)

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/heartbeat"
        p = json.loads(messages[0].payload)
        assert p["code"] == "heartbeat_validation"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert captured[0] == f"MQTT validation error: Invalid heartbeat format."
        assert captured[1] == f"ERROR: {exp_err}"

    def test_unconfigured_instrument(self, capsys, pe_mocks):
        msg = MockMessage(topic="ins/test_inst/hb", payload=json.dumps({"bad": "info"}))
        exp_err_l1 = (
            "Instrument test_inst is not configured. Unexpected heartbeat message:"
        )
        exp_err_l2 = '    ins/test_inst/hb  {"bad": "info"}'

        pe.unconfigured_instrument(msg, "test_inst")

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/heartbeat"
        p = json.loads(messages[0].payload)
        assert p["code"] == "unconfigured_instrument"
        assert p["message"] == exp_err_l1 + "\n" + exp_err_l2

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 2
        assert captured[0] == f"WARNING: {exp_err_l1}"
        assert captured[1] == exp_err_l2

    def test_controller_timeout(self, capsys, pe_mocks):
        exp_err = "Timed out waiting for instruments. Stopping..."

        pe.controller_timeout("test_uid", "instruments", "Stopping")

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "timeout"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {exp_err}"

    def test_controller_state_incompatible_with_timer(self, capsys, pe_mocks):
        exp_err = "Timer for instrument_setup exited unexpectedly. The controller state was found to be running instead of awaiting_instruments."

        pe.controller_state_incompatible_with_timer(
            "test_uid", "instrument_setup", "awaiting_instruments", "running"
        )

        messages = pe_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        p = json.loads(messages[0].payload)
        assert p["code"] == "timer_error"
        assert p["message"] == exp_err

        captured = capsys.readouterr().out.splitlines()
        assert len(captured) == 1
        assert captured[0] == f"ERROR: {exp_err}"
