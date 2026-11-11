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
from src.controller_state import cstate


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
        topics=["instruments/+/heartbeat", "setpoint_controllers/+/heartbeat"],
        callback=on_heartbeat_message,
        obj=state,
    )
    return mqtt_mocks["client_instance"]("heartbeat")


@pytest.fixture
def mock_validate(mock_experiment_dict):
    with patch("src.on_controller_message.val.validate_experiment") as mock_validate:
        mock_validate.return_value = mock_experiment_dict
        yield mock_validate


@pytest.fixture(autouse=True)
def data_path(tmp_path):
    """A temporary data folder, where the controller records the running experiment."""
    with patch("src.controller_helper.data_path", new=str(tmp_path)):
        yield tmp_path


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
    # expected_messages = validate + passed + 3 * instrument config + spc config + start + timer
    expected_messages = 8
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
        "temperature": {"tolerance": 5, "offset": 273}
    }
    assert messages[3].topic == "instruments/pressure/configure"
    assert json.loads(messages[3].payload) == {"pressure": {"tolerance": 0.2}}
    assert messages[4].topic == "instruments/mass_flow/configure"
    assert json.loads(messages[4].payload) == {"mass_flow": {"tolerance": 1}}
    spc_id = "pressure-pressure--mass_flow-mass_flow"
    assert messages[5].topic == f"setpoint_controllers/{spc_id}/configure"
    assert json.loads(messages[5].payload) == {
        "pid": {
            "k_p": 10.0,
            "k_i": 1.0,
            "k_d": 0.1,
            "k_aw": 0.05,
            "k_df": 0.01,
            "max_rate": None,
        }
    }
    assert messages[6].topic == "controller/command/start"
    assert messages[7].topic == "controller/timer/command/start"
    assert json.loads(messages[7].payload) == {
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

    # Not ready until the setpoint controller reports the expected PID config
    assert state.instruments_ready is False
    message_bus.publish(
        f"setpoint_controllers/{spc_id}/heartbeat",
        json.dumps(spc_heartbeat(state, spc_id)),
    )
    t.sleep(0.1)

    # Each instrument and spc heartbeat should be processed
    assert state.instruments_ready is True
    # Should go through c_ready and into c_running
    assert controller_client.callback.__name__ == "c_running"
    assert state._status_history[3:] == ["ready", "running"]
    assert state.status == "running"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = heartbeats + spc heartbeat + ready + run + setpoints + timer
    expected_messages = len(instrument_names) + 1 + 2 + len(driving_sensors) + 1
    assert len(messages) == expected_messages
    heartbeat_instruments = []
    for i, msg in enumerate(messages[: len(instrument_names)]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "instruments"
        heartbeat_instruments.append(topic_parts[1])
        assert topic_parts[2] == "heartbeat"
    assert sorted(heartbeat_instruments) == instrument_names
    n_heartbeats = len(instrument_names) + 1
    assert (
        messages[n_heartbeats - 1].topic == f"setpoint_controllers/{spc_id}/heartbeat"
    )
    assert messages[n_heartbeats].topic == "controller/event/ready"
    assert messages[n_heartbeats + 1].topic == "controller/command/run"
    assert json.loads(messages[n_heartbeats + 1].payload) == {
        "experiment_id": "D123-456"
    }
    # Setpoint messages (for each instrument) then timer
    setpoint_start = n_heartbeats + 2
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


@pytest.fixture
def start_monitored_experiment(
    message_bus,
    mqtt_mocks,
    mock_comodo_config,
    mock_validate,
    mqtt_validator_mocks,
    mock_serial_id,
):
    """
    Returns a function that starts an experiment with a real controller state (so the
    instruments are evaluated on every controller heartbeat) and the given config
    globals, with every instrument responding once at its first setpoints.
    It returns the controller state and client, once the experiment is running.
    """

    def start(**config_globals):
        mock_comodo_config.globals.update(config_globals)
        state = cstate()
        state.config = mock_comodo_config
        state.reset()
        for client_id, topics, callback in [
            ("controller", "controller/#", c_idle),
            (
                "heartbeat",
                ["instruments/+/heartbeat", "setpoint_controllers/+/heartbeat"],
                on_heartbeat_message,
            ),
        ]:
            mqtt_mocks["client_class"](
                id=client_id, topics=topics, callback=callback, obj=state
            )

        message_bus.publish(
            topic="controller/command/validate",
            payload=json.dumps({"file": "some_file", "temp_id": "123"}),
        )
        t.sleep(0.1)
        assert state.status == "awaiting_instruments"
        for instrument in state.config.instruments:
            message_bus.publish(
                f"instruments/{instrument}/heartbeat",
                json.dumps(instrument_heartbeat(state, instrument)),
            )
        for spc_id in state.config.spcs:
            message_bus.publish(
                f"setpoint_controllers/{spc_id}/heartbeat",
                json.dumps(spc_heartbeat(state, spc_id)),
            )
        t.sleep(0.1)
        assert state.status == "running"
        return state, mqtt_mocks["client_instance"]("controller")

    return start


def instrument_heartbeat(state, instrument, measurements=None):
    """
    Returns a heartbeat of a running instrument with the expected config, at its default
    setpoints (the first setpoints of the mock experiment). Its measurements are at the
    setpoints, unless given.
    """
    setpoints = state.config.instruments[instrument]["default_setpoints"]
    return {
        "state": {
            "status": "running",
            "measurements": dict(setpoints) if measurements is None else measurements,
        },
        "setpoints": setpoints,
        "config": copy.deepcopy(state.get_expected_heartbeat(instrument)),
    }


def spc_heartbeat(state, spc_id, pid=None):
    """
    Returns a heartbeat of a setpoint controller with the PID config of the experiment,
    unless given.
    """
    spc = state.config.spcs[spc_id]
    expected_pid = state.get_expected_spc_config(spc_id)["pid"]
    return {
        "state": {
            "status": "adjusting",
            "enabled": True,
            "sensor_measurement": None,
            "actuator_setpoint": None,
            "experiment_id": state.experiment_id,
        },
        "setpoints": {"sensor_setpoint": None},
        "config": {
            "sensor": spc["external_sensor"],
            "actuator": spc["actuator"],
            "pid": {
                "max": 100.0,
                "min": 0.0,
                "max_rate": None,
                **(expected_pid if pid is None else pid),
            },
        },
    }


def get_controller_heartbeats(message_bus):
    messages = message_bus.get_messages("controller/heartbeat", decoded=True)
    return [json.loads(m.payload) for m in messages]


def test_experiment_stops_if_instruments_stop_responding(
    message_bus, start_monitored_experiment, mock_dump
):
    # No heartbeat means silent for over 0.3s (max_missed_heartbeats * heartbeat
    # interval), and the 3rd evaluation of an instrument in a bad state is an error
    state, controller_client = start_monitored_experiment(
        heartbeat_interval=0.1, bad_state_tolerance=2
    )

    # Instruments are evaluated on every controller heartbeat, at their setpoints first
    message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    assert get_controller_heartbeats(message_bus)[-1]["state"] == {
        "status": "running",
        "variables": {
            "furnace/temperature": "at_setpoint",
            "pressure/pressure": "at_setpoint",
        },
    }

    # Instruments stop responding, and are in a bad state for 3 controller heartbeats
    t.sleep(0.4)
    for _ in range(3):
        message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    assert [
        hb["state"]["status"] for hb in get_controller_heartbeats(message_bus)[1:]
    ] == [
        "running",
        "running",
        "error",
    ]
    assert get_controller_heartbeats(message_bus)[-1]["state"]["variables"] == {
        "furnace/temperature": "no_heartbeat",
        "pressure/pressure": "no_heartbeat",
    }
    # Check that further heartbeats don't repeat the errors
    message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    errors = message_bus.get_messages("error/controller", decoded=True)
    assert sorted(json.loads(m.payload)["message"] for m in errors) == [
        "Instrument furnace in bad state for too long.",
        "Instrument pressure in bad state for too long.",
    ]


def test_experiment_stops_if_instruments_cannot_keep_up_with_setpoints(
    message_bus, start_monitored_experiment, mock_dump
):
    # Adjusting for more than 1 setpoint (missed_setpoint_tolerance * resolution 2s /
    # heartbeat interval 1s = 2 controller heartbeats) is an error, so the 3rd is an error
    state, controller_client = start_monitored_experiment(missed_setpoint_tolerance=1)

    # Instruments are evaluated on every controller heartbeat, at their setpoints first
    message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    assert get_controller_heartbeats(message_bus)[-1]["state"] == {
        "status": "running",
        "variables": {
            "furnace/temperature": "at_setpoint",
            "pressure/pressure": "at_setpoint",
        },
    }

    # The furnace keeps responding with the right setpoint, but its temperature drops
    # out of tolerance (5) and does not recover for 3 controller heartbeats
    message_bus.publish(
        "instruments/furnace/heartbeat",
        json.dumps(instrument_heartbeat(state, "furnace", {"temperature": 10})),
    )
    t.sleep(0.1)
    for _ in range(3):
        message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    assert [
        hb["state"]["status"] for hb in get_controller_heartbeats(message_bus)[1:]
    ] == [
        "running",
        "running",
        "error",
    ]
    assert get_controller_heartbeats(message_bus)[-1]["state"]["variables"] == {
        "furnace/temperature": "adjusting",
        "pressure/pressure": "at_setpoint",
    }
    # Check that further heartbeats don't repeat the error
    message_bus.publish("controller/heartbeat", json.dumps(state.heartbeat()))
    errors = message_bus.get_messages("error/controller", decoded=True)
    assert [json.loads(m.payload)["message"] for m in errors] == [
        "Instrument furnace not keeping up with setpoints."
    ]


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
