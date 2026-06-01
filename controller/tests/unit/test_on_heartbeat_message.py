import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
    instrument_heartbeat_msg,
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
    assert messages[0].topic == "error/controller"
    assert "Controller is awaiting_instruments. Cannot act on heartbeat/something_else" in messages[0].payload


def test_wrong_json(message_bus, state, capsys):
    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload="not a json",
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/controller"
    exp_err = "Cannot decode instruments/instrument_1/heartbeat message, wrong JSON:"
    assert exp_err in messages[0].payload
    assert f"ERROR: {exp_err}" in capsys.readouterr().out


def test_validation_exception(message_bus, state):
    msg = MockMessage(
        topic="instruments/instrument_1/heartbeat",
        payload=json.dumps({"hello": "world"}),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    m = messages[0].payload
    assert "Invalid heartbeat from instrument_1:" in m
    assert "'hello' was unexpected" in m


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


def test_awaiting_instruments_wrong_config(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
    capsys,
):
    assert state.instruments["configured"] == False

    instruments = mock_experiment_dict["config"]["instruments"]
    first_instrument_name = instruments[0]["name"]
    first_instrument_config = {
        **{k: v for k, v in instruments[0].items() if k != "name"},
        "experiment_id": state.experiment_uid,
    }
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config

    # Incorrect heartbeat for first instrument
    wrong_config = instruments[0].copy()
    wrong_config["tolerance"] = wrong_config["tolerance"] + 1
    msg = instrument_heartbeat_msg(
        instrument=wrong_config, state="ready", setpoints={}, experiment_id="123"
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should not have updated instrument
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config
    assert state.instruments["configured"] == False

    # Should abort experiment due to wrong config
    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 2
    assert messages[0].topic == "error/sensor"
    m0 = json.loads(messages[0].payload)
    assert m0["code"] == "configuration"
    exp_err = "Instrument 'temperature' misconfigured. Expected {'tolerance': 0.21, 'experiment_id': '123'}, received {'tolerance': 1.21, 'experiment_id': '123'}"
    assert exp_err in m0["message"]
    assert f"ERROR: {exp_err}" in capsys.readouterr().out
    assert messages[1].topic == "controller/command/stop"
    assert json.loads(messages[1].payload)["id"] == "123"


def test_awaiting_instruments_racing_heartbeat(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.instruments["configured"] == False

    instruments = mock_experiment_dict["config"]["instruments"]
    first_instrument_name = instruments[0]["name"]
    first_instrument_config = {
        **{k: v for k, v in instruments[0].items() if k != "name"},
        "experiment_id": state.experiment_uid,
    }
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config

    # Incorrect heartbeat for first instrument
    wrong_config = instruments[0].copy()
    wrong_config["tolerance"] = wrong_config["tolerance"] + 1
    msg = instrument_heartbeat_msg(
        instrument=wrong_config, state="idle", setpoints={}
    )

    # Should not raise, because instrument status is still awaiting_config
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should not have updated instrument
    assert state.instruments[first_instrument_name]["state"] == None
    assert state.instruments[first_instrument_name]["setpoints"] == None
    assert state.instruments[first_instrument_name]["config"] == first_instrument_config
    assert state.instruments["configured"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_instruments_not_all_responded(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments["configured"] == False

    instruments = mock_experiment_dict["config"]["instruments"]

    # Correct heartbeat for all but first instruments
    for instrument in instruments[1:]:
        msg = instrument_heartbeat_msg(
            instrument=instrument, state="ready", setpoints={}, experiment_id="123"
        )
        on_heartbeat_message(heartbeat_client, msg, state)

    # Should have updated instruments, but not be ready yet
    for instrument in instruments[1:]:
        assert state.instruments[instrument["name"]]["state"] == "ready"
        assert state.instruments[instrument["name"]]["setpoints"] == {}
    assert state.status == "awaiting_instruments"
    assert state.instruments["configured"] == False

    # First instrument heartbeat with idle state
    msg = instrument_heartbeat_msg(
        instrument=instruments[0], state="idle", setpoints={}
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should still not be ready
    assert state.instruments[instruments[0]["name"]]["state"] == None
    assert state.instruments[instruments[0]["name"]]["setpoints"] == None
    assert state.status == "awaiting_instruments"
    assert state.instruments["configured"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_instruments_all_responded(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_instruments"
    assert state.instruments["configured"] == False

    instruments = mock_experiment_dict["config"]["instruments"]

    # Correct heartbeat for all instruments
    for instrument in instruments:
        msg = instrument_heartbeat_msg(
            instrument=instrument, state="ready", setpoints={}, experiment_id="123"
        )
        on_heartbeat_message(heartbeat_client, msg, state)

    assert state.instruments[instrument["name"]]["state"] == "ready"
    assert state.instruments["configured"] == True
    assert state.status == "awaiting_instruments"

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/event/ready"
    assert json.loads(messages[0].payload)["experiment_id"] == "123"


def test_running_heartbeat_updates_instrument(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    state.status = "running"
    instruments = mock_experiment_dict["config"]["instruments"]

    msg = instrument_heartbeat_msg(
        instrument=instruments[0], state="adjusting", setpoints={"temperature": 42}
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    assert state.instruments[instruments[0]["name"]]["state"] == "adjusting"
    assert state.instruments[instruments[0]["name"]]["setpoints"] == {"temperature": 42}

    messages = message_bus.get_messages(decoded=True)
    # No new messages should be published during running heartbeats
    assert len(messages) == 0
