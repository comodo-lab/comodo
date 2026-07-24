import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_timer_message import on_wd_timer_message


class TestOnWatchdogTimerMessage:

    @pytest.fixture
    def wd_state(self):
        return {
            "interval": 0.2,
            "timeout": 1,
            "timer": 1,
            "healthy": True,
        }

    @pytest.fixture
    def wd_timer_client(self, mqtt_mocks):
        mqtt_mocks["client_class"](
            id="wd_timer",
            topics="watchdog/timer/command/start",
            callback=on_wd_timer_message,
        )
        return mqtt_mocks["client_instance"]

    # ========================================

    def test_incompatible_topic(self, message_bus, wd_timer_client, wd_state):
        msg = MockMessage(
            topic="watchdog/timer/command/run", payload=json.dumps({"not": "important"})
        )
        on_wd_timer_message(wd_timer_client, msg, wd_state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/watchdog_timer"
        assert (
            "The watchdog timer cannot act on watchdog/timer/command/run"
            in messages[0].payload
        )

    def test_wrong_json(self, message_bus, wd_timer_client, wd_state, capsys):
        msg = MockMessage(topic="watchdog/timer/command/start", payload="not json")
        on_wd_timer_message(wd_timer_client, msg, wd_state)

        # Printed error
        captured = capsys.readouterr()
        assert "ERROR: Watchdog timer failed to start." in captured.out
        assert "Wrong json:" in captured.out

        # MQTT error
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = "Cannot decode watchdog/timer/command/start message, wrong JSON:"
        assert exp_err in messages[0].payload
        assert wd_state["healthy"] == False
        assert f"ERROR: {exp_err}" in captured.out

    def test_missing_keys(self, message_bus, wd_timer_client, wd_state, capsys):
        msg = MockMessage(
            topic="watchdog/timer/command/start", payload=json.dumps({"timeout": 1})
        )
        on_wd_timer_message(wd_timer_client, msg, wd_state)

        # Printed error
        captured = capsys.readouterr()
        assert "ERROR: Watchdog timer failed to start." in captured.out
        assert "Missing keys: 'interval'" in captured.out

        # MQTT error
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = "Cannot decode watchdog/timer/command/start message, missing:"
        assert exp_err in messages[0].payload
        assert "interval" in messages[0].payload
        assert wd_state["healthy"] == False
        assert f"ERROR: {exp_err}" in captured.out

    def test_incompatible_values(self, message_bus, wd_timer_client, wd_state, capsys):
        assert wd_state["timeout"] == 1
        assert wd_state["interval"] == 0.2
        msg = MockMessage(
            topic="watchdog/timer/command/start",
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
        assert messages[0].topic == "error/watchdog_timer"
        assert "WATCHDOG_TIMER incompatible values:" in messages[0].payload
        assert "Expected interval 0.2, but got 1" in messages[0].payload
        assert wd_state["healthy"] == False

    def test_correct_start_and_timeout(
        self, message_bus, wd_timer_client, wd_state, capsys
    ):
        assert wd_state["timeout"] == 1
        assert wd_state["interval"] == 0.2
        msg = MockMessage(
            topic="watchdog/timer/command/start",
            payload=json.dumps({"timeout": 1, "interval": 0.2}),
        )
        on_wd_timer_message(wd_timer_client, msg, wd_state)

        assert "Watchdog running." in capsys.readouterr().out
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/timeout"
        assert wd_state["timer"] <= 0
        assert wd_state["interval"] == 0.2
        assert wd_state["timeout"] == 1
        assert wd_state["healthy"] == True
