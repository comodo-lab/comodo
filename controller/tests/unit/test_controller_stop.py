import json
import pytest
import os
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from tests.tests_helper import *

from controller_state import *
from mqtt_clients import *
from on_controller_message import *


state = make_state_fixture("end")

controller_client = make_client_fixture(
    client_id="controller",
    callback=c_stopping,
    topics="controller/#",
    autouse=False,
)


def test_incompatible_request(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    capmqtt.publish(
        topic="controller/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    wait_for_message(capmqtt)

    assert state.status == "running"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Controller is running. Cannot act on controller/something_else"
        in capmqtt.messages[-1].payload
    )


def test_checks_uid(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    capmqtt.publish(
        topic="controller/stop",
        payload=json.dumps({"uid": "456"}),
    )
    wait_for_message(capmqtt)

    assert state.status == "running"
    assert capmqtt.messages[-1].topic == "error/controller"
    assert (
        "Current experiment is 123. Cannot act on controller/stop for experiment 456."
        in capmqtt.messages[-1].payload
    )


def test_valid_stop(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping

    with patch("on_controller_message.dump_database_for_experiment") as mock_dump:
        mock_dump.side_effect = lambda x: (t.sleep(0.3), None)[1]
        capmqtt.publish(
            topic="controller/stop",
            payload=json.dumps({"uid": "123"}),
        )
        assert state.status == "stopping"
        wait_for_message(capmqtt)
        mock_dump.assert_called_once()

    assert capmqtt.messages[-1].topic == "controller/stopped"
    assert capmqtt.messages[-1].payload == json.dumps({"uid": "123"})
    assert state.status == "idle"
    assert state.experiment_uid is None
    assert controller_client.callback == c_idle


def test_stop_from_other_callback(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    controller_client.callback = c_running

    with patch("on_controller_message.dump_database_for_experiment") as mock_dump:
        mock_dump.side_effect = lambda x: (t.sleep(0.3), None)[1]
        capmqtt.publish(
            topic="controller/stop",
            payload=json.dumps({"uid": "123"}),
        )
        assert state.status == "stopping"
        wait_for_message(capmqtt)
        mock_dump.assert_called_once()

    assert capmqtt.messages[-1].topic == "controller/stopped"
    assert capmqtt.messages[-1].payload == json.dumps({"uid": "123"})
    assert state.status == "idle"
    assert state.experiment_uid is None
    assert controller_client.callback == c_idle


def test_database_dump(capmqtt, state, controller_client):
    assert state.experiment_uid == "123"
    assert state.status == "running"
    assert controller_client.callback == c_stopping
    org = config["influxdb"]["org"]
    buckets = config["influxdb"]["buckets"]

    t0 = datetime.now() - timedelta(minutes=5)
    state.experiment_start_time = t0
    tmp_path = f"{data_path}/tmp/123.test_temp_exp.json"
    state.exp_file = tmp_path
    assert not os.path.exists(tmp_path)
    expected_dir = f"{data_path}/tmp/123.test_temp_exp"
    try:
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "w") as f:
            f.write("this is an experiment")
        assert os.path.exists(tmp_path)

        with patch(
            "influxdb_client.client.query_api.QueryApi.query_csv"
        ) as mock_query_csv:
            mock_query_csv.return_value = Mock()
            mock_query_csv.return_value.to_values.return_value = [
                ["#some", "data", "here"],
                ["maybe", "some", "info"],
                ["and", "finally", "values"],
                ["0.123", "2024-03-05T14:26:43.715914833Z", "measurement"],
            ]
            capmqtt.publish(
                topic="controller/end",
                payload=json.dumps({"uid": "123"}),
            )
            wait_for_message(capmqtt)

        assert mock_query_csv.call_count == len(buckets)

        for i, call in enumerate(mock_query_csv.call_args_list):
            args, kwargs = call
            assert kwargs["org"] == org
            assert kwargs["query"].startswith(f'from(bucket: "{buckets[i]}")')
            assert f"range(start: {t0.isoformat()}Z" in kwargs["query"]

        assert os.path.exists(expected_dir)
        for bucket in buckets:
            assert os.path.exists(f"{expected_dir}/{bucket}.csv")

    except AssertionError as e:
        raise e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        for bucket in buckets:
            if os.path.exists(f"{expected_dir}/{bucket}.csv"):
                os.remove(f"{expected_dir}/{bucket}.csv")
        if os.path.exists(expected_dir):
            os.rmdir(expected_dir)
