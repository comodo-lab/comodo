import json
import pytest
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.on_timer_message import on_timer_message


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("awaiting_instruments", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def timer_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="timer",
        topics="timer/#",
        callback=on_timer_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_wrong_json(message_bus, state, capsys):
    msg = MockMessage(
        topic="timer/start/instrument_setup",
        payload="not a json",
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    exp_err = "Cannot decode timer/start/instrument_setup message, wrong JSON:"
    assert exp_err in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_missing_uid(timer_client, message_bus, state, capsys):
    msg = MockMessage(
        topic="timer/start/instrument_setup",
        payload=json.dumps({"some": "json"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/timer"
    exp_err = "Cannot decode timer/start/instrument_setup message, missing:"
    assert exp_err in messages[0].payload
    assert "uid" in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_incorrect_uid(timer_client, message_bus, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="timer/start/instrument_setup",
        payload=json.dumps({"uid": "999"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/timer"
    assert (
        "Current experiment is 123. Cannot act on timer/start/instrument_setup for experiment 999."
        in messages[0].payload
    )


def test_incompatible_request(timer_client, message_bus, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="timer/something_else",
        payload=json.dumps({"uid": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/timer"
    assert "Timer cannot act on timer/something_else" in messages[0].payload


def test_timeout(timer_client, message_bus, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments["configured"] == False

    with patch("os.getenv", return_value="0.1") as mock_getenv, patch(
        "src.on_timer_message.timer_check_frequency", 0.01
    ):
        msg = MockMessage(
            topic="timer/start/instrument_setup",
            payload=json.dumps({"uid": "123"}),
        )
        on_timer_message(timer_client, msg, state)

    mock_getenv.assert_called_once_with("INSTRUMENT_SETUP_WAIT", 10)
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 2
    assert messages[0].topic == "error/controller/timeout"
    assert "Timed out waiting for instruments. Stopping..." in messages[0].payload
    assert messages[1].topic == "controller/stop"
    assert '{"uid": "123"' in messages[1].payload


def test_stops_when_configured(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    state.instruments["configured"] = True

    msg = MockMessage(
        topic="timer/start/instrument_setup",
        payload=json.dumps({"uid": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "timer/done/instrument_setup"
    assert json.loads(messages[0].payload) == {
        "uid": "123",
        "instruments_configured": True,
        "controller_status": "awaiting_instruments",
    }


def test_stops_when_not_awaiting_instruments(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.instruments["configured"] == False
    state.status = "ready"

    msg = MockMessage(
        topic="timer/start/instrument_setup",
        payload=json.dumps({"uid": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "timer/done/instrument_setup"
    assert json.loads(messages[0].payload) == {
        "uid": "123",
        "instruments_configured": False,
        "controller_status": "ready",
    }


def test_done_instrument_setup_uses_obj_uid(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.instruments["configured"] == False
    state.status = "ready"

    with patch("src.on_timer_message.t.time") as mock_time:
        # Simulate experiment uid change when instruments get configured
        def change_uid(*args, **kwargs):
            state.experiment_uid = "D25-123"
            return 12345  # arbitrary time

        mock_time.side_effect = change_uid

        msg = MockMessage(
            topic="timer/start/instrument_setup",
            payload=json.dumps({"uid": "123"}),
        )
        on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "timer/done/instrument_setup"
    assert json.loads(messages[0].payload) == {
        "uid": "D25-123",
        "instruments_configured": False,
        "controller_status": "ready",
    }


def test_timer_setpoint(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "running"

    msg = MockMessage(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123", "duration": 0.1}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/run"
    assert messages[0].payload == '{"uid": "123"}'


def test_timer_setpoint_missing_duration(timer_client, message_bus, state, capsys):
    assert state.experiment_uid == "123"
    state.status = "running"

    msg = MockMessage(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/timer"
    exp_err = "Cannot decode timer/start/setpoint message, missing:"
    assert exp_err in messages[0].payload
    assert "duration" in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_timer_setpoint_incompatible_controller_state(timer_client, message_bus, state):
    assert state.experiment_uid == "123"
    state.status = "ready"

    msg = MockMessage(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123", "duration": 0.1}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller/timer/setpoint"
    m = json.loads(messages[0].payload)
    assert m["uid"] == "123"
    assert "Timer for setpoint exited unexpectedly."
    assert "ready instead of running" in m["error"]


def test_timer_setpoint_stopping(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "stopping"

    msg = MockMessage(
        topic="timer/start/setpoint",
        payload=json.dumps({"uid": "123", "duration": 0.1}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "timer/done/setpoint"
    assert json.loads(messages[0].payload) == {
        "uid": "123",
        "controller_status": "stopping",
    }


def test_timer_done_topic(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "running"

    msg = MockMessage(
        topic="timer/done/setpoint",
        payload=json.dumps({"uid": "123", "controller_status": "stopping"}),
    )
    on_timer_message(timer_client, msg, state)
    msg = MockMessage(
        topic="timer/done/setpoint",
        payload=json.dumps(
            {
                "uid": "123",
                "instruments_configured": False,
                "controller_status": "ready",
            }
        ),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "No messages should be published for timer/done topics"
