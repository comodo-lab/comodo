import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_timer_message import on_wd_timer_message

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
def wd_timer_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="wd_timer",
        topics=["wd_timer/#"],
        callback=on_wd_timer_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_incompatible_request(message_bus, wd_timer_client, wd_state):
    msg = MockMessage(topic="wd_timer/run", payload=json.dumps({"not": "important"}))
    on_wd_timer_message(wd_timer_client, msg, wd_state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/wd_timer"
    assert (
        "WATCHDOG_TIMER: Unexpected message received: wd_timer/run"
        in messages[0].payload
    )


def test_wrong_json(message_bus, wd_timer_client, wd_state, capsys):
    msg = MockMessage(topic="wd_timer/start", payload="not json")
    on_wd_timer_message(wd_timer_client, msg, wd_state)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Wrong json:" in captured.out

    # MQTT error
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/wd_timer"
    exp_err = "Cannot decode wd_timer/start message, wrong JSON:"
    assert exp_err in messages[0].payload
    assert wd_state["healthy"] == False
    assert f"ERROR: {exp_err}" in captured.out


def test_missing_keys(message_bus, wd_timer_client, wd_state, capsys):
    msg = MockMessage(topic="wd_timer/start", payload=json.dumps({"timeout": 1}))
    on_wd_timer_message(wd_timer_client, msg, wd_state)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Missing keys: 'interval'" in captured.out

    # MQTT error
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/wd_timer"
    exp_err = "Cannot decode wd_timer/start message, missing:"
    assert exp_err in messages[0].payload
    assert "interval" in messages[0].payload
    assert wd_state["healthy"] == False
    assert f"ERROR: {exp_err}" in captured.out


def test_incompatible_values(message_bus, wd_timer_client, wd_state, capsys):
    assert wd_state["timeout"] == 1
    assert wd_state["interval"] == 0.2
    msg = MockMessage(
        topic="wd_timer/start",
        payload=json.dumps({"timeout": 1, "interval": 1}),
    )
    on_wd_timer_message(wd_timer_client, msg, wd_state)

    # Printed error
    captured = capsys.readouterr()
    assert "ERROR: Watchdog timer failed to start." in captured.out
    assert "Values do not match:" in captured.out

    # MQTT error
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/wd_timer"
    assert "WATCHDOG_TIMER incompatible values:" in messages[0].payload
    assert "Expected interval 0.2, but got 1" in messages[0].payload
    assert wd_state["healthy"] == False


def test_correct_start_and_timeout(message_bus, wd_timer_client, wd_state, capsys):
    assert wd_state["timeout"] == 1
    assert wd_state["interval"] == 0.2
    msg = MockMessage(
        topic="wd_timer/start",
        payload=json.dumps({"timeout": 1, "interval": 0.2}),
    )
    on_wd_timer_message(wd_timer_client, msg, wd_state)

    assert "Watchdog running." in capsys.readouterr().out
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "watchdog/timeout"
    assert wd_state["timer"] <= 0
    assert wd_state["interval"] == 0.2
    assert wd_state["timeout"] == 1
    assert wd_state["healthy"] == True
