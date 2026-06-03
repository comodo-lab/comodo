import json
import pytest
import time as t
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
    instrument_heartbeat_msg,
)

from src.on_controller_message import (
    c_idle,
    c_starting,
    c_ready,
    c_running,
    c_stopping,
)
from src.on_heartbeat_message import on_heartbeat_message


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("idle", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def controller_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="controller",
        topics="controller/#",
        callback=c_idle,
        obj=state,
    )
    return mqtt_mocks["client_instance"]("controller")


@pytest.fixture
def heartbeat_client(mqtt_mocks, state):
    mqtt_mocks["client_class"](
        id="heartbeat",
        topics="instruments/+/heartbeat",
        callback=on_heartbeat_message,
        obj=state,
    )
    return mqtt_mocks["client_instance"]("heartbeat")


@pytest.fixture
def mock_validate(mock_experiment_dict):
    with patch("src.on_controller_message.validate_file") as mock_validate:
        mock_validate.return_value = mock_experiment_dict
        yield mock_validate


@pytest.fixture
def mock_serial_id():
    with patch("src.on_controller_message.assign_serial_id") as mock_assign_serial_id:

        def side_effect(obj):
            obj.experiment_uid = f"D123-456"
            obj.exp_file = "/path/to/experiment/D123-456.json"

        mock_assign_serial_id.side_effect = side_effect
        yield mock_assign_serial_id


@pytest.fixture
def mock_dump():
    with patch("src.on_controller_message.dump_database_for_experiment") as mock_dump:
        mock_dump.return_value = None
        yield mock_dump


def test_control_loop(
    message_bus,
    state,
    controller_client,
    heartbeat_client,
    mock_validate,
    mock_serial_id,
    mock_dump,
    capsys,
):
    assert state.status == "idle"
    checked_messages = 0

    # Start an experiment
    message_bus.publish(
        topic="controller/command/validate",
        payload=json.dumps({"file": "some_file", "id": "123"}),
    )
    t.sleep(0.1)

    mock_validate.assert_called_once_with("some_file", state.schema_path)
    # Should go through c_idle and c_starting, then expect instruments to respond
    assert state._status_history == ["validating", "starting", "awaiting_instruments"]
    assert state.experiment_uid == "123"
    instrument_names = sorted(
        [instrument for instrument in state.instruments.keys() if instrument != "configured"]
    )
    messages = message_bus.get_messages()
    # expected_messages = validate + passed + start + timer
    expected_messages = 4
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/command/validate"
    assert messages[1].topic == "controller/validator/passed"
    assert messages[2].topic == "controller/command/start"
    assert messages[3].topic == "controller/timer/command/start"
    assert json.loads(messages[3].payload) == {"source": "instrument_setup", "experiment_id": "123"}
    checked_messages += expected_messages
    assert state.instruments["configured"] is False
    assert state.status == "awaiting_instruments"
    assert controller_client.callback.__name__ == "c_ready"

    # Respond with instrument heartbeats
    assert heartbeat_client.callback.__name__ == "on_heartbeat_message"
    for instrument in instrument_names:
        msg = instrument_heartbeat_msg(
            instrument={"name": instrument} | state.instruments[instrument]["config"],
            state="ready",
            setpoints={},
        )
        message_bus.publish(msg.topic, msg.payload.decode())
    t.sleep(0.1)

    # Each instrument heartbeat should be processed
    assert state.instruments["configured"] is True
    # Should go through c_ready and into c_running
    mock_serial_id.assert_called_once()
    assert controller_client.callback.__name__ == "c_running"
    assert state._status_history[3:] == ["ready", "running"]
    assert state.status == "running"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = heartbeats + ready + run + setpoints + timer
    expected_messages = len(instrument_names) + 2 + len(instrument_names) + 1
    assert len(messages) == expected_messages
    heartbeat_instruments = []
    for i, msg in enumerate(messages[: len(instrument_names)]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "instruments"
        heartbeat_instruments.append(topic_parts[1])
        assert topic_parts[2] == "heartbeat"
    assert sorted(heartbeat_instruments) == instrument_names
    assert messages[len(instrument_names)].topic == "controller/event/ready"
    assert messages[len(instrument_names) + 1].topic == "controller/command/run"
    assert json.loads(messages[len(instrument_names) + 1].payload) == {"experiment_id": "D123-456"}
    # Setpoint messages (for each instrument) then timer
    setpoint_start = len(instrument_names) + 2
    setpoint_instruments = []
    for i, msg in enumerate(messages[setpoint_start : -1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 4
        assert topic_parts[0] == "instruments"
        setpoint_instruments.append(topic_parts[1])
        assert topic_parts[3] == "setpoint"
    assert sorted(setpoint_instruments) == instrument_names
    assert messages[-1].topic == "controller/timer/command/start"
    assert json.loads(messages[-1].payload)["source"] == "setpoint"
    assert json.loads(messages[-1].payload)["experiment_id"] == "D123-456"
    checked_messages += expected_messages

    # Simulate setpoint timer ticks
    n_setpoints = len(state.setpoints)
    past_setpoints = len(state.past_setpoints)
    message_bus.publish("controller/command/run", json.dumps({"experiment_id": "D123-456"}))
    t.sleep(0.1)
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = run + setpoints + timer
    expected_messages = 1 + len(instrument_names) + 1
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/command/run"
    setpoint_instruments = []
    for i, msg in enumerate(messages[1:-1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 4
        setpoint_instruments.append(topic_parts[1])
        assert topic_parts[3] == "setpoint"
    assert sorted(setpoint_instruments) == instrument_names
    assert messages[-1].topic == "controller/timer/command/start"
    assert json.loads(messages[-1].payload)["source"] == "setpoint"
    assert json.loads(messages[-1].payload)["experiment_id"] == "D123-456"
    checked_messages += expected_messages
    assert len(state.setpoints) == n_setpoints - 1
    assert len(state.past_setpoints) == past_setpoints + 1
    # Continue simulating setpoint timer ticks until done
    for _ in range(n_setpoints - 1):
        message_bus.publish("controller/command/run", json.dumps({"experiment_id": "D123-456"}))
        t.sleep(0.01)
    assert state.setpoints == []
    assert len(state.past_setpoints) == n_setpoints
    checked_messages += (n_setpoints - 1) * (1 + len(instrument_names) + 1)

    # Final timer tick to end experiment
    message_bus.publish("controller/command/run", json.dumps({"experiment_id": "D123-456"}))
    t.sleep(2)

    # Should go from c_running to c_stopping
    assert controller_client.callback.__name__ == "c_idle"
    assert state._status_history[4:] == ["running", "stopping", "idle"]
    assert state.status == "idle"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = run + end
    expected_messages = 2
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/command/run"
    assert messages[1].topic == "controller/event/end"
    assert json.loads(messages[1].payload) == {"experiment_id": "D123-456"}
    checked_messages += expected_messages
    mock_dump.assert_called_once()
    state.reset.assert_called_once()
    stop_message = f"Experiment D123-456 finished and the controller has been reset."
    assert stop_message in capsys.readouterr().out
    assert "error" not in capsys.readouterr().out.lower()
