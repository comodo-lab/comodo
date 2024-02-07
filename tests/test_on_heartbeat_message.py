import json
import pytest
import time as t

from controller_state import *
from mqtt_clients import *
from on_heartbeat_message import *
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
def heartbeat_client(state):
    # Setup before test
    hc = MQTTClient("heartbeat", on_heartbeat_message, "heartbeat/#", obj=state)
    # Wait until the client is connected
    while not hc.client.is_connected():
        t.sleep(0.01)

    yield hc  # Testing happens here

    # Teardown after test
    hc.client.disconnect()


def wait_for_message(capmqtt):
    waiting = True
    start_time = t.time()
    while waiting:
        t.sleep(0.01)
        waiting = len(capmqtt.messages) <= 1
        if t.time() - start_time > 10:
            raise TimeoutError("Timed out waiting for message")


def publish_sensor_heartbeat(capmqtt, sensor, status, setpoint):
    capmqtt.publish(
        topic="heartbeat/sensor/" + sensor["name"],
        payload=json.dumps(
            {
                "name": sensor["name"],
                "status": status,
                "setpoint": setpoint,
                "config": {k: v for k, v in sensor.items() if k != "name"},
            }
        ),
    )


capmqtt_decode_utf8 = True


def test_incompatible_request(capmqtt, state):
    assert state.experiment_uid == "123"

    capmqtt.publish(
        topic="heartbeat/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/heartbeat"
    assert (
        "Heartbeat cannot act on heartbeat/something_else"
        in capmqtt.messages[-1].payload
    )


def test_wrong_json(capmqtt, state):
    capmqtt.publish(
        topic="heartbeat/sensor/sensor_1",
        payload="not a json",
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/heartbeat"
    assert (
        "Error decoding heartbeat/sensor/sensor_1 message, wrong JSON"
        in capmqtt.messages[-1].payload
    )


def test_missing_keys(capmqtt, state):
    capmqtt.publish(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps({"hello": "world"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/heartbeat/validation"
    m = capmqtt.messages[-1].payload
    assert "Error validating heartbeat from sensor_1:" in m
    assert "Validation errors:" in m
    assert "'name' is a required property" in m
    assert "'status' is a required property" in m
    assert "'setpoint' is a required property" in m
    assert "'config' is a required property" in m


def test_unconfigured_sensor(capmqtt, state):
    assert state.experiment_uid == "123"

    capmqtt.publish(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps(
            {
                "name": "sensor_1",
                "status": "ready",
                "setpoint": 1,
                "config": {"p": 1, "i": 1, "d": 1, "tolerance": 1},
            }
        ),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/heartbeat"
    assert "Sensor sensor_1 is not configured" in capmqtt.messages[-1].payload


def test_awaiting_sensors_wrong_config(capmqtt, state, valid_experiment):
    assert state.sensors["configured"] == False

    sensors = valid_experiment["config"]["sensors"]
    first_sensor_name = sensors[0]["name"]
    first_sensor_config = {k: v for k, v in sensors[0].items() if k != "name"}
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config

    # Incorrect heartbeat for first sensor
    wrong_config = sensors[0].copy()
    wrong_config["p"] = wrong_config["p"] + 1
    publish_sensor_heartbeat(capmqtt, wrong_config, "awaiting_setpoint", 0)

    # Should not have updated sensor
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config
    assert state.sensors["configured"] == False


def test_awaiting_sensors_not_all_responded(capmqtt, state, valid_experiment):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment["config"]["sensors"]

    # Correct heartbeat for all but first sensors
    for sensor in sensors[1:]:
        publish_sensor_heartbeat(capmqtt, sensor, "awaiting_setpoint", None)

    # Should have updated sensors, but not be ready yet
    for sensor in sensors[1:]:
        assert state.sensors[sensor["name"]]["status"] == "awaiting_setpoint"
        assert state.sensors[sensor["name"]]["setpoint"] == None
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False


def test_awaiting_sensors_wrong_sensor_status(capmqtt, state, valid_experiment):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment["config"]["sensors"]

    # Wrong sensor status for first sensor
    publish_sensor_heartbeat(capmqtt, sensors[0], "awaiting_config", None)
    # Correct heartbeat for all but first sensors
    for sensor in sensors[1:]:
        publish_sensor_heartbeat(capmqtt, sensor, "awaiting_setpoint", None)

    assert state.sensors[sensor["name"]]["status"] == "awaiting_setpoint"
    assert state.sensors["configured"] == False


def test_awaiting_sensors_all_responded(capmqtt, state, valid_experiment):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment["config"]["sensors"]

    # Correct heartbeat for all sensors
    for sensor in sensors:
        publish_sensor_heartbeat(capmqtt, sensor, "awaiting_setpoint", None)
    wait_for_message(capmqtt)

    assert state.sensors[sensor["name"]]["status"] == "awaiting_setpoint"
    assert state.sensors["configured"] == True
    assert state.status == "awaiting_sensors"
    assert capmqtt.messages[-1].topic == "controller/ready"
    assert json.loads(capmqtt.messages[-1].payload)["uid"] == "123"
