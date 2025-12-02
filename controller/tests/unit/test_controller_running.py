import json
import pytest

from tests.tests_helper import *

from controller_state import *
from utils.mqtt_clients import *
from on_controller_message import *
from unittest.mock import patch


state = make_state_fixture("running")

controller_client = make_client_fixture(
    client_id="controller",
    callback=c_running,
    topics="controller/#",
    autouse=False,
)


def test_incompatible_request(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running

    capmqtt.publish(
        topic="controller/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.status == "ready"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is ready. Cannot act on controller/something_else"
        in capmqtt.messages[-1].payload
    )


def test_accepts_stop_signal(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running

    with patch("on_controller_message.c_stopping") as mock_stopping:
        capmqtt.publish(
            topic="controller/stop",
            payload="not important",
        )

    assert mock_stopping.called


def test_updates_state_on_first_setpoint_only(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    assert state.setpoints != []

    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    # Should update state on first setpoint
    assert state.status == "running"

    # Should not update state on second setpoint
    state.status = "idle"
    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.status == "idle"


def test_sets_current_setpoint(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.current_setpoint == all_setpoints[0]


def test_drops_current_setpoint_from_list(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.setpoints == all_setpoints[1:]


def test_sends_setpoint(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-2].topic == "sensor/setpoint"
    assert json.loads(capmqtt.messages[-2].payload) == all_setpoints[0]


def test_starts_timer(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "ready"
    assert controller_client.callback == c_running
    assert state.current_setpoint is None
    all_setpoints = state.setpoints.copy()
    assert all_setpoints != []

    capmqtt.publish(
        topic="controller/run",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "timer/start/setpoint"
    assert json.loads(capmqtt.messages[-1].payload) == {"uid": "123", "duration": 0}


def test_saves_and_clears_last_setpoint(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert controller_client.callback == c_running
    state.status == "running"
    last_setpoint = state.setpoints[-1].copy()
    state.current_setpoint = last_setpoint.copy()
    state.setpoints = []

    with patch("on_controller_message.c_stopping") as mock_stopping:
        mock_stopping.return_value = None
        capmqtt.publish(
            topic="controller/run",
            payload=json.dumps({"uid": "123"}),
        )
        wait_for_message(capmqtt)

    assert state.current_setpoint is None
    assert state.past_setpoints == [last_setpoint]


def test_sends_end_signal(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert controller_client.callback == c_running
    state.status == "running"
    state.current_setpoint = state.setpoints[-1]
    state.setpoints = []

    with patch("on_controller_message.c_stopping") as mock_stopping:
        mock_stopping.return_value = None
        mock_stopping.__name__ = "mock_stopping"
        capmqtt.publish(
            topic="controller/run",
            payload=json.dumps({"uid": "123"}),
        )
        wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "controller/end"
    assert json.loads(capmqtt.messages[-1].payload) == {"uid": "123"}
