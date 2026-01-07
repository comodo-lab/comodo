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
    sensor_heartbeat_msg,
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
        topics="heartbeat/#",
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
def mock_validate_dict():
    with patch("src.on_heartbeat_message.validate_dict") as mock_validate_dict:

        def side_effect(input_dict, schema_path):
            return input_dict  # Simply return the input dict for testing

        mock_validate_dict.side_effect = side_effect
        yield mock_validate_dict


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
    mock_validate_dict,
    mock_serial_id,
    mock_dump,
    capsys,
):
    assert state.status == "idle"
    checked_messages = 0

    # Start an experiment
    message_bus.publish(
        topic="controller/validate",
        payload=json.dumps({"file": "some_file", "uid": "123"}),
    )
    t.sleep(0.1)

    mock_validate.assert_called_once_with("some_file", state.schema_path)
    # Should go through c_idle and c_starting, then expect sensors to respond
    assert state._status_history == ["validating", "starting", "awaiting_sensors"]
    assert state.experiment_uid == "123"
    sensor_names = sorted(
        [sensor for sensor in state.sensors.keys() if sensor != "configured"]
    )
    messages = message_bus.get_messages()
    # expected_messages = validate + passed + start + timer + sensor setups
    expected_messages = 4 + len(sensor_names)
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/validate"
    assert messages[1].topic == "validator/passed"
    assert messages[2].topic == "controller/start"
    assert messages[3].topic == "timer/start/sensor_setup"
    setup_sensors = []
    for msg in messages[4:]:
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "sensor"
        setup_sensors.append(topic_parts[1])
        assert topic_parts[2] == "setup"
    assert sorted(setup_sensors) == sensor_names
    checked_messages += expected_messages
    assert state.sensors["configured"] is False
    assert state.status == "awaiting_sensors"
    assert controller_client.callback.__name__ == "c_ready"

    # Respond with sensor heartbeats
    assert heartbeat_client.callback.__name__ == "on_heartbeat_message"
    for sensor in sensor_names:
        msg = sensor_heartbeat_msg(
            sensor={"name": sensor} | state.sensors[sensor]["config"],
            status="no_setpoint",
            setpoint=None,
        )
        message_bus.publish(msg.topic, msg.payload.decode())
    t.sleep(0.1)

    # Each sensor heartbeat should be processed
    assert mock_validate_dict.call_count == len(sensor_names)
    assert state.sensors["configured"] is True
    # Should go through c_ready and into c_running
    mock_serial_id.assert_called_once()
    assert controller_client.callback.__name__ == "c_running"
    assert state._status_history[3:] == ["ready", "running"]
    assert state.status == "running"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = heartbeats + ready + run + setpoints + timer
    expected_messages = len(sensor_names) + 2 + len(sensor_names) + 1
    assert len(messages) == expected_messages
    heartbeat_sensors = []
    for i, msg in enumerate(messages[: len(sensor_names)]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "heartbeat"
        assert topic_parts[1] == "sensor"
        heartbeat_sensors.append(topic_parts[2])
    assert sorted(heartbeat_sensors) == sensor_names
    assert messages[len(sensor_names)].topic == "controller/ready"
    assert messages[len(sensor_names) + 1].topic == "controller/run"
    setpoint_sensors = []
    for i, msg in enumerate(messages[len(sensor_names) + 2 : -1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "sensor"
        setpoint_sensors.append(topic_parts[1])
        assert topic_parts[2] == "setpoint"
    assert sorted(setpoint_sensors) == sensor_names
    assert messages[-1].topic == "timer/start/setpoint"
    checked_messages += expected_messages

    # Simulate setpoint timer ticks
    n_setpoints = len(state.setpoints)
    past_setpoints = len(state.past_setpoints)
    message_bus.publish("controller/run", json.dumps({"uid": "D123-456"}))
    t.sleep(0.1)
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = run + setpoints + timer
    expected_messages = 1 + len(sensor_names) + 1
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/run"
    setpoint_sensors = []
    for i, msg in enumerate(messages[1:-1]):
        topic_parts = msg.topic.split("/")
        assert len(topic_parts) == 3
        assert topic_parts[0] == "sensor"
        setpoint_sensors.append(topic_parts[1])
        assert topic_parts[2] == "setpoint"
    assert sorted(setpoint_sensors) == sensor_names
    assert messages[-1].topic == "timer/start/setpoint"
    checked_messages += expected_messages
    assert len(state.setpoints) == n_setpoints - 1
    assert len(state.past_setpoints) == past_setpoints + 1
    # Continue simulating setpoint timer ticks until done
    for _ in range(n_setpoints - 1):
        message_bus.publish("controller/run", json.dumps({"uid": "D123-456"}))
        t.sleep(0.01)
    assert state.setpoints == []
    assert len(state.past_setpoints) == n_setpoints
    checked_messages += (n_setpoints - 1) * (1 + len(sensor_names) + 1)

    # Final timer tick to end experiment
    message_bus.publish("controller/run", json.dumps({"uid": "D123-456"}))
    t.sleep(2)

    # Should go from c_running to c_stopping
    assert controller_client.callback.__name__ == "c_idle"
    assert state._status_history[4:] == ["running", "stopping", "idle"]
    assert state.status == "idle"
    messages = message_bus.get_messages()[checked_messages:]
    # expected_messages = run + end
    expected_messages = 2
    assert len(messages) == expected_messages
    assert messages[0].topic == "controller/run"
    assert messages[1].topic == "controller/end"
    checked_messages += expected_messages
    mock_dump.assert_called_once()
    state.reset.assert_called_once()
    stop_message = f"Experiment D123-456 finished and the controller has been reset."
    assert stop_message in capsys.readouterr().out
    assert "error" not in capsys.readouterr().out.lower()
