import json
import pytest
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
)

from src.on_watchdog_timer_message import on_wd_timer_message


class TestOnWatchdogTimerMessage:

    @pytest.fixture
    def owdtm_mocks(self, message_bus, mqtt_mocks):
        with patch("src.on_watchdog_timer_message.pub_err") as mock_publish_error:
            wd_state = {
                "interval": 0.02,
                "timeout": 0.1,
                "time_remaining": None,
                "healthy": True,
            }
            mqtt_mocks["client_class"](
                id="wd_timer",
                topics="watchdog/timer/command/start",
                callback=on_wd_timer_message,
            )

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "wd_state": wd_state,
                "wdt_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_topic(self, owdtm_mocks):
        msg = MockMessage(topic="watchdog/timer/command/run", payload=json.dumps({}))

        on_wd_timer_message(owdtm_mocks["wdt_client"], msg, owdtm_mocks["wd_state"])

        owdtm_mocks["pub_err"].incompatible_topic.assert_called_once_with(
            owdtm_mocks["wd_state"], msg, "watchdog_timer"
        )

    def test_missing_keys(self, owdtm_mocks, capsys):
        owdtm_mocks["wd_state"].pop("timeout", None)
        msg = MockMessage(
            topic="watchdog/timer/command/start",
            payload=json.dumps({"source": "controller"}),
        )

        on_wd_timer_message(owdtm_mocks["wdt_client"], msg, owdtm_mocks["wd_state"])

        owdtm_mocks["pub_err"].missing_keys.assert_called_once()
        messages = owdtm_mocks["messages"]()
        assert len(messages) == 0

    def test_correct_start_and_timeout(self, owdtm_mocks, capsys):
        wd_state = owdtm_mocks["wd_state"]
        assert wd_state["timeout"] == 0.1
        assert wd_state["interval"] == 0.02
        msg = MockMessage(
            topic="watchdog/timer/command/start",
            payload=json.dumps({"source": "controller"}),
        )

        on_wd_timer_message(owdtm_mocks["wdt_client"], msg, wd_state)

        assert "Watchdog running." in capsys.readouterr().out
        messages = owdtm_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "watchdog/timer/event/timeout"
        assert wd_state["time_remaining"] <= 0
        assert wd_state["interval"] == 0.02
        assert wd_state["timeout"] == 0.1
        assert wd_state["healthy"] == True
