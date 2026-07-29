import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_message import on_watchdog_message


class TestOnWatchdogMessage:

    @pytest.fixture
    def owdm_mocks(self, mqtt_mocks):
        wd_state = {
            "interval": 0.2,
            "timeout": 1,
            "timer": 1,
            "healthy": True,
        }
        mqtt_mocks["client_class"](
            id="watchdog",
            topics=[
                "watchdog/timer/event/+",
                "watchdog/timer/command/+",
                "controller/heartbeat",
                "error/exception",
            ],
            callback=on_watchdog_message,
        )
        yield {
            "wd_state": wd_state,
            "watchdog_client": mqtt_mocks["client_instance"],
        }

    # ========================================

    def test_incompatible_topic(self, message_bus, owdm_mocks):
        msg = MockMessage(
            topic="something/else",
            payload=json.dumps({"experiment_id": "123"}),
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/watchdog"
        assert "The watchdog cannot act on something/else." in messages[0].payload

    def test_wrong_json(self, message_bus, owdm_mocks, capsys):
        msg = MockMessage(topic="controller/heartbeat", payload="not json")
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = "Cannot decode controller/heartbeat message, wrong JSON:"
        assert exp_err in messages[0].payload
        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_ignores_watchdog_command(self, message_bus, owdm_mocks):
        msg = MockMessage(
            topic="watchdog/timer/command/run", payload=json.dumps({"not": "important"})
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        messages = message_bus.get_messages(decoded=True)
        assert (
            len(messages) == 0
        ), "watchdog/timer/command/* topics should be silently ignored"

    def test_updates_timer_on_heartbeat(self, message_bus, owdm_mocks):
        wd_state = owdm_mocks["wd_state"]
        assert wd_state["timeout"] == 1
        wd_state["timer"] = 0.3
        msg = MockMessage(topic="controller/heartbeat", payload='{"some": "data"}')
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, wd_state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0, "Call should be mqtt silent"
        assert wd_state["timer"] == 1

    def test_handles_error_exception(self, message_bus, owdm_mocks, capsys):
        msg = MockMessage(
            topic="error/exception", payload=json.dumps({"error": "Test"})
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        # Printed error
        captured = capsys.readouterr()
        assert "WATCHDOG: Received error: Test" in captured.out

        # MQTT message
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/restart_triggered"
        assert messages[0].payload == json.dumps(
            {"message": "Restarting controller..."}
        )

    def test_responds_to_timeout(self, message_bus, owdm_mocks, capsys):
        msg = MockMessage(
            topic="watchdog/timer/event/timeout",
            payload=json.dumps({"message": "Test"}),
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        # Printed error
        captured = capsys.readouterr()
        assert "WATCHDOG: Timed out waiting for controller heartbeat." in captured.out
        assert "Test" in captured.out

        # MQTT message
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/restart_triggered"
        assert messages[0].payload == json.dumps(
            {"message": "Restarting controller..."}
        )

    def test_ignores_watchdog_command_restart(self, message_bus, owdm_mocks, capsys):
        wd_state = owdm_mocks["wd_state"]
        assert wd_state["healthy"] == True

        msg = MockMessage(
            topic="watchdog/timer/command/restart", payload='{"not": "important"}'
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, wd_state)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert wd_state["healthy"] == True

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0, "watchdog/timer/command/* should be silently ignored"
