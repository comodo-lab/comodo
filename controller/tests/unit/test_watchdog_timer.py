import json
import pytest

from tests.tests_helper import *

from utils.mqtt_clients import *

from src.on_watchdog_timer_message import *


@pytest.fixture
def state():
    wdog = {
        "interval": 0.2,
        "timeout": 1,
        "timer": 1,
        "healthy": False,
    }
    return wdog


wd_timer_client = make_client_fixture(
    client_id="wd_timer",
    callback=on_wd_timer_message,
    topics="wd_timer/#",
    autouse=True,
)


def test_incompatible_request(capmqtt):
    capmqtt.publish(
        topic="wd_timer/run",
        payload=json.dumps({"not": "important"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/wd_timer"
    assert (
        "WATCHDOG_TIMER: Unexpected message received: wd_timer/run"
        in capmqtt.messages[-1].payload
    )


def test_wrong_json(capmqtt, capsys, wd_timer_client):
    capmqtt.publish(
        topic="wd_timer/start",
        payload="not json",
    )
    wait_for_message(capmqtt)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Wrong json:" in captured.out

    # MQTT error
    assert capmqtt.messages[-1].topic == "error/wd_timer"
    assert (
        "Error decoding wd_timer/start message, wrong JSON:"
        in capmqtt.messages[-1].payload
    )
    assert wd_timer_client.obj["healthy"] == False


def test_missing_keys(capmqtt, capsys, wd_timer_client):
    capmqtt.publish(
        topic="wd_timer/start",
        payload=json.dumps({"timeout": 1}),
    )
    wait_for_message(capmqtt)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Missing keys: 'interval'" in captured.out

    # MQTT error
    assert capmqtt.messages[-1].topic == "error/wd_timer"
    assert (
        "Error decoding wd_timer/start message, missing: \\n   'interval"
        in capmqtt.messages[-1].payload
    )
    assert wd_timer_client.obj["healthy"] == False


def test_incompatible_values(capmqtt, capsys, wd_timer_client):
    assert wd_timer_client.obj["timeout"] == 1
    assert wd_timer_client.obj["interval"] == 0.2
    capmqtt.publish(
        topic="wd_timer/start",
        payload=json.dumps({"timeout": 1, "interval": 1}),
    )
    wait_for_message(capmqtt)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Values do not match:" in captured.out

    # MQTT error
    assert capmqtt.messages[-1].topic == "error/wd_timer"
    assert "WATCHDOG_TIMER incompatible values:" in capmqtt.messages[-1].payload
    assert "Expected interval 0.2, but got 1" in capmqtt.messages[-1].payload
    assert wd_timer_client.obj["healthy"] == False


def test_correct_start_and_timeout(capmqtt, capsys, wd_timer_client):
    assert wd_timer_client.obj["timeout"] == 1
    assert wd_timer_client.obj["interval"] == 0.2
    capmqtt.publish(
        topic="wd_timer/start",
        payload=json.dumps({"timeout": 1, "interval": 0.2}),
    )
    wait_for_message(capmqtt)

    assert "Watchdog running." in capsys.readouterr().out
    assert capmqtt.messages[-1].topic == "watchdog/timeout"
    assert wd_timer_client.obj["timer"] <= 0
    assert wd_timer_client.obj["interval"] == 0.2
    assert wd_timer_client.obj["timeout"] == 1
    assert wd_timer_client.obj["healthy"] == True
