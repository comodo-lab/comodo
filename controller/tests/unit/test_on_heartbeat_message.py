import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.on_heartbeat_message import on_heartbeat_message

# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("awaiting_instruments", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def heartbeat_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="heartbeat",
        topics="instruments/+/heartbeat",
        callback=on_heartbeat_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_incompatible_request(message_bus, heartbeat_client, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="heartbeat/something_else", payload=json.dumps({"experiment_id": "123"})
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    assert "Heartbeat cannot act on heartbeat/something_else. Controller status is awaiting_instruments." in messages[0].payload


def test_wrong_json(message_bus, state, capsys):
    exp_err = "Cannot decode instruments/instrument_1/heartbeat message, wrong JSON:"
    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload="not a json",
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    
    message = messages[0]
    payload_obj = json.loads(message.payload)

    assert payload_obj["code"] == "malformed_json"
    assert exp_err in payload_obj["message"]
    assert f"ERROR: {exp_err}" in capsys.readouterr().out

def test_validation_exception(message_bus, state, capsys):
    exp_err = "Invalid heartbeat from instrument_1: {\"hello\": \"world\"}. Additional properties are not allowed ('hello' was unexpected)"
    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload=json.dumps({"hello": "world"}),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1

    message = messages[0]
    payload_obj = json.loads(message.payload)

    assert payload_obj["code"] == "heartbeat_validation"
    assert exp_err in payload_obj["message"]
    assert exp_err in capsys.readouterr().out

def test_unconfigured_instrument(message_bus, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert "instrument_1" not in state.instruments

    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload=json.dumps(
            {
                "state": "ready",
                "setpoints": {},
                "config": {"tolerance": 1, "experiment_id": None},
            }
        ),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    assert "Instrument instrument_1 is not configured" in messages[0].payload


def test_sensor_only_heartbeat_awaiting_instruments(message_bus, state):
    assert state.status == "awaiting_instruments"
    assert "furnace_left" not in state.instruments
    assert "furnace_left" in state.sensor_instruments

    msg = MockMessage(
        topic="instruments/furnace_left/heartbeat",
        payload=json.dumps({"state": "ready", "setpoints": {}, "config": {"experiment_id": None}}),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Sensor-only heartbeats should not publish errors"


def test_sensor_only_heartbeat_running(message_bus, state):
    state.status = "running"
    assert "furnace_left" in state.sensor_instruments

    msg = MockMessage(
        topic="instruments/furnace_left/heartbeat",
        payload=json.dumps({"state": "ready", "setpoints": {}, "config": {"experiment_id": None}}),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Sensor-only heartbeats should not publish errors"


def test_unconfigured_instrument_idle(message_bus, state, heartbeat_client):
    assert state.experiment_uid == "123"
    state.status = "idle"
    assert "instrument_1" not in state.instruments

    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload=json.dumps(
            {
                "state": "idle",
                "setpoints": {},
                    "config": {"tolerance": None, "experiment_id": None},
            }
        ),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "No messages should be published in idle state"



def test_awaiting_instruments_racing_heartbeat(
    message_bus,
    state,
    heartbeat_client,
):
    assert state.instruments_ready == False

    first_instrument_name = "furnace_centre"
    first_instrument_config = {
        "firmware": "test",
        "device_address": "1.2.3.4",
        "simulate": True,
        "variables": [],
    }
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config

    # Incorrect heartbeat for first instrument
    msg = MockMessage(
        topic="instruments/furnace_centre/heartbeat",
        payload=json.dumps({
            "state": "idle",
            "setpoints": {},
            "config": {"firmware": "wrong", "device_address": "1.2.3.4",
                       "simulate": True, "variables": []},
        }),
    )

    # Should not raise, because instrument status is still awaiting_config
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should not have updated instrument
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config
    assert state.instruments_ready == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_instruments_not_all_responded(
    message_bus,
    state,
    heartbeat_client,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments_ready == False

    names = ["mass_flow"]

    # Correct heartbeat for all but first instruments
    for name in names:
        msg = MockMessage(
            topic=f"instruments/{name}/heartbeat",
            payload=json.dumps({
                "state": "ready",
                "setpoints": {},
                "config": {"firmware": "test", "device_address": "1.2.3.4",
                           "simulate": True, "variables": []},
            }),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

    # Should have updated instruments, but not be ready yet
    for name in names:
        assert state.instruments[name]["state"] == "ready"
        assert state.instruments[name]["setpoints"] == {}
    assert state.status == "awaiting_instruments"
    assert state.instruments_ready == False

    # First instrument heartbeat with idle state
    msg = MockMessage(
        topic="instruments/furnace_centre/heartbeat",
        payload=json.dumps({
            "state": "idle",
            "setpoints": {},
            "config": {"firmware": "test", "device_address": "1.2.3.4",
                       "simulate": True, "variables": []},
        }),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should still not be ready
    assert state.instruments["furnace_centre"]["state"] is None
    assert state.instruments["furnace_centre"]["setpoints"] is None
    assert state.status == "awaiting_instruments"
    assert state.instruments_ready == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_instruments_all_responded(
    message_bus,
    state,
    heartbeat_client,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments_ready == False

    names = ["furnace_centre", "mass_flow"]

    # Correct heartbeat for all instruments
    for name in names:
        msg = MockMessage(
            topic=f"instruments/{name}/heartbeat",
            payload=json.dumps({
                "state": "ready",
                "setpoints": {},
                "config": {"firmware": "test", "device_address": "1.2.3.4",
                           "simulate": True, "variables": []},
            }),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

    assert state.instruments["mass_flow"]["state"] == "ready"
    assert state.instruments_ready == True
    assert state.status == "awaiting_instruments"

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/event/ready"
    assert json.loads(messages[0].payload)["experiment_id"] == "123"


def test_running_heartbeat_updates_instrument(
    message_bus,
    state,
    heartbeat_client,
):
    state.status = "running"

    msg = MockMessage(
        topic="instruments/furnace_centre/heartbeat",
        payload=json.dumps({
            "state": "adjusting",
            "setpoints": {"temperature": 42},
            "config": {"firmware": "test", "device_address": "1.2.3.4",
                       "simulate": True, "variables": []},
        }),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    assert state.instruments["furnace_centre"]["state"] == "adjusting"
    assert state.instruments["furnace_centre"]["setpoints"] == {"temperature": 42}

    messages = message_bus.get_messages(decoded=True)
    # No new messages should be published during running heartbeats
    assert len(messages) == 0
