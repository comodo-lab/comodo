import json
import pytest
import time as t

from controller_state import *
from mqtt_clients import *
from on_controller_message import *
from unittest.mock import patch


@pytest.fixture
def state():
    return cstate()


@pytest.fixture(autouse=False)
def controller_client(state):
    # Setup before test
    cc = MQTTClient("controller", c_idle, "controller/#", obj=state)
    # Wait until the client is connected
    while not cc.client.is_connected():
        t.sleep(0.01)

    yield cc  # Testing happens here.

    # Teardown after test
    cc.client.disconnect()


@pytest.fixture
def valid_experiment_path():
    return "tests/file_fixtures/dummy_experiment.json"


@pytest.fixture
def invalid_experiment_path():
    return "tests/file_fixtures/invalid_experiment.json"


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(0.01)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > 10:
            raise TimeoutError("Timed out waiting for message")


capmqtt_decode_utf8 = True


def test_incompatible_request(capmqtt, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    capmqtt.publish(
        topic="controller/run",
        payload="not important",
    )
    wait_for_message(capmqtt)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is idle. Cannot act on controller/run"
        in capmqtt.messages[-1].payload
    )


def test_wrong_json(capmqtt, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload="this is not json",
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        assert capmqtt.messages[-1].topic == "error/controller"
        assert (
            "Error decoding controller/validate message, wrong JSON"
            in capmqtt.messages[-1].payload
        )


def test_json_missing_file_key(capmqtt, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"uid": "123"}),
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        assert capmqtt.messages[-1].topic == "error/controller"
        assert (
            "Error decoding controller/validate message, missing: \n   'file'"
            in json.loads(capmqtt.messages[-1].payload)["error"]
        )


def test_missing_file(capmqtt, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": "missing_file.json"}),
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        assert capmqtt.messages[-1].topic == "error/validator/failed"
        assert "File not found" in capmqtt.messages[-1].payload


def test_valid_file(capmqtt, state, valid_experiment_path, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": valid_experiment_path}),
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == mock_c_starting
        assert capmqtt.messages[-2].topic == "validator/passed"
        assert '{"uid": "123", "valid": true}' in capmqtt.messages[-2].payload
        assert capmqtt.messages[-1].topic == "controller/start"
        assert '{"uid": "123"}' in capmqtt.messages[-1].payload


def test_invalid_file(capmqtt, state, invalid_experiment_path, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": invalid_experiment_path}),
        )
        wait_for_message(capmqtt)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    assert capmqtt.messages[-1].topic == "error/validator/failed"
    assert "Validation errors" in capmqtt.messages[-1].payload
    assert '"uid": "123"' in capmqtt.messages[-1].payload
