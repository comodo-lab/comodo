import json
import pytest
import time as t

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_controller_message import *
from unittest.mock import patch


@pytest.fixture
def state():
    obj = cstate()
    obj.exp_config = valid_experiment_dict()
    obj.experiment_uid = valid_experiment_dict()["uid"]
    obj.status = "awaiting_sensors"
    obj.sensors = {"configured": True}
    for sensor in obj.exp_config["config"]["sensors"]:
        obj.sensors[sensor["name"]] = {
            "last_contact": t.time() - 1,
            "config": {k: v for k, v in sensor.items() if k != "name"},
            "status": "awaiting_setpoint",
            "setpoint": None,
        }
    return obj


@pytest.fixture(autouse=False)
def controller_client(state):
    # Setup before test
    cc = MQTTClient("controller", c_ready, "controller/#", obj=state)
    # Wait until the client is connected
    while not cc.client.is_connected():
        t.sleep(0.01)

    yield cc  # Testing happens here

    # Teardown after test
    cc.client.disconnect()


def test_incompatible_request(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    capmqtt.publish(
        topic="controller/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.status == "awaiting_sensors"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is awaiting_sensors. Cannot act on controller/something_else"
        in capmqtt.messages[-1].payload
    )


def test_accepts_stop_signal(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    with patch("on_controller_message.c_stopping") as mock_stopping:
        capmqtt.publish(
            topic="controller/stop",
            payload="not important",
        )

    assert mock_stopping.called


# def test_valid_ready_signal

# serial id created correctly
# callback updated correctly
# message controller/run {uid} sent
