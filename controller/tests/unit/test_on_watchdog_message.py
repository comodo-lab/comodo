import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_message import on_watchdog_message

# =============== Fixtures ===============


@pytest.fixture
def wd_state():
    return {
        "interval": 0.2,
        "timeout": 1,
        "timer": 1,
        "healthy": True,
    }


@pytest.fixture
def watchdog_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="watchdog",
        topics=["watchdog/#", "heartbeat/controller", "ERROR/exception"],
        callback=on_watchdog_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_wrong_json(message_bus, watchdog_client, wd_state):
    msg = MockMessage(topic="heartbeat/controller", payload="not json")
    on_watchdog_message(watchdog_client, msg, wd_state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/watchdog"
    assert (
        "Error decoding heartbeat/controller message, wrong JSON:"
        in messages[0].payload
    )


def test_incompatible_request(message_bus, watchdog_client, wd_state):
    msg = MockMessage(topic="watchdog/run", payload=json.dumps({"not": "important"}))
    on_watchdog_message(watchdog_client, msg, wd_state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/watchdog"
    assert "WATCHDOG: Unexpected message received: watchdog/run" in messages[0].payload


def test_updates_timer_on_heartbeat(message_bus, watchdog_client, wd_state):
    assert wd_state["timeout"] == 1
    wd_state["timer"] = 0.3
    msg = MockMessage(topic="heartbeat/controller", payload='{"some": "data"}')
    on_watchdog_message(watchdog_client, msg, wd_state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Call should be mqtt silent"
    assert wd_state["timer"] == 1


def test_handles_error_exception(message_bus, watchdog_client, wd_state, capsys):
    msg = MockMessage(topic="ERROR/exception", payload=json.dumps({"error": "Test"}))
    on_watchdog_message(watchdog_client, msg, wd_state)

    # Printed error
    captured = capsys.readouterr()
    assert "WATCHDOG: Received ERROR: Test" in captured.out

    # MQTT message
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "watchdog/restart"
    assert messages[0].payload == json.dumps({"message": "Restarting controller..."})


def test_responds_to_timeout(message_bus, watchdog_client, wd_state, capsys):
    msg = MockMessage(topic="watchdog/timeout", payload=json.dumps({"error": "Test"}))
    on_watchdog_message(watchdog_client, msg, wd_state)

    # Printed error
    captured = capsys.readouterr()
    assert "WATCHDOG: Timed out waiting for controller heartbeat." in captured.out
    assert "Test" in captured.out

    # MQTT message
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "watchdog/restart"
    assert messages[0].payload == json.dumps({"message": "Restarting controller..."})


def test_restart(message_bus, watchdog_client, wd_state, capsys):
    assert wd_state["healthy"] == True

    msg = MockMessage(topic="watchdog/restart", payload='{"not": "important"}')
    on_watchdog_message(watchdog_client, msg, wd_state)

    captured = capsys.readouterr()
    assert "Restarting controller..." in captured.out
    assert wd_state["healthy"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Call should be mqtt silent"
