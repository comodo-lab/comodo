import json
import pytest
import time as t
import os

from tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_controller_message import *
from unittest.mock import patch


state = make_state_fixture("ready")

controller_client = make_client_fixture(
    client_id="controller",
    callback=c_ready,
    topics="controller/#",
    autouse=False,
)


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


def test_updates_states_correctly(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    with patch("on_controller_message.c_running") as mock_c_running:
        mock_c_running.return_value = None
        mock_c_running.__name__ = "mock_c_running"
        with patch("on_controller_message.assign_serial_id") as mock_assign:
            mock_assign.return_value = None
            capmqtt.publish(
                topic="controller/ready",
                payload=json.dumps({"uid": "123"}),
            )
            wait_for_message(capmqtt)

    assert state.status == "ready"
    assert state.experiment_uid == "123"
    assert controller_client.callback == mock_c_running
    assert capmqtt.messages[-1].topic == "controller/run"
    assert capmqtt.messages[-1].payload == '{"uid": "123"}'


def test_updates_serial_id_correctly_empty_dir(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready
    assert state.exp_file == None
    current_year = str(datetime.now().year)[-2:]

    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = []
        with patch("os.rename") as mock_rename:
            with patch("on_controller_message.c_running") as mock_c_running:
                mock_c_running.return_value = None
                mock_c_running.__name__ = "mock_c_running"
                capmqtt.publish(
                    topic="controller/ready",
                    payload=json.dumps({"uid": "123"}),
                )
                assert mock_listdir.called
                assert mock_rename.called
                wait_for_message(capmqtt)

    expected_uid = f"D{current_year}-001"
    assert state.experiment_uid == expected_uid
    assert state.exp_file == f"{data_path}/{expected_uid}.json"
    assert capmqtt.messages[-1].topic == "controller/run"
    assert capmqtt.messages[-1].payload == json.dumps({"uid": expected_uid})


def test_updates_serial_id_correctly_non_empty_dir(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready
    assert state.exp_file == None
    current_year = str(datetime.now().year)[-2:]

    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = [
            f"D{current_year}-041.json",
            f"D{current_year}-005.json",
            f"D{current_year}-514.txt",
            "D21-365.json",
        ]
        with patch("os.rename") as mock_rename:
            with patch("on_controller_message.c_running") as mock_c_running:
                mock_c_running.return_value = None
                mock_c_running.__name__ = "mock_c_running"
                capmqtt.publish(
                    topic="controller/ready",
                    payload=json.dumps({"uid": "123"}),
                )
                assert mock_listdir.called
                assert mock_rename.called
                wait_for_message(capmqtt)

    expected_uid = f"D{current_year}-042"
    assert state.experiment_uid == expected_uid
    assert state.exp_file == f"{data_path}/{expected_uid}.json"
    assert capmqtt.messages[-1].topic == "controller/run"
    assert capmqtt.messages[-1].payload == json.dumps({"uid": expected_uid})


def test_moves_file_correctly(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert controller_client.callback == c_ready

    current_year = str(datetime.now().year)[-2:]
    d_path = f"{data_path}/D{current_year}-41.test_temp_exp.json"
    tmp_path = f"{data_path}/tmp/123.test_temp_exp.json"
    state.exp_file = tmp_path
    assert not os.path.exists(d_path)
    assert not os.path.exists(tmp_path)
    try:
        os.makedirs(os.path.dirname(d_path), exist_ok=True)
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(d_path, "w") as f:
            f.write("The answer is 42")
        with open(tmp_path, "w") as f:
            f.write("But what is the question?")
        assert os.path.exists(d_path)
        assert os.path.exists(tmp_path)

        with patch("on_controller_message.c_running") as mock_c_running:
            mock_c_running.return_value = None
            capmqtt.publish(
                topic="controller/ready",
                payload=json.dumps({"uid": "123"}),
            )
            wait_for_message(capmqtt)

        expected_file = f"{data_path}/D{current_year}-042.json"
        assert state.exp_file == expected_file
        assert os.path.exists(d_path)
        assert os.path.exists(expected_file)
        assert not os.path.exists(tmp_path)
    except AssertionError as e:
        raise e
    finally:
        if os.path.exists(d_path):
            os.remove(d_path)
        if os.path.exists(expected_file):
            os.remove(expected_file)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(state.exp_file):
            if t.time() - os.path.getctime(state.exp_file) < 15:
                os.remove(state.exp_file)
