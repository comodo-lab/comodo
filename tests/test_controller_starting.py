import json
import pytest
import time as t

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_controller_message import *
from unittest.mock import patch


state = make_state_fixture("starting")

controller_client = make_client_fixture(
    client_id="controller",
    callback=c_starting,
    topics="controller/#",
    autouse=False,
)


def test_incompatible_request(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    capmqtt.publish(
        topic="controller/run",
        payload="not important",
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is validating. Cannot act on controller/run"
        in capmqtt.messages[-1].payload
    )


def test_accepts_stop_signal(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    with patch("on_controller_message.c_stopping") as mock_stopping:
        capmqtt.publish(
            topic="controller/stop",
            payload="not important",
        )

    assert mock_stopping.called


def test_valid_start(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "validating"
    assert controller_client.callback == c_starting

    sensors = valid_experiment_dict()["config"]["sensors"]
    sensor_names = [sensor["name"] for sensor in sensors]
    ns = len(sensors)

    capmqtt.publish(
        topic="controller/start",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    # State object updated correctly
    assert state.experiment_uid == "123"
    assert state.setpoints is not None
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready
    # Sensor config list updated correctly
    assert len(state.sensors) == ns + 1
    assert state.sensors["configured"] == False
    for sensor_key in state.sensors.keys():
        if sensor_key != "configured":
            assert sensor_key in sensor_names
            sensor = state.sensors[sensor_key]
            assert "last_contact" in sensor
            assert sensor["last_contact"] is None
            assert "config" in sensor
            assert sensor["config"] is not None
            assert "status" in sensor
            assert sensor["status"] is None
            assert "setpoint" in sensor
            assert sensor["setpoint"] is None
    # Timer called correctly
    assert capmqtt.messages[-ns - 1].topic == "timer/start/sensor_setup"
    assert capmqtt.messages[-ns - 1].payload == json.dumps({"uid": "123"})
    # Sensor setup messages sent
    for i, sensor in enumerate(sensors):
        assert capmqtt.messages[-ns + i].topic == f"sensor/{sensor['name']}/setup"
        assert capmqtt.messages[-ns + i].payload == json.dumps(sensor)


def test_split_setpoints():
    setpoints = [
        {
            "time": 0,
            "pressure": 0,
            "temperature": 0,
            "displacement 1": 0,
            "displacement 2": 0,
        },
        {
            "time": 1,
            "pressure": 2,
            "temperature": 3,
            "displacement 1": 4,
            "displacement 2": 5,
        },
        {
            "time": 3,
            "pressure": 0,
            "temperature": 0,
            "displacement 1": 0,
            "displacement 2": 0,
        },
    ]
    resolution = 0.5
    result = split_setpoints(setpoints, resolution)
    assert result == [
        {
            "duration": 0.0,
            "pressure": 0.0,
            "temperature": 0.0,
            "displacement 1": 0.0,
            "displacement 2": 0.0,
        },
        {
            "duration": 0.5,
            "pressure": 1.0,
            "temperature": 1.5,
            "displacement 1": 2.0,
            "displacement 2": 2.5,
        },
        {
            "duration": 0.5,
            "pressure": 2.0,
            "temperature": 3.0,
            "displacement 1": 4.0,
            "displacement 2": 5.0,
        },
        {
            "duration": 0.5,
            "pressure": 1.5,
            "temperature": 2.25,
            "displacement 1": 3.0,
            "displacement 2": 3.75,
        },
        {
            "duration": 0.5,
            "pressure": 1.0,
            "temperature": 1.5,
            "displacement 1": 2.0,
            "displacement 2": 2.5,
        },
        {
            "duration": 0.5,
            "pressure": 0.5,
            "temperature": 0.75,
            "displacement 1": 1.0,
            "displacement 2": 1.25,
        },
        {
            "duration": 0.5,
            "pressure": 0.0,
            "temperature": 0.0,
            "displacement 1": 0.0,
            "displacement 2": 0.0,
        },
    ]
