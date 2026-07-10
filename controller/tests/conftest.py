"""Shared pytest fixtures and utilities for controller tests."""

import pytest
from unittest.mock import PropertyMock, patch, MagicMock
import json
from random import uniform as rand
import time as t
from datetime import datetime

from src.controller_state import cstate

from utils.tests.mocks.mock_mqtt_clients import (
    pytest_runtest_makereport,
    MockMessage,
    InMemoryMessageBus,
    message_bus,
    mqtt_mocks,
    parse_message_args,
)


def mock_state(status, mock_experiment_dict={}, mock_setpoints=[]):
    """
    Factory to create a cstate fixture in the state it would be right before a callback is called.
    It expects a string corresponding to the callback to be tested, which should be one of:
        - "idle"
        - "starting"
        - "awaiting_instruments"
        - "ready"
        - "running"
        - "end"
    If the provided status is not one of the allowed status values, it returns None.
    """
    if status not in [
        "idle",
        "starting",
        "awaiting_instruments",
        "ready",
        "running",
        "end",
    ]:
        return None

    state_obj = MagicMock(spec=cstate)
    state_obj._status_history = []

    # Mock the config object
    state_obj.config = MagicMock()
    state_obj.config.globals = {"instrument_setup_wait": 10}
    state_obj.config.get_expected_heartbeat.return_value = {
        "firmware": "test",
        "device_address": "1.2.3.4",
        "simulate": True,
        "variables": [],
    }
    state_obj.config.instruments = {
        "furnace_centre": {
            "variables": {"temperature": {"actuator": {"min": 0, "max": 1000}}}
        },
        "mass_flow": {
            "variables": {"mass_flow": {"actuator": {"min": 0, "max": 100}}}
        },
        "furnace_left": {
            "variables": {"temperature": {"sensor": {"interval": 1.0}}}
        },
    }

    # Use PropertyMock to track status changes
    def track_status(self, value):
        state_obj._status_history.append(value)
        state_obj._status_value = value

    def get_status(self):
        return state_obj._status_value

    state_obj._status_value = None
    type(state_obj).status = property(get_status, track_status)

    def reset():
        state_obj.experiment_start_time = None
        state_obj.experiment_uid = None
        state_obj.exp_file = None
        state_obj.status = "idle"
        state_obj.exp_config = None
        state_obj.setpoints = []
        state_obj.current_setpoint = None
        state_obj.past_setpoints = []
        state_obj.instruments = {}
        state_obj.instruments_ready = False

    state_obj.reset = MagicMock(side_effect=reset)

    # ------------------------------- idle (default new cstate)
    state_obj.experiment_start_time = None
    state_obj.experiment_uid = None
    state_obj.exp_file = None
    state_obj.status = "idle"
    state_obj._status_history = []
    state_obj.exp_config = None
    state_obj.setpoints = []
    state_obj.current_setpoint = None
    state_obj.past_setpoints = []
    state_obj.instruments = {}
    state_obj.instruments_ready = False
    state_obj.actuator_variables = {"furnace_centre/temperature", "mass_flow/mass_flow"}
    av_set = state_obj.actuator_variables
    sv_set = {
        "furnace_centre/temperature",
        "furnace_left/temperature",
        "furnace_right/temperature",
        "pressure_downstream/pressure",
        "pressure_upstream/pressure",
        "mass_flow/mass_flow",
        "mass_flow/temperature",
        "mass_flow/pressure_upstream",
        "mass_flow/pressure_downstream",
        "mass_spec/mass_spec",
    }
    sensor_inst = {sv.split("/", 1)[0] for sv in sv_set}
    actuator_inst = {av.split("/", 1)[0] for av in av_set}
    expected_sensor_instruments = sensor_inst - actuator_inst
    type(state_obj).actuator_instruments = PropertyMock(return_value=actuator_inst)
    type(state_obj).sensor_instruments = PropertyMock(
        return_value=expected_sensor_instruments
    )
    state_obj.sensor_variables = sv_set

    if status == "idle":
        return state_obj

    # ------------------------------- starting
    state_obj.experiment_start_time = datetime.now()
    state_obj.exp_config = mock_experiment_dict
    state_obj.experiment_uid = mock_experiment_dict["id"]
    state_obj.status = "validating"
    state_obj._status_history = []
    if status == "starting":
        return state_obj

    # ------------------------------- awaiting_instruments
    state_obj.status = "awaiting_instruments"
    state_obj._status_history = []
    for instrument_name in state_obj.config.instruments:
        if instrument_name not in state_obj.instruments:
            state_obj.instruments[instrument_name] = {
                "last_contact": None,
                "config": {
                    "firmware": "test",
                    "device_address": "1.2.3.4",
                    "simulate": True,
                    "variables": [],
                },
                "state": None,
                "setpoints": None,
            }
    if status == "awaiting_instruments":
        return state_obj

    state_obj.setpoints = mock_setpoints
    for instrument_name in state_obj.config.instruments:
        if instrument_name in state_obj.instruments:
            state_obj.instruments[instrument_name]["last_contact"] = t.time() - 1
            state_obj.instruments[instrument_name]["state"] = "idle"
            state_obj.instruments[instrument_name]["setpoints"] = None
    state_obj.instruments = {}
    if status == "ready":
        return state_obj

    state_obj.status = "ready"
    state_obj._status_history = []
    if status == "running":
        return state_obj

    state_obj.status = "running"
    state_obj._status_history = []
    if status == "end":
        return state_obj

    return state_obj


