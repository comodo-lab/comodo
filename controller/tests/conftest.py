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


def mock_state(status):
    """
    Factory to create a cstate fixture in the state it would be right before a callback is called.
    It expects a string corresponding to the callback to be tested, which should be one of:
        - "idle"
        - "starting"
        - "awaiting_sensors"
        - "ready"
        - "running"
        - "end"
    If the provided status is not one of the allowed status values, it returns None.
    """

    @pytest.fixture
    def state(mock_experiment_dict):
        if status not in [
            "idle",
            "starting",
            "awaiting_sensors",
            "ready",
            "running",
            "end",
        ]:
            return None

        obj = MagicMock(spec=cstate)
        obj._status_history = []

        # Use PropertyMock to track status changes
        def track_status(self, value):
            obj._status_history.append(value)
            obj._status_value = value

        def get_status(self):
            return obj._status_value

        obj._status_value = None
        type(obj).status = property(get_status, track_status)

        # ------------------------------- idle (default new cstate)
        obj.experiment_start_time = None
        obj.experiment_uid = None
        obj.exp_file = None
        obj.status = "idle"
        obj._status_history = []
        obj.exp_config = None
        obj.setpoints = []
        obj.current_setpoint = None
        obj.past_setpoints = []
        obj.sensors = {"configured": False}
        obj.adjusting = MagicMock(spec=AdjustingDict)
        obj.schema_path = "schemas/schema_experiment.json"
        obj.schema_sensor_heartbeat_path = "schemas/schema_sensor_heartbeat.json"

        if status == "idle":
            return obj

        # ------------------------------- starting
        obj.experiment_start_time = datetime.now()
        obj.exp_config = mock_experiment_dict
        obj.experiment_uid = mock_experiment_dict["uid"]
        obj.status = "validating"
        obj._status_history = []
        if status == "starting":
            return obj

        # ------------------------------- awaiting_sensors
        obj.status = "awaiting_sensors"
        obj._status_history = []
        for sensor in obj.exp_config["config"]["sensors"]:
            obj.sensors[sensor["name"]] = {
                "last_contact": None,
                "config": {k: v for k, v in sensor.items() if k != "name"},
                "status": None,
                "setpoint": None,
            }
        if status == "awaiting_sensors":
            return obj

        obj.setpoints = mock_setpoints
        for sensor in obj.exp_config["config"]["sensors"]:
            obj.sensors[sensor["name"]]["last_contact"] = t.time() - 1
            obj.sensors[sensor["name"]]["status"] = "no_setpoint"
        obj.sensors = {"configured": True}
        if status == "ready":
            return obj

        obj.status = "ready"
        obj._status_history = []
        if status == "running":
            return obj

        obj.status = "running"
        obj._status_history = []
        if status == "end":
            return obj

        return obj

    return state


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
