import json
import pytest
import time as t

from controller_state import *
from mqtt_clients import *
from on_timer_message import *
from unittest.mock import patch


@pytest.fixture
def valid_experiment():
    with open("tests/file_fixtures/dummy_experiment.json", "r") as f:
        data = json.load(f)
    return data


@pytest.fixture
def state(valid_experiment):
    obj = cstate()
    obj.exp_config = valid_experiment
    obj.experiment_uid = valid_experiment["uid"]
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


@pytest.fixture(autouse=True)
def timer_client(state):
    # Setup before test
    tc = MQTTClient("timer", on_timer_message, "timer/#", obj=state)
    # Wait until the client is connected
    while not tc.client.is_connected():
        t.sleep(0.01)

    yield tc  # Testing happens here

    # Teardown after test
    tc.client.disconnect()


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(0.01)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > 10:
            raise TimeoutError("Timed out waiting for message")


def flagged_on_timer_message(*args, **kwargs):
    """
    Used to check if the on_timer_message callback has finished without an error.
    Normally, the on_timer_message function is silent unless there are errors.
    When this callback is used instead, a message is published once the original on_timer_message function is done.
    """
    on_timer_message(*args, **kwargs)
    pub.publish("engaged_timer", "false")


capmqtt_decode_utf8 = True


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

    assert capmqtt.messages[-2].topic == "error/controller"
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
