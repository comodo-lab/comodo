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
def state(mock_state, mock_experiment_dict, mock_setpoints):
    return mock_state("awaiting_instruments", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def timer_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="timer",
        topics="controller/timer/#",
        callback=on_timer_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_wrong_json(message_bus, state, capsys):
    msg = MockMessage(
        topic="controller/timer/command/start",
        payload="not a json",
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    exp_err = "Cannot decode controller/timer/command/start message, wrong JSON:"
    assert exp_err in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_missing_experiment_id(timer_client, message_bus, state, capsys):
    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps({"source": "instrument_setup"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    exp_err = "Cannot decode controller/timer/command/start message, missing:"
    assert exp_err in messages[0].payload
    assert "experiment_id" in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_incorrect_experiment_id(timer_client, message_bus, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps({"source": "instrument_setup", "experiment_id": "999"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller_timer"
    assert (
        "Current experiment is 123. Controller timer cannot act on controller/timer/command/start for experiment 999."
        in messages[0].payload
    )


def test_incompatible_topic(timer_client, message_bus, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="controller/timer/something_else",
        payload=json.dumps({"experiment_id": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller_timer"
    assert (
        "The controller timer cannot act on controller/timer/something_else."
        in messages[0].payload
    )


def test_timeout(timer_client, message_bus, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments_ready == False
    state.instrument_setup_wait = 0.1

    with patch("src.on_timer_message.timer_check_frequency", 0.01):
        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
        )
        on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 2
    assert messages[0].topic == "error/controller"
    assert "Timed out waiting for instruments. Stopping..." in messages[0].payload
    assert messages[1].topic == "controller/command/stop"
    assert '{"id": "123"' in messages[1].payload


def test_stops_when_configured(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    state.instruments_ready = True

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/timer/event/done"
    assert json.loads(messages[0].payload) == {
        "source": "instrument_setup",
        "experiment_id": "123",
        "instruments_configured": True,
        "controller_status": "awaiting_instruments",
    }


def test_stops_when_not_awaiting_instruments(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.instruments_ready == False
    state.status = "ready"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/timer/event/done"
    assert json.loads(messages[0].payload) == {
        "source": "instrument_setup",
        "experiment_id": "123",
        "instruments_configured": False,
        "controller_status": "ready",
    }


def test_done_instrument_setup_uses_obj_uid(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    assert state.instruments_ready == False
    state.status = "ready"

    with patch("src.on_timer_message.t.time") as mock_time:
        # Simulate experiment uid change when instruments get configured
        def change_uid(*args, **kwargs):
            state.experiment_uid = "D25-123"
            return 12345  # arbitrary time

        mock_time.side_effect = change_uid

        msg = MockMessage(
            topic="controller/timer/command/start",
            payload=json.dumps({"source": "instrument_setup", "experiment_id": "123"}),
        )
        on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/timer/event/done"
    assert json.loads(messages[0].payload) == {
        "source": "instrument_setup",
        "experiment_id": "D25-123",
        "instruments_configured": False,
        "controller_status": "ready",
    }


def test_timer_setpoint(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "running"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps(
            {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
        ),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/command/run"
    assert messages[0].payload == '{"experiment_id": "123"}'


def test_timer_setpoint_missing_duration(timer_client, message_bus, state, capsys):
    assert state.experiment_uid == "123"
    state.status = "running"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps({"source": "setpoint", "experiment_id": "123"}),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    exp_err = "Cannot decode controller/timer/command/start message, missing:"
    assert exp_err in messages[0].payload
    assert "duration" in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_timer_setpoint_incompatible_controller_state(timer_client, message_bus, state):
    assert state.experiment_uid == "123"
    state.status = "ready"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps(
            {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
        ),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    m = json.loads(messages[0].payload)
    assert m["code"] == "timer_error"
    assert "Timer for setpoint exited unexpectedly." in m["message"]
    assert "ready instead of running" in m["message"]


def test_timer_setpoint_stopping(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "stopping"

    msg = MockMessage(
        topic="controller/timer/command/start",
        payload=json.dumps(
            {"source": "setpoint", "experiment_id": "123", "duration": 0.1}
        ),
    )
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/timer/event/done"
    assert json.loads(messages[0].payload) == {
        "source": "setpoint",
        "experiment_id": "123",
        "controller_status": "stopping",
    }


def test_timer_done_topic(message_bus, state, timer_client):
    assert state.experiment_uid == "123"
    state.status = "running"

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
    on_timer_message(timer_client, msg, state)
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
    on_timer_message(timer_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert (
        len(messages) == 0
    ), "No messages should be published for timer/event/done topics"
