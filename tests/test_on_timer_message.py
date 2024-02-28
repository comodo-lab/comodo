import json
import pytest
import time as t

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_timer_message import *
from unittest.mock import patch


state = make_state_fixture("awaiting_sensors")

timer_client = make_client_fixture(
    client_id="timer",
    callback=on_timer_message,
    topics="timer/#",
    autouse=True,
)


def test_incompatible_request(capmqtt, state):
    assert state.experiment_uid == "123"

    capmqtt.publish(
        topic="timer/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/timer"
    assert "Timer cannot act on timer/something_else" in capmqtt.messages[-1].payload


def test_timeout(capmqtt, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    with patch("on_timer_message.sensor_setup_wait", 0.3):
        capmqtt.publish(
            topic="timer/start/sensor_setup",
            payload=json.dumps({"uid": "123"}),
        )
        wait_for_message(capmqtt)

    assert capmqtt.messages[-2].topic == "error/controller/timeout"
    assert "Timed out waiting for sensors. Stopping..." in capmqtt.messages[-2].payload
    assert capmqtt.messages[-1].topic == "controller/stop"
    assert '{"uid": "123"' in capmqtt.messages[-1].payload


def test_sensors_configured(capmqtt, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    timer_client.callback = flagged(
        on_timer_message,
        flag_topic="flagged_timer",
        flag_message="timer not engaged",
    )
    with patch("on_timer_message.sensor_setup_wait", 0.3):
        capmqtt.publish(
            topic="timer/start/sensor_setup",
            payload=json.dumps({"uid": "123"}),
        )
        t.sleep(0.1)
        state.sensors["configured"] = True
        wait_for_message(capmqtt)

    assert capmqtt.messages[0].topic == "timer/start/sensor_setup"
    assert len(capmqtt.messages) == 2
    assert capmqtt.messages[-1].topic == "flagged_timer"
    assert capmqtt.messages[-1].payload == "timer not engaged"


def test_changed_controller_state(capmqtt, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    timer_client.callback = flagged(
        on_timer_message,
        flag_topic="flagged_timer",
        flag_message="timer not engaged",
    )
    with patch("on_timer_message.sensor_setup_wait", 0.3):
        capmqtt.publish(
            topic="timer/start/sensor_setup",
            payload=json.dumps({"uid": "123"}),
        )
        t.sleep(0.1)
        state.status = "idle"
        wait_for_message(capmqtt)

    assert capmqtt.messages[0].topic == "timer/start/sensor_setup"
    assert len(capmqtt.messages) == 2
    assert capmqtt.messages[-1].topic == "flagged_timer"
    assert capmqtt.messages[-1].payload == "timer not engaged"


def test_timer_setpoint(capmqtt, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "running"

    capmqtt.publish(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123", "duration": 0.3}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "controller/run"
    assert capmqtt.messages[-1].payload == '{"uid": "123"}'


def test_timer_setpoint_missing_duration(capmqtt, state):
    assert state.experiment_uid == "123"
    state.status = "running"

    capmqtt.publish(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/timer"
    assert "Error decoding timer/start/setpoint message" in capmqtt.messages[-1].payload
    assert "missing" in capmqtt.messages[-1].payload
    assert "duration" in capmqtt.messages[-1].payload


def test_timer_setpoint_incompatible_controller_state(capmqtt, state):
    assert state.experiment_uid == "123"
    state.status = "ready"

    capmqtt.publish(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123", "duration": 0.3}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/controller/timer/setpoint"
    m = json.loads(capmqtt.messages[-1].payload)
    assert m["uid"] == "123"
    assert "Timer for setpoint exited unexpectedly."
    assert "ready instead of running" in m["error"]
