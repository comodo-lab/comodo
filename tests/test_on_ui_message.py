import json
import pytest
import time as t

from controller_state import *
from mqtt_clients import *
from on_ui_message import *


@pytest.fixture
def state():
    return cstate()


@pytest.fixture(autouse=True)
def controller_client(state):
    # Setup before test
    uic = MQTTClient("ui", on_ui_message, "ui/#", obj=state)
    # Wait until the client is connected
    while not uic.client.is_connected():
        t.sleep(0.01)

    yield uic  # Testing happens here

    # Teardown after test
    uic.client.disconnect()


@pytest.fixture
def valid_experiment():
    with open("tests/file_fixtures/dummy_experiment.json", "r") as f:
        data = json.load(f)
    return json.dumps(data)


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(0.01)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > 10:
            raise TimeoutError("Timed out waiting for message")


capmqtt_decode_utf8 = True


def test_invalid_ui_message(capmqtt, state):
    assert state.experiment_uid == None

    capmqtt.publish(topic="ui/start", payload="invalid")

    assert state.experiment_uid == None
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        f"Error decoding ui/start message, wrong JSON" in capmqtt.messages[-1].payload
    )


def test_missing_uid(capmqtt, state, valid_experiment):
    assert state.experiment_uid == None

    no_uid = valid_experiment.replace('"uid": "123",', "")
    capmqtt.publish(topic="ui/start", payload=no_uid)

    assert state.experiment_uid == None
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        f"Error decoding ui/start message, missing: \n   'uid'"
        in json.loads(capmqtt.messages[-1].payload)["error"]
    )


def test_valid_start(capmqtt, state, valid_experiment):
    assert state.experiment_uid == None
    assert state.status == "idle"

    capmqtt.publish(topic="ui/start", payload=valid_experiment)
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "controller/validate"
    assert "123.json" in capmqtt.messages[-1].payload


def test_stop_while_idle(capmqtt, state, valid_experiment):
    assert state.experiment_uid == None
    assert state.status == "idle"

    capmqtt.publish(topic="ui/stop", payload=valid_experiment)
    wait_for_message(capmqtt)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert "Controller is idle. Cannot act on ui/stop" in capmqtt.messages[-1].payload


def test_start_while_not_idle(capmqtt, state, valid_experiment):
    state.status = "running"
    state.experiment_uid = "456"

    capmqtt.publish(topic="ui/start", payload=valid_experiment)
    wait_for_message(capmqtt)

    assert state.experiment_uid == "456"
    assert state.status == "running"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is running. Cannot act on ui/start" in capmqtt.messages[-1].payload
    )


def test_stop_for_wrong_uid(capmqtt, state, valid_experiment):
    state.status = "running"
    state.experiment_uid = "456"

    capmqtt.publish(topic="ui/stop", payload=valid_experiment)
    wait_for_message(capmqtt)

    assert state.experiment_uid == "456"
    assert state.status == "running"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Current experiment is 456. Cannot act on ui/stop for experiment 123."
        in capmqtt.messages[-1].payload
    )


def test_valid_stop(capmqtt, state, valid_experiment):
    state.status = "running"
    state.experiment_uid = "123"

    capmqtt.publish(topic="ui/stop", payload=valid_experiment)
    wait_for_message(capmqtt)

    assert state.experiment_uid == "123"
    assert capmqtt.messages[-1].topic == "controller/stop"
    assert '"uid": "123"' in capmqtt.messages[-1].payload
