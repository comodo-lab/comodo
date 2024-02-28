import json
import pytest
import time as t

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_heartbeat_message import *
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


heartbeat_client = make_client_fixture(
    client_id="heartbeat",
    callback=on_heartbeat_message,
    topics="heartbeat/#",
    autouse=True,
)


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


def test_unconfigured_sensor_idle(capmqtt, state, heartbeat_client):
    assert state.experiment_uid == "123"
    state.status = "idle"
    heartbeat_client.callback = flagged(
        on_heartbeat_message,
        flag_topic="flagged_heartbeat",
        flag_message="heartbeat_ignored",
    )

    capmqtt.publish(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps(
            {
                "name": "sensor_1",
                "status": "awaiting_config",
                "setpoint": None,
                "config": {"p": None, "i": None, "d": None, "tolerance": None},
            }
        ),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "flagged_heartbeat"
    assert capmqtt.messages[-1].payload == "heartbeat_ignored"


def test_awaiting_sensors_wrong_config(capmqtt, state):
    assert state.sensors["configured"] == False

    sensors = valid_experiment_dict()["config"]["sensors"]
    first_sensor_name = sensors[0]["name"]
    first_sensor_config = {k: v for k, v in sensors[0].items() if k != "name"}
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config

    # Incorrect heartbeat for first sensor
    wrong_config = sensors[0].copy()
    wrong_config["p"] = wrong_config["p"] + 1
    publish_sensor_heartbeat(capmqtt, wrong_config, "no_setpoint", 0)

    # Should not have updated sensor
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config
    assert state.sensors["configured"] == False


def test_awaiting_sensors_not_all_responded(capmqtt, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment_dict()["config"]["sensors"]

    # Correct heartbeat for all but first sensors
    for sensor in sensors[1:]:
        publish_sensor_heartbeat(capmqtt, sensor, "no_setpoint", None)

    # Should have updated sensors, but not be ready yet
    for sensor in sensors[1:]:
        assert state.sensors[sensor["name"]]["status"] == "no_setpoint"
        assert state.sensors[sensor["name"]]["setpoint"] == None
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False


def test_awaiting_sensors_wrong_sensor_status(capmqtt, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment_dict()["config"]["sensors"]

    # Wrong sensor status for first sensor
    publish_sensor_heartbeat(capmqtt, sensors[0], "awaiting_config", None)
    # Correct heartbeat for all but first sensors
    for sensor in sensors[1:]:
        publish_sensor_heartbeat(capmqtt, sensor, "no_setpoint", None)

    assert state.sensors[sensor["name"]]["status"] == "no_setpoint"
    assert state.sensors["configured"] == False


def test_awaiting_sensors_all_responded(capmqtt, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = valid_experiment_dict()["config"]["sensors"]

    # Correct heartbeat for all sensors
    for sensor in sensors:
        publish_sensor_heartbeat(capmqtt, sensor, "no_setpoint", None)
    wait_for_message(capmqtt)

    assert state.sensors[sensor["name"]]["status"] == "no_setpoint"
    assert state.sensors["configured"] == True
    assert state.status == "awaiting_sensors"
    assert capmqtt.messages[-1].topic == "controller/ready"
    assert json.loads(capmqtt.messages[-1].payload)["uid"] == "123"
