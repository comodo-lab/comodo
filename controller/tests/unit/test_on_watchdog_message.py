import json
import pytest
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_message import on_watchdog_message


class TestOnWatchdogMessage:

    @pytest.fixture
    def owdm_mocks(self, message_bus, mqtt_mocks):
        with patch("src.on_watchdog_message.pe") as mock_publish_error:
            wd_state = {
                "interval": 0.2,
                "timeout": 1,
                "time_remaining": None,
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

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "wd_state": wd_state,
                "watchdog_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_topic(self, owdm_mocks):
        msg = MockMessage(
            topic="something/else",
            payload=json.dumps({"experiment_id": "123"}),
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        owdm_mocks["pe"].incompatible_topic.assert_called_once_with(
            owdm_mocks["wd_state"], msg, "watchdog"
        )

    def test_wrong_json(self, owdm_mocks, capsys):
        msg = MockMessage(topic="controller/heartbeat", payload="not json")
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        owdm_mocks["pe"].wrong_json.assert_called_once()
        messages = owdm_mocks["messages"]()
        assert len(messages) == 0

    def test_ignores_watchdog_command(self, owdm_mocks):
        msg = MockMessage(
            topic="watchdog/timer/command/run", payload=json.dumps({"not": "important"})
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        messages = owdm_mocks["messages"]()
        assert (
            len(messages) == 0
        ), "watchdog/timer/command/* topics should be silently ignored"

    def test_updates_timer_on_heartbeat(self, owdm_mocks):
        wd_state = owdm_mocks["wd_state"]
        assert wd_state["timeout"] == 1
        wd_state["time_remaining"] = 0.3
        msg = MockMessage(topic="controller/heartbeat", payload='{"some": "data"}')
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, wd_state)

        messages = owdm_mocks["messages"]()
        assert len(messages) == 0, "Call should be mqtt silent"
        assert wd_state["time_remaining"] == 1

    def test_handles_error_exception(self, owdm_mocks, capsys):
        msg = MockMessage(
            topic="error/exception", payload=json.dumps({"error": "Test"})
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, owdm_mocks["wd_state"])

        # Printed error
        captured = capsys.readouterr()
        assert "WATCHDOG: Received error: Test" in captured.out

        # MQTT message
        messages = owdm_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/restart_triggered"
        assert messages[0].payload == json.dumps(
            {"message": "Restarting controller..."}
        )

    def test_responds_to_timeout(self, owdm_mocks, capsys):
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
        messages = owdm_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/restart_triggered"
        assert messages[0].payload == json.dumps(
            {"message": "Restarting controller..."}
        )

    def test_ignores_watchdog_command_restart(self, owdm_mocks, capsys):
        wd_state = owdm_mocks["wd_state"]
        assert wd_state["healthy"] == True

        msg = MockMessage(
            topic="watchdog/timer/command/restart", payload='{"not": "important"}'
        )
        on_watchdog_message(owdm_mocks["watchdog_client"], msg, wd_state)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert wd_state["healthy"] == True

        messages = owdm_mocks["messages"]()
        assert len(messages) == 0, "watchdog/timer/command/* should be silently ignored"
