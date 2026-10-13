import copy
import json
import pytest
import threading
import time as t
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
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
def state(mock_state):
    return mock_state("idle")


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
    with patch("src.on_controller_message.val.validate_experiment") as mock_validate:
        mock_validate.return_value = mock_experiment_dict
        yield mock_validate


@pytest.fixture
def mock_dump():
    with patch("src.on_controller_message.dump_database_for_experiment") as mock_dump:
        mock_dump.return_value = None
        yield mock_dump


@pytest.fixture
def thread_exceptions(monkeypatch):
    """
    Collects exceptions raised in the message bus callback threads, instead of pytest
    reporting them as warnings, so tests can check the expected ones were raised.
    """
    caught = []
    monkeypatch.setattr(
        threading, "excepthook", lambda args: caught.append(args.exc_value)
    )
    return caught


def test_control_loop(
    message_bus,
    state,
    controller_client,
    heartbeat_client,
    mock_validate,
    mqtt_validator_mocks,
    mock_serial_id,
    mock_dump,
    capsys,
):
    assert state.status == "idle"
    checked_messages = 0

    # Start an experiment
    message_bus.publish(
        topic="controller/command/validate",
        payload=json.dumps({"file": "some_file", "temp_id": "123"}),
    )
    t.sleep(0.1)

    mock_validate.assert_called_once_with("some_file", state.config)
    # Should go through c_idle and c_starting, then expect instruments to respond
    assert state._status_history == ["validating", "starting", "awaiting_instruments"]
    mock_serial_id.assert_called_once()
    assert state.exp_config["temp_id"] == "123"
    assert state.experiment_id == "D123-456"
    instrument_names = sorted([ins for ins in state.config.instruments.keys()])
    driving_sensors = sorted(
        [
            actuator_config["driving_sensor"]
            for actuator_name, actuator_config in state.config.actuators.items()
        ]
    )
    messages = message_bus.get_messages()
    # expected_messages = validate + passed + start + 3 * instrument config + timer
    expected_messages = 7
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/command/validate"
    assert messages[1].topic == "controller/validator/passed"
    assert json.loads(messages[1].payload) == {
        "temp_id": "123",
        "experiment_id": "D123-456",
        "valid": True,
    }
    assert messages[2].topic == "instruments/furnace/configure"
    assert json.loads(messages[2].payload) == {
        "temperature": {"tolerance": 1, "offset": 273}
    }
    assert messages[3].topic == "instruments/pressure/configure"
    assert json.loads(messages[3].payload) == {"pressure": {"tolerance": 0.5}}
    assert messages[4].topic == "instruments/mass_flow/configure"
    assert json.loads(messages[4].payload) == {"mass_flow": {"tolerance": 1}}
    assert messages[5].topic == "controller/command/start"
    assert messages[6].topic == "controller/timer/command/start"
    assert json.loads(messages[6].payload) == {
        "source": "instrument_setup",
        "experiment_id": "D123-456",
    }
    checked_messages += expected_messages
    assert state.instruments_ready is False
    assert state.status == "awaiting_instruments"
    assert controller_client.callback.__name__ == "c_ready"

    # Respond with instrument heartbeats
    assert heartbeat_client.callback.__name__ == "on_heartbeat_message"
    for instrument in instrument_names:
        heartbeat = {
            "state": {"status": "running"},
            "setpoints": state.config.instruments[instrument]["default_setpoints"],
            "config": state.get_expected_heartbeat(instrument),
        }
        heartbeat["config"]["experiment"] = {
            "experiment_id": "D123-456",
            "calibration": {"some": "values"},
        }
        msg = MockMessage(
            topic=f"instruments/{instrument}/heartbeat",
            payload=json.dumps(heartbeat),
        )
        message_bus.publish(msg.topic, msg.payload.decode())
    t.sleep(0.1)

    # Each instrument heartbeat should be processed
    assert state.instruments_ready is True
    # Should go through c_ready and into c_running
    assert controller_client.callback.__name__ == "c_running"
    assert state._status_history[3:] == ["ready", "running"]
    assert state.status == "running"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = heartbeats + ready + run + setpoints + timer
    expected_messages = len(instrument_names) + 2 + len(driving_sensors) + 1
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
    assert json.loads(messages[len(instrument_names) + 1].payload) == {
        "experiment_id": "D123-456"
    }
    # Setpoint messages (for each instrument) then timer
    setpoint_start = len(instrument_names) + 2
    setpoint_sensors = []
    for i, msg in enumerate(messages[setpoint_start:-1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 4
        assert topic_parts[0] == "instruments"
        setpoint_sensors.append(f"{topic_parts[1]}/{topic_parts[2]}")
        assert topic_parts[3] == "setpoint"
    assert sorted(setpoint_sensors) == driving_sensors
    assert messages[-1].topic == "controller/timer/command/start"
    assert json.loads(messages[-1].payload)["source"] == "setpoint"
    assert json.loads(messages[-1].payload)["experiment_id"] == "D123-456"
    checked_messages += expected_messages

    # Simulate setpoint timer ticks
    n_setpoints = len(state.setpoints)
    past_setpoints = len(state.past_setpoints)
    message_bus.publish(
        "controller/command/run", json.dumps({"experiment_id": "D123-456"})
    )
    t.sleep(0.1)
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = run + setpoints + timer
    expected_messages = 1 + len(driving_sensors) + 1
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/command/run"
    setpoint_sensors = []
    for i, msg in enumerate(messages[1:-1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 4
        setpoint_sensors.append(f"{topic_parts[1]}/{topic_parts[2]}")
        assert topic_parts[3] == "setpoint"
    assert sorted(setpoint_sensors) == driving_sensors
    assert messages[-1].topic == "controller/timer/command/start"
    assert json.loads(messages[-1].payload)["source"] == "setpoint"
    assert json.loads(messages[-1].payload)["experiment_id"] == "D123-456"
    checked_messages += expected_messages
    assert len(state.setpoints) == n_setpoints - 1
    assert len(state.past_setpoints) == past_setpoints + 1
    # Continue simulating setpoint timer ticks until done
    for _ in range(n_setpoints - 1):
        message_bus.publish(
            "controller/command/run", json.dumps({"experiment_id": "D123-456"})
        )
        t.sleep(0.01)
    assert state.setpoints == []
    assert len(state.past_setpoints) == n_setpoints
    checked_messages += (n_setpoints - 1) * (1 + len(driving_sensors) + 1)

    # Final timer tick to end experiment
    message_bus.publish(
        "controller/command/run", json.dumps({"experiment_id": "D123-456"})
    )
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


def test_recover_on_exceptions_while_starting(
    message_bus,
    state,
    controller_client,
    heartbeat_client,
    mock_validate,
    mqtt_validator_mocks,
    mock_serial_id,
    mock_dump,
    mock_experiment_dict,
    thread_exceptions,
):
    assert state.status == "idle"

    mock_serial_id.side_effect = Exception("Serial ID assignment failed")

    message_bus.publish(
        topic="controller/command/validate",
        payload=json.dumps({"file": "some_file", "temp_id": "123"}),
    )
    t.sleep(0.1)

    # Should not move on to starting the experiment
    assert controller_client.callback.__name__ == "c_idle"
    assert message_bus.get_messages("controller/command/start") == []
    # Should go through error and recover to idle, rather than staying in validating
    assert state._status_history == ["validating", "error", "idle"]
    assert state.status == "idle"
    state.reset.assert_called_once()
    assert state.experiment_id is None
    # Recovery re-raises, so the generic MQTT wrapper still reports the error
    assert len(thread_exceptions) == 1
    assert str(thread_exceptions[0]) == "Serial ID assignment failed"


def test_recover_on_exceptions_while_running(
    message_bus,
    state,
    controller_client,
    heartbeat_client,
    mock_validate,
    mqtt_validator_mocks,
    mock_serial_id,
    mock_dump,
    mock_experiment_dict,
    thread_exceptions,
):
    assert state.status == "idle"

    # Start an experiment
    message_bus.publish(
        topic="controller/command/validate",
        payload=json.dumps({"file": "some_file", "temp_id": "123"}),
    )
    t.sleep(0.1)
    assert state.status == "awaiting_instruments"
    assert controller_client.callback.__name__ == "c_ready"

    # A malformed setpoint (column without instrument/variable) crashes c_running
    state.setpoints.insert(0, {"broken_column": 1, "duration": 2})

    # Instruments ready, so the controller moves to running and pops the first setpoint
    message_bus.publish(
        topic="controller/event/ready",
        payload=json.dumps({"experiment_id": "D123-456"}),
    )
    # Wait for the stop to be handled by c_stopping (which pauses for 1s)
    t.sleep(1.5)

    # Should go through error, then stop the experiment normally and recover to idle
    assert state._status_history == [
        "validating",
        "starting",
        "awaiting_instruments",
        "ready",
        "running",
        "error",
        "stopping",
        "idle",
    ]
    assert state.status == "idle"
    assert controller_client.callback.__name__ == "c_idle"
    state.reset.assert_called_once()
    assert state.experiment_id is None
    # Instruments were running, so they should be told to stop
    messages = message_bus.get_messages("controller/command/stop")
    assert len(messages) == 1
    assert json.loads(messages[0].payload) == {"experiment_id": "D123-456"}
    # Experiment data should be saved as in a normal stop
    mock_dump.assert_called_once()
    # Recovery re-raises, so the generic MQTT wrapper still reports the error
    assert len(thread_exceptions) == 1
    assert isinstance(thread_exceptions[0], ValueError)


def test_recover_on_exceptions_while_stopping(
    message_bus,
    state,
    controller_client,
    heartbeat_client,
    mock_validate,
    mqtt_validator_mocks,
    mock_serial_id,
    mock_dump,
    mock_experiment_dict,
    thread_exceptions,
):
    assert state.status == "idle"

    # Start an experiment and get it running
    message_bus.publish(
        topic="controller/command/validate",
        payload=json.dumps({"file": "some_file", "temp_id": "123"}),
    )
    t.sleep(0.1)
    message_bus.publish(
        topic="controller/event/ready",
        payload=json.dumps({"experiment_id": "D123-456"}),
    )
    t.sleep(0.1)
    assert state.status == "running"
    assert controller_client.callback.__name__ == "c_running"

    # Stopping fails while saving the experiment data
    mock_dump.side_effect = Exception("Database dump failed")

    # Stop requested while running, so c_running calls c_stopping directly
    message_bus.publish(
        topic="controller/command/stop",
        payload=json.dumps({"experiment_id": "D123-456"}),
    )
    # Wait for c_stopping (which pauses for 1s)
    t.sleep(1.5)

    # Should recover once (not once per nested callback) and not retry stopping
    assert state._status_history == [
        "validating",
        "starting",
        "awaiting_instruments",
        "ready",
        "running",
        "stopping",
        "error",
        "idle",
    ]
    assert state.status == "idle"
    assert controller_client.callback.__name__ == "c_idle"
    mock_dump.assert_called_once()
    state.reset.assert_called_once()
    assert state.experiment_id is None
    # Only the requested stop, recovery should not publish another one
    assert len(message_bus.get_messages("controller/command/stop")) == 1
    # Re-raised once through both wrappers, so the generic MQTT wrapper still reports it
    assert len(thread_exceptions) == 1
    assert str(thread_exceptions[0]) == "Database dump failed"
