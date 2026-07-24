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
from utils.tests.mocks.mock_comodo_yaml_dict import mock_comodo_yaml_dict
from utils.tests.mocks.mock_comodo_config import mock_comodo_config


@pytest.fixture
def mock_state(mock_comodo_config):
    def _mock_state(status, mock_experiment_dict={}, mock_setpoints=[]):
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
        state_obj.config = mock_comodo_config

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
            state_obj.instrument_states = {}
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
        state_obj.instrument_states = {}
        state_obj.instruments_ready = False

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
            if instrument_name not in state_obj.instrument_states:
                state_obj.instrument_states[instrument_name] = {
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
            if instrument_name in state_obj.instrument_states:
                state_obj.instrument_states[instrument_name]["last_contact"] = (
                    t.time() - 1
                )
                state_obj.instrument_states[instrument_name]["state"] = "idle"
                state_obj.instrument_states[instrument_name]["setpoints"] = None
        state_obj.instrument_states = {}
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

    return _mock_state


@pytest.fixture
def mock_experiment_dict():
    """Fixture that returns a valid experiment configuration dictionary."""
    data = {
        "id": "123",
        "config": {"resolution": 0.1},
        "experiment_definition": [
            {"time": 0, "furnace/temperature": 0, "pressure/pressure": 10},
            {"time": 3, "furnace/temperature": 0, "pressure/pressure": 150},
            {"time": 6, "furnace/temperature": 500, "pressure/pressure": 150},
            {"time": 9, "furnace/temperature": 500, "pressure/pressure": 10},
            {"time": 12, "furnace/temperature": 0, "pressure/pressure": 10},
        ],
    }
    return data


@pytest.fixture
def mock_setpoints():
    """Fixture that returns a list of setpoints as expected from split_setpoints."""
    return [
        {"duration": 9, "furnace/temperature": 20, "pressure/pressure": 200},
        {"duration": 5, "furnace/temperature": 80, "pressure/pressure": 800},
        {"duration": 7, "furnace/temperature": 50, "pressure/pressure": 500},
        {"duration": 4, "furnace/temperature": 30, "pressure/pressure": 300},
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
