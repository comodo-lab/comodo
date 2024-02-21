import json
import pytest
import time as t

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_timer_message import *
from unittest.mock import patch


@pytest.fixture
def state():
    obj = cstate()
    obj.exp_config = valid_experiment_dict()
    obj.experiment_uid = valid_experiment_dict()["uid"]
    obj.status = "awaiting_sensors"
    obj.sensors = {"configured": False}
    for sensor in obj.exp_config["config"]["sensors"]:
        obj.sensors[sensor["name"]] = {
            "last_contact": None,
            "config": {k: v for k, v in sensor.items() if k != "name"},
            "status": None,
            "setpoint": None,
        }
    return obj


timer_client = make_client_fixture(
    client_id="timer",
    callback=on_timer_message,
    topics="timer/#",
    autouse=True,
)


def flagged_on_timer_message(*args, **kwargs):
    """
    Used to check if the on_timer_message callback has finished without an error.
    Normally, the on_timer_message function is silent unless there are errors.
    When this callback is used instead, a message is published once the original on_timer_message function is done.
    """
    on_timer_message(*args, **kwargs)
    pub.publish("engaged_timer", "false")


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
    assert "Timed out waiting for sensors. Exiting..." in capmqtt.messages[-2].payload
    assert capmqtt.messages[-1].topic == "controller/stop"
    assert '{"uid": "123"' in capmqtt.messages[-1].payload


def test_sensors_configured(capmqtt, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    timer_client.callback = flagged_on_timer_message
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
    assert capmqtt.messages[-1].topic == "engaged_timer"
    assert capmqtt.messages[-1].payload == "false"


def test_changed_controller_state(capmqtt, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    timer_client.callback = flagged_on_timer_message
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
    assert capmqtt.messages[-1].topic == "engaged_timer"
    assert capmqtt.messages[-1].payload == "false"
