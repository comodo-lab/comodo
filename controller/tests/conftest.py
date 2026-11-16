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
from utils.tests.mocks.mock_mqtt_validator import mqtt_validator_mocks
from utils.tests.mocks.mock_comodo_yaml_dict import mock_comodo_yaml_dict
from utils.tests.mocks.mock_comodo_config import mock_comodo_config
from utils.tests.mocks.mock_experiment import mock_experiment_dict, mock_setpoints


@pytest.fixture
def mock_state(mock_comodo_config, mock_experiment_dict, mock_setpoints):
    def _mock_state(status):
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
        state_obj.heartbeat = MagicMock(
            return_value={
                "config": {"experiment_id": None},
                "setpoints": {},
                "state": {"status": "idle"},
            }
        )

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
            state_obj.experiment_id = None
            state_obj.exp_file = None
            state_obj.status = "idle"
            state_obj.exp_config = None
            state_obj.setpoints = []
            state_obj.current_setpoint = None
            state_obj.past_setpoints = []
            state_obj.instrument_states = {}
            state_obj.spc_states = {}
            state_obj.expected_heartbeats = {
                "furnace": mock_comodo_config.get_expected_heartbeat("furnace"),
                "pressure": mock_comodo_config.get_expected_heartbeat("pressure"),
                "mass_flow": mock_comodo_config.get_expected_heartbeat("mass_flow"),
            }
            state_obj.instruments_ready = False

        state_obj.reset = MagicMock(side_effect=reset)
        state_obj.get_expected_spc_config = lambda spc_id: (
            None
            if state_obj.exp_config is None
            else state_obj.exp_config["config"].get("spcs", {}).get(spc_id, None)
        )
        state_obj.get_expected_heartbeat = (
            lambda instrument_name: state_obj.expected_heartbeats.get(
                instrument_name, {}
            )
        )

        # ------------------------------- idle (default new cstate)
        state_obj.experiment_start_time = None
        state_obj.experiment_id = None
        state_obj.exp_file = None
        state_obj.status = "idle"
        state_obj._status_history = []
        state_obj.exp_config = None
        state_obj.setpoints = []
        state_obj.current_setpoint = None
        state_obj.past_setpoints = []
        state_obj.instrument_states = {}
        state_obj.spc_states = {}
        state_obj.expected_heartbeats = {
            "furnace": mock_comodo_config.get_expected_heartbeat("furnace"),
            "pressure": mock_comodo_config.get_expected_heartbeat("pressure"),
            "mass_flow": mock_comodo_config.get_expected_heartbeat("mass_flow"),
        }
        state_obj.instruments_ready = False

        if status == "idle":
            return state_obj

        # ------------------------------- starting
        state_obj.set_hb_experiment_config(
            "furnace", mock_experiment_dict["config"]["instruments"]["furnace"]
        )
        state_obj._expected_heartbeats["furnace"]["experiment"][
            "experiment_id"
        ] = "D123-456"
        state_obj.set_hb_experiment_config("pressure", {"experiment_id": "D123-456"})
        state_obj.set_hb_experiment_config("mass_flow", {"experiment_id": "D123-456"})

        state_obj.experiment_start_time = datetime.now()
        state_obj.exp_config = mock_experiment_dict
        state_obj.experiment_id = "D123-456"
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
                        "address": "1.2.3.4",
                        "simulate": True,
                        "variables": [],
                    },
                    "state": None,
                    "setpoints": None,
                }
        for spc_id in state_obj.config.spcs:
            if spc_id not in state_obj.spc_states:
                state_obj.spc_states[spc_id] = {"last_contact": None, "config": None}
        if status == "awaiting_instruments":
            return state_obj

        state_obj.setpoints = mock_setpoints
        for instrument_name in state_obj.config.instruments:
            if instrument_name in state_obj.instrument_states:
                state_obj.instrument_states[instrument_name]["last_contact"] = (
                    t.time() - 1
                )
                state_obj.instrument_states[instrument_name]["state"] = {
                    "status": "idle"
                }
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
def mock_serial_id():
    with patch("src.on_controller_message.assign_serial_id") as mock_assign_serial_id:

        def side_effect(obj):
            obj.experiment_id = "D123-456"
            obj.exp_file = "/path/to/experiment/D123-456.json"

        mock_assign_serial_id.side_effect = side_effect
        yield mock_assign_serial_id


@pytest.fixture
def mock_c_stopping():
    with patch("src.on_controller_message.c_stopping") as mock_c_stopping:
        mock_c_stopping.return_value = None
        mock_c_stopping.__name__ = "mock_c_stopping"
        yield mock_c_stopping
