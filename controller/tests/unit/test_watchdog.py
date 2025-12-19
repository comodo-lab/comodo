import json
import pytest

from tests.tests_helper import *

from utils.mqtt_clients import *

from src.on_watchdog_message import *


@pytest.fixture
def state():
    wdog = {
        "interval": 0.2,
        "timeout": 1,
        "timer": 1,
        "healthy": True,
    }
    return wdog


watchdog_client = make_client_fixture(
    client_id="watchdog",
    callback=on_watchdog_message,
    topics=["watchdog/#", "heartbeat/controller", "ERROR/exception"],
    autouse=True,
)


def test_wrong_json(capmqtt):
    capmqtt.publish(
        topic="heartbeat/controller",
        payload="not json",
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/watchdog"
    assert (
        "Error decoding heartbeat/controller message, wrong JSON:"
        in capmqtt.messages[-1].payload
    )


def test_incompatible_request(capmqtt):
    capmqtt.publish(
        topic="watchdog/run",
        payload=json.dumps({"not": "important"}),
    )
    wait_for_message(capmqtt)

    assert capmqtt.messages[-1].topic == "error/watchdog"
    assert (
        "WATCHDOG: Unexpected message received: watchdog/run"
        in capmqtt.messages[-1].payload
    )


def test_updates_timer_on_heartbeat(capmqtt, watchdog_client):
    assert watchdog_client.obj["timeout"] == 1
    watchdog_client.obj["timer"] = 0.3

    watchdog_client.callback = flagged(
        on_watchdog_message,
        flag_topic="flagged_watchdog",
        flag_message="silent watchdog call",
    )

    capmqtt.publish(topic="heartbeat/controller", payload=f"{cstate()}")

    assert capmqtt.messages[-1].topic == "flagged_watchdog"
    assert capmqtt.messages[-1].payload == "silent watchdog call"
    assert watchdog_client.obj["timer"] == 1


def test_handles_error_exception(capmqtt, capsys):
    capmqtt.publish(
        topic="ERROR/exception",
        payload=json.dumps({"error": "test error"}),
    )

    # Printed error
    captured = capsys.readouterr()
    assert "WATCHDOG: Received ERROR: test error" in captured.out

    # MQTT message
    assert capmqtt.messages[-1].topic == "watchdog/restart"
    assert capmqtt.messages[-1].payload == json.dumps(
        {"message": "Restarting controller..."}
    )


def test_responds_to_timeout(capmqtt, capsys):
    capmqtt.publish(
        topic="watchdog/timeout",
        payload=json.dumps({"error": "test error"}),
    )

    # Printed error
    captured = capsys.readouterr()
    assert "WATCHDOG: Timed out waiting for controller heartbeat." in captured.out
    assert "test error" in captured.out

    # MQTT message
    assert capmqtt.messages[-1].topic == "watchdog/restart"
    assert capmqtt.messages[-1].payload == json.dumps(
        {"message": "Restarting controller..."}
    )


def test_restart(capmqtt, capsys, watchdog_client):
    assert watchdog_client.obj["healthy"] == True

    capmqtt.publish(
        topic="watchdog/restart",
        payload=json.dumps({"not": "important"}),
    )

    captured = capsys.readouterr()
    assert "Restarting controller..." in captured.out
    assert watchdog_client.obj["healthy"] == False