@pytest.fixture
def mock_experiment_dict():
    """Fixture that returns a valid experiment configuration dictionary."""
    with open("tests/file_fixtures/dummy_experiment.json", "r") as f:
        data = json.load(f)
    return data


@pytest.fixture
def mock_setpoints():
    """Fixture that returns a list of setpoints as expected from split_setpoints."""
    return [
        {"duration": 9, "furnace_centre/temperature": 20, "mass_flow/mass_flow": 200},
        {"duration": 5, "furnace_centre/temperature": 80, "mass_flow/mass_flow": 800},
        {"duration": 7, "furnace_centre/temperature": 50, "mass_flow/mass_flow": 500},
        {"duration": 4, "furnace_centre/temperature": 30, "mass_flow/mass_flow": 300},
    ]


@pytest.fixture
def mock_c_stopping():
    with patch("src.on_controller_message.c_stopping") as mock_c_stopping:
        mock_c_stopping.return_value = None
        mock_c_stopping.__name__ = "mock_c_stopping"
        yield mock_c_stopping


@pytest.fixture(autouse=True)
def mock_asyncapi_spec():
    asyncapi_topic_map = {
        "ui/start": {
            "name": "uiStart",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "config", "experiment_definition"],
                "properties": {
                    "id": {"type": "string"},
                    "config": {"type": "object", "additionalProperties": True},
                    "experiment_definition": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                },
            },
        },
        "instruments/+/heartbeat": {
            "name": "instrumentHeartbeat",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["config", "setpoints", "state"],
                "properties": {
                    "config": {"type": "object"},
                    "setpoints": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                    "state": {
                        "type": "string",
                        "enum": ["idle", "adjusting", "ready", "error"],
                    },
                },
            },
        },
    }

    experiment_row_topic_map = {
        "experiment/row": {
            "name": "experimentRow",
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "time",
                    "furnace_centre/temperature",
                    "mass_spec/mass_spec",
                ],
                "properties": {
                    "time": {"type": "number", "minimum": 0},
                    "furnace_centre/temperature": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1000,
                    },
                    "mass_spec/mass_spec": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
            },
        },
    }

    def _mock_load_spec(schema_name="asyncapi"):
        if schema_name == "experiment_row":
            return experiment_row_topic_map
        return asyncapi_topic_map

    with patch("utils.mqtt_validator.load_spec", side_effect=_mock_load_spec):
        yield
