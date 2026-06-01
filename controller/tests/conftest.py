"""Shared pytest fixtures and utilities for controller tests."""

import pytest
from unittest.mock import PropertyMock, patch, MagicMock
import json
from random import uniform as rand
import time as t
from datetime import datetime

from src.controller_state import cstate, AdjustingDict

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
        state_obj.instruments = {"configured": False}

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
    state_obj.instruments = {"configured": False}
    state_obj.adjusting = MagicMock(spec=AdjustingDict)
    state_obj.schema_path = "schemas/schema_experiment.json"
    state_obj.schema_instrument_heartbeat_path = "schemas/schema_instrument_heartbeat.json"

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
    for instrument in state_obj.exp_config["config"]["instruments"]:
        state_obj.instruments[instrument["name"]] = {
            "last_contact": None,
            "config": {
                **{k: v for k, v in instrument.items() if k != "name"},
                "experiment_id": state_obj.experiment_uid,
            },
            "state": None,
            "setpoints": None,
        }
    if status == "awaiting_instruments":
        return state_obj

    state_obj.setpoints = mock_setpoints
    for instrument in state_obj.exp_config["config"]["instruments"]:
        state_obj.instruments[instrument["name"]]["last_contact"] = t.time() - 1
        state_obj.instruments[instrument["name"]]["state"] = "idle"
        state_obj.instruments[instrument["name"]]["setpoints"] = None
    state_obj.instruments = {"configured": True}
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
        {"duration": 9, "temperature": 20, "pressure": 200},
        {"duration": 5, "temperature": 80, "pressure": 800},
        {"duration": 7, "temperature": 50, "pressure": 500},
        {"duration": 4, "temperature": 30, "pressure": 300},
    ]


@pytest.fixture
def mock_c_stopping():
    with patch("src.on_controller_message.c_stopping") as mock_c_stopping:
        mock_c_stopping.return_value = None
        mock_c_stopping.__name__ = "mock_c_stopping"
        yield mock_c_stopping


def instrument_heartbeat_msg(instrument, state, setpoints, experiment_id=None):
    """Helper function to create a instrument heartbeat mock message."""
    config = {k: v for k, v in instrument.items() if k != "name"}
    config.setdefault("experiment_id", experiment_id)
    return MockMessage(
        topic=f"instruments/{instrument['name']}/heartbeat",
        payload=json.dumps(
            {
                "state": state,
                "setpoints": setpoints,
                "config": config,
            }
        ),
    )
