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

    yield cc  # To use cc in the test, the test function must include the fixture in the definition, as in `def test_something(controller_client):`

    # Teardown after test
    cc.client.disconnect()


@pytest.fixture
def valid_experiment_path():
    return "tests/file_fixtures/dummy_experiment.json"


@pytest.fixture
def invalid_experiment_path():
    return "tests/file_fixtures/invalid_experiment.json"


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
        assert capmqtt.messages[-1].topic == "controller/error"
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
        assert capmqtt.messages[-1].topic == "controller/error"
        assert (
            "Error decoding controller/validate message, missing: \n   'file'"
            in capmqtt.messages[-1].payload
        )


def test_missing_file(capmqtt, state, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"file": "missing_file.json"}),
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        assert capmqtt.messages[-1].topic == "controller/validator/failed"
        assert "File not found" in capmqtt.messages[-1].payload


def test_valid_file(capmqtt, state, valid_experiment_path, controller_client):
    assert state.experiment_uid == None
    assert state.status == "idle"

    with patch("on_controller_message.c_starting") as mock_c_starting:
        mock_c_starting.return_value = None

        capmqtt.publish(
            topic="controller/validate",
            payload=json.dumps({"file": valid_experiment_path}),
        )
        wait_for_message(capmqtt)

        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == mock_c_starting
        assert capmqtt.messages[-2].topic == "controller/validator/passed"
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
            payload=json.dumps({"file": invalid_experiment_path}),
        )
        wait_for_message(capmqtt)

    assert state.experiment_uid == None
    assert state.status == "idle"
    assert controller_client.callback == c_idle
    assert capmqtt.messages[-1].topic == "controller/validator/failed"
    assert "Validation errors" in capmqtt.messages[-1].payload
