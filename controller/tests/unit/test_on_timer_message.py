import json
import pytest
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
)

from src.on_timer_message import on_timer_message
from utils.mqtt_validator import MQTTValidationException


class TestOnTimerMessage:

    @pytest.fixture
    def ouim_mocks(self, message_bus, mqtt_mocks, mqtt_validator_mocks, mock_state):
        with (
            patch("src.on_ui_message.data_path", new="test_data"),
            patch("src.on_timer_message.pub_err") as mock_publish_error,
        ):
            state = mock_state("awaiting_instruments")

            mqtt_mocks["client_class"](
                id="timer",
                topics="controller/timer/#",
                callback=on_timer_message,
            )

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "validate_message": mqtt_validator_mocks["validate_message"],
                "state": state,
                "timer_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_invalid_message(self, ouim_mocks, capsys):
        err = MQTTValidationException("Invalid JSON")
        ouim_mocks["validate_message"].side_effect = err

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload="not a json",
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["validate_message"].assert_called_once_with(msg.topic, msg.payload)
        ouim_mocks["pub_err"].message_validation.assert_called_once_with(err)
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_missing_experiment_id(self, ouim_mocks):
        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["pub_err"].missing_keys.assert_called_once()
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_incorrect_experiment_id(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "999"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["pub_err"].incompatible_uid.assert_called_once_with(
            ouim_mocks["state"], msg, "999", "controller_timer"
        )
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_incompatible_topic(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"

        msg = MockMessage(
            topic="controller/timer/something_else",
            payload=json.dumps({"experiment_id": "123"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["pub_err"].incompatible_topic.assert_called_once_with(
            ouim_mocks["state"], msg, "controller_timer"
        )
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_missing_inst_setup_wait(self, ouim_mocks, capsys):
        assert ouim_mocks["state"].experiment_id == "123"
        assert ouim_mocks["state"].status == "awaiting_instruments"
        assert ouim_mocks["state"].instruments_ready == False
        ouim_mocks["state"].config.globals["instrument_setup_wait"] = None

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["pub_err"].missing_keys.assert_called_once()
        assert "Stopping experiment..." in capsys.readouterr().out
        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert '{"experiment_id": "123"' in messages[0].payload

    def test_timeout(self, ouim_mocks, capsys):
        assert ouim_mocks["state"].experiment_id == "123"
        assert ouim_mocks["state"].status == "awaiting_instruments"
        assert ouim_mocks["state"].instruments_ready == False
        ouim_mocks["state"].config.globals["instrument_setup_wait"] = 0.1

        with patch("src.on_timer_message.timer_check_frequency", 0.01):
            msg = MockMessage(
                topic="controller/timer/command/start",
                payload=json.dumps(
                    {"source": "instrument_setup", "experiment_id": "123"}
                ),
            )
            on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        ouim_mocks["pub_err"].controller_timeout.assert_called_once_with(
            "123", "instruments"
        )
        assert "Stopping experiment..." in capsys.readouterr().out
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert '{"experiment_id": "123"' in messages[0].payload

    def test_stops_when_configured(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        assert ouim_mocks["state"].status == "awaiting_instruments"
        ouim_mocks["state"].instruments_ready = True

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/event/done"
        assert json.loads(messages[0].payload) == {
            "source": "instrument_setup",
            "experiment_id": "123",
            "instruments_configured": True,
            "controller_status": "awaiting_instruments",
        }

    def test_stops_when_not_awaiting_instruments(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        assert ouim_mocks["state"].instruments_ready == False
        ouim_mocks["state"].status = "ready"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/event/done"
        assert json.loads(messages[0].payload) == {
            "source": "instrument_setup",
            "experiment_id": "123",
            "instruments_configured": False,
            "controller_status": "ready",
        }

    def test_timer_setpoint(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        ouim_mocks["state"].status = "running"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps(
                {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
            ),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/run"
        assert messages[0].payload == '{"experiment_id": "123"}'

    def test_timer_setpoint_missing_duration(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        ouim_mocks["state"].status = "running"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "setpoint", "experiment_id": "123"}),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks["pub_err"].missing_keys.assert_called_once()
        messages = ouim_mocks["messages"]()
        assert len(messages) == 0

    def test_timer_setpoint_incompatible_controller_state(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        ouim_mocks["state"].status = "ready"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps(
                {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
            ),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        ouim_mocks[
            "pub_err"
        ].controller_state_incompatible_with_timer.assert_called_once_with(
            "123", "setpoint", "running", "ready"
        )

    def test_timer_setpoint_stopping(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        ouim_mocks["state"].status = "stopping"

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps(
                {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
            ),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/event/done"
        assert json.loads(messages[0].payload) == {
            "source": "setpoint",
            "experiment_id": "123",
            "controller_status": "stopping",
        }

    def test_timer_done_topic(self, ouim_mocks):
        assert ouim_mocks["state"].experiment_id == "123"
        ouim_mocks["state"].status = "running"

        msg = MockMessage(
            topic="controller/timer/event/done",
            payload=json.dumps(
                {
                    "source": "setpoint",
                    "experiment_id": "123",
                    "controller_status": "stopping",
                }
            ),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])
        msg = MockMessage(
            topic="controller/timer/event/done",
            payload=json.dumps(
                {
                    "source": "instrument_setup",
                    "experiment_id": "123",
                    "instruments_configured": False,
                    "controller_status": "ready",
                }
            ),
        )
        on_timer_message(ouim_mocks["timer_client"], msg, ouim_mocks["state"])

        messages = ouim_mocks["messages"]()
        assert (
            len(messages) == 0
        ), "No messages should be published for timer/event/done topics"
