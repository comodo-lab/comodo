import json
import pytest

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
    sensor_heartbeat_msg,
)

from src.on_heartbeat_message import on_heartbeat_message


# =============== Fixtures ===============


@pytest.fixture
def state(mock_experiment_dict, mock_setpoints):
    return mock_state("awaiting_sensors", mock_experiment_dict, mock_setpoints)


@pytest.fixture
def heartbeat_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="heartbeat",
        topics="heartbeat/#",
        callback=on_heartbeat_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


def test_incompatible_request(message_bus, heartbeat_client, state):
    assert state.experiment_uid == "123"

    msg = MockMessage(
        topic="heartbeat/something_else", payload=json.dumps({"uid": "123"})
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    assert "Heartbeat cannot act on heartbeat/something_else" in messages[0].payload


def test_wrong_json(message_bus, state):
    msg = MockMessage(
        topic="heartbeat/sensor/sensor_1",
        payload="not a json",
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    assert (
        "Error decoding heartbeat/sensor/sensor_1 message, wrong JSON"
        in messages[0].payload
    )


def test_validation_exception(message_bus, state):
    msg = MockMessage(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps({"hello": "world"}),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat/validation"
    m = messages[0].payload
    assert "Error validating heartbeat from sensor_1:" in m
    assert "Validation errors:" in m
    assert "'name' is a required property" in m
    assert "'status' is a required property" in m
    assert "'setpoint' is a required property" in m
    assert "'config' is a required property" in m


def test_unconfigured_sensor(message_bus, state):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert "sensor_1" not in state.sensors

    msg = MockMessage(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps(
            {
                "name": "sensor_1",
                "status": "ready",
                "setpoint": 1,
                "config": {"p": 1, "i": 1, "d": 1, "tolerance": 1},
            }
        ),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "error/heartbeat"
    assert "Sensor sensor_1 is not configured" in messages[0].payload


def test_unconfigured_sensor_idle(message_bus, state, heartbeat_client):
    assert state.experiment_uid == "123"
    state.status = "idle"
    assert "sensor_1" not in state.sensors

    msg = MockMessage(
        topic="heartbeat/sensor/sensor_1",
        payload=json.dumps(
            {
                "name": "sensor_1",
                "status": "awaiting_config",
                "setpoint": None,
                "config": {"p": None, "i": None, "d": None, "tolerance": None},
            }
        ),
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "No messages should be published in idle state"


def test_awaiting_sensors_wrong_config(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.sensors["configured"] == False

    sensors = mock_experiment_dict["config"]["sensors"]
    first_sensor_name = sensors[0]["name"]
    first_sensor_config = {k: v for k, v in sensors[0].items() if k != "name"}
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config

    # Incorrect heartbeat for first sensor
    wrong_config = sensors[0].copy()
    wrong_config["p"] = wrong_config["p"] + 1
    msg = sensor_heartbeat_msg(sensor=wrong_config, status="no_setpoint", setpoint=0)
    with pytest.raises(RuntimeError, match="Sensor misconfigured"):
        on_heartbeat_message(heartbeat_client, msg, state)

    # Should not have updated sensor
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config
    assert state.sensors["configured"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_sensors_racing_heartbeat(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.sensors["configured"] == False

    sensors = mock_experiment_dict["config"]["sensors"]
    first_sensor_name = sensors[0]["name"]
    first_sensor_config = {k: v for k, v in sensors[0].items() if k != "name"}
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config

    # Incorrect heartbeat for first sensor
    wrong_config = sensors[0].copy()
    wrong_config["p"] = wrong_config["p"] + 1
    msg = sensor_heartbeat_msg(
        sensor=wrong_config, status="awaiting_config", setpoint=0
    )

    # Should not raise, because sensor status is still awaiting_config
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should not have updated sensor
    assert state.sensors[first_sensor_name]["status"] == None
    assert state.sensors[first_sensor_name]["setpoint"] == None
    assert state.sensors[first_sensor_name]["config"] == first_sensor_config
    assert state.sensors["configured"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_sensors_not_all_responded(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = mock_experiment_dict["config"]["sensors"]

    # Correct heartbeat for all but first sensors
    for sensor in sensors[1:]:
        msg = sensor_heartbeat_msg(sensor=sensor, status="no_setpoint", setpoint=None)
        on_heartbeat_message(heartbeat_client, msg, state)

    # Should have updated sensors, but not be ready yet
    for sensor in sensors[1:]:
        assert state.sensors[sensor["name"]]["status"] == "no_setpoint"
        assert state.sensors[sensor["name"]]["setpoint"] == None
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    # First sensor heartbeat with awaiting_config
    msg = sensor_heartbeat_msg(
        sensor=sensors[0], status="awaiting_config", setpoint=None
    )
    on_heartbeat_message(heartbeat_client, msg, state)

    # Should still not be ready
    assert state.sensors[sensors[0]["name"]]["status"] == None
    assert state.sensors[sensors[0]["name"]]["setpoint"] == None
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 0, "Should only publish if ready"


def test_awaiting_sensors_all_responded(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    assert state.experiment_uid == "123"
    assert state.status == "awaiting_sensors"
    assert state.sensors["configured"] == False

    sensors = mock_experiment_dict["config"]["sensors"]

    # Correct heartbeat for all sensors
    for sensor in sensors:
        msg = sensor_heartbeat_msg(sensor=sensor, status="no_setpoint", setpoint=None)
        on_heartbeat_message(heartbeat_client, msg, state)

    assert state.sensors[sensor["name"]]["status"] == "no_setpoint"
    assert state.sensors["configured"] == True
    assert state.status == "awaiting_sensors"

    messages = message_bus.get_messages(decoded=True)
    assert len(messages) == 1
    assert messages[0].topic == "controller/ready"
    assert json.loads(messages[0].payload)["uid"] == "123"


def test_running_heartbeat_updates_sensor(
    message_bus,
    state,
    heartbeat_client,
    mock_experiment_dict,
):
    state.status = "running"
    sensors = mock_experiment_dict["config"]["sensors"]

    msg = sensor_heartbeat_msg(sensor=sensors[0], status="adjusting", setpoint=42)
    on_heartbeat_message(heartbeat_client, msg, state)

    assert state.sensors[sensors[0]["name"]]["status"] == "adjusting"
    assert state.sensors[sensors[0]["name"]]["setpoint"] == 42

    messages = message_bus.get_messages(decoded=True)
    # No new messages should be published during running heartbeats
    assert len(messages) == 0
