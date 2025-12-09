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
    mock_c_stopping,
)

from src.on_controller_message import (
    c_idle,
    c_starting,
    c_ready,
    c_running,
    c_stopping,
    assign_serial_id,
)
from src.validation import ValidationException


class TestIdle:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        return mock_state("idle", mock_experiment_dict, mock_setpoints)

    @pytest.fixture
    def controller_client(self, mqtt_mocks, state):
        mqtt_mocks["client_class"](
            id="controller",
            topics="controller/#",
            callback=c_idle,
            obj=state,
        )
        return mqtt_mocks["client_instance"]

    @pytest.fixture(autouse=True)
    def mock_c_starting(self):
        with patch("src.on_controller_message.c_starting") as mock_c_starting:
            mock_c_starting.return_value = None
            mock_c_starting.__name__ = "mock_c_starting"
            yield mock_c_starting

    # ========================================

    def test_incompatible_request(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(topic="controller/run", payload="not important")
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert "Controller is idle. Cannot act on controller/run" in messages[0].payload

    def test_wrong_json(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(topic="controller/validate", payload="this is not json")
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Error decoding controller/validate message, wrong JSON"
            in messages[0].payload
        )

    def test_json_missing_file_key(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(
            topic="controller/validate", payload=json.dumps({"uid": "123"})
        )
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Error decoding controller/validate message, missing: \n   'file'"
            in json.loads(messages[0].payload)["error"]
        )

    def test_missing_file(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(
            topic="controller/validate",
            payload=json.dumps({"uid": "123", "file": "missing_file.json"}),
        )
        with patch("src.on_controller_message.validate_file") as mock_validate_file:
            mock_validate_file.side_effect = ValidationException(
                f"Error: File not found - {state.schema_path}"
            )
            c_idle(controller_client, msg, state)

            mock_validate_file.assert_called_once_with(
                "missing_file.json", state.schema_path
            )

        assert state._status_history == ["validating", "idle"]
        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator/failed"
        assert "File not found" in messages[0].payload

    def test_valid_file(self, message_bus, state, controller_client, mock_c_starting):
        assert state.experiment_uid == None
        assert state.experiment_start_time == None
        assert state.status == "idle"

        with patch("src.on_controller_message.validate_file") as mock_validate_file:
            mock_validate_file.return_value = {
                "uid": "123",
                "experiment": {},
            }
            msg = MockMessage(
                topic="controller/validate",
                payload=json.dumps({"uid": "123", "file": "valid_file.json"}),
            )
            c_idle(controller_client, msg, state)

            mock_validate_file.assert_called_once_with(
                "valid_file.json", state.schema_path
            )

        assert state.experiment_start_time != None
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == mock_c_starting
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 2
        assert messages[0].topic == "validator/passed"
        assert '{"uid": "123", "valid": true}' in messages[0].payload
        assert messages[1].topic == "controller/start"
        assert '{"uid": "123"}' in messages[1].payload

    def test_invalid_file(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        with patch("src.on_controller_message.validate_file") as mock_validate_file:
            mock_validate_file.side_effect = ValidationException(
                f"Test validation error"
            )
            msg = MockMessage(
                topic="controller/validate",
                payload=json.dumps({"uid": "123", "file": "invalid_file.json"}),
            )
            c_idle(controller_client, msg, state)

        assert state._status_history == ["validating", "idle"]
        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator/failed"
        assert "Test validation error" in messages[0].payload
        assert '"uid": "123"' in messages[0].payload


class TestStarting:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        return mock_state("starting", mock_experiment_dict, mock_setpoints)

    @pytest.fixture
    def controller_client(self, mqtt_mocks, state):
        mqtt_mocks["client_class"](
            id="controller",
            topics="controller/#",
            callback=c_starting,
            obj=state,
        )
        return mqtt_mocks["client_instance"]

    @pytest.fixture(autouse=True)
    def mock_split_setpoints(self, mock_setpoints):
        with patch("src.on_controller_message.split_setpoints") as mock_split_setpoints:
            mock_split_setpoints.return_value = mock_setpoints
            yield mock_split_setpoints

    @pytest.fixture(autouse=True)
    def mock_c_ready(self):
        with patch("src.on_controller_message.c_ready") as mock_c_ready:
            mock_c_ready.return_value = None
            mock_c_ready.__name__ = "mock_c_ready"
            yield mock_c_ready

    # ========================================

    def test_incompatible_request(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        msg = MockMessage(topic="controller/run", payload="not important")
        c_starting(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller is validating. Cannot act on controller/run"
            in messages[0].payload
        )

    def test_accepts_stop_signal(self, state, controller_client, mock_c_stopping):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        msg = MockMessage(topic="controller/stop", payload="not important")
        c_starting(controller_client, msg, state)

        assert mock_c_stopping.called

    def test_valid_start(
        self,
        message_bus,
        state,
        controller_client,
        mock_experiment_dict,
        mock_split_setpoints,
        mock_c_ready,
    ):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        sensors = mock_experiment_dict["config"]["sensors"]
        sensor_names = [sensor["name"] for sensor in sensors]

        msg = MockMessage(topic="controller/start", payload=json.dumps({"uid": "123"}))
        c_starting(controller_client, msg, state)

        # goes through starting to awaiting_sensors
        assert state._status_history == ["starting", "awaiting_sensors"]
        # State object updated correctly
        assert state.experiment_uid == "123"
        assert state.setpoints is not None
        assert state.status == "awaiting_sensors"
        assert controller_client.callback == mock_c_ready
        # Sensor config list updated correctly
        assert len(state.sensors) == len(sensors) + 1
        assert state.sensors["configured"] == False
        for sensor_key in state.sensors.keys():
            if sensor_key != "configured":
                assert sensor_key in sensor_names
                sensor = state.sensors[sensor_key]
                assert "last_contact" in sensor
                assert sensor["last_contact"] is None
                assert "config" in sensor
                assert sensor["config"] is not None
                assert "status" in sensor
                assert sensor["status"] is None
                assert "setpoint" in sensor
                assert sensor["setpoint"] is None
        # Split setpoints called
        mock_split_setpoints.assert_called_once_with(
            mock_experiment_dict["experiment"],
            mock_experiment_dict["config"]["resolution"],
        )
        # Timer message sent
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1 + len(sensors)
        assert messages[0].topic == "timer/start/sensor_setup"
        assert messages[0].payload == json.dumps({"uid": "123"})
        # Sensor setup messages sent
        for i, sensor in enumerate(sensors):
            assert messages[i + 1].topic == f"sensor/{sensor['name']}/setup"
            assert messages[i + 1].payload == json.dumps(sensor)


class TestReady:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        return mock_state("ready", mock_experiment_dict, mock_setpoints)

    @pytest.fixture
    def controller_client(self, mqtt_mocks, state):
        mqtt_mocks["client_class"](
            id="controller",
            topics="controller/#",
            callback=c_ready,
            obj=state,
        )
        return mqtt_mocks["client_instance"]

    @pytest.fixture(autouse=True)
    def mock_split_setpoints(self, mock_setpoints):
        with patch("src.on_controller_message.split_setpoints") as mock_split_setpoints:
            mock_split_setpoints.return_value = mock_setpoints
            yield mock_split_setpoints

    @pytest.fixture
    def mock_c_running(self, autouse=True):
        with patch("src.on_controller_message.c_running") as mock_c_running:
            mock_c_running.return_value = None
            mock_c_running.__name__ = "mock_c_running"
            yield mock_c_running

    # ========================================

    def test_incompatible_request(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"
        assert controller_client.callback == c_ready

        msg = MockMessage(
            topic="controller/something_else",
            payload=json.dumps({"uid": "123"}),
        )
        c_ready(controller_client, msg, state)

        assert state.status == "awaiting_sensors"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller is awaiting_sensors. Cannot act on controller/something_else"
            in messages[0].payload
        )

    def test_accepts_stop_signal(
        self, message_bus, state, controller_client, mock_c_stopping
    ):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"
        assert controller_client.callback == c_ready

        msg = MockMessage(topic="controller/stop", payload="not important")
        c_ready(controller_client, msg, state)

        assert mock_c_stopping.called

    def test_updates_states_correctly(
        self,
        message_bus,
        state,
        controller_client,
        mock_c_running,
    ):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_sensors"
        assert controller_client.callback == c_ready

        with patch("src.on_controller_message.assign_serial_id") as mock_assign:
            mock_assign.return_value = None
            msg = MockMessage(
                topic="controller/ready", payload=json.dumps({"uid": "123"})
            )
            c_ready(controller_client, msg, state)

            mock_assign.assert_called_once_with(state)
            assert state.status == "ready"
            assert state.experiment_uid == "123"
            assert controller_client.callback == mock_c_running
            messages = message_bus.get_messages(decoded=True)
            assert len(messages) == 1
            assert messages[0].topic == "controller/run"
            assert messages[0].payload == '{"uid": "123"}'


class TestRunning:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        return mock_state("running", mock_experiment_dict, mock_setpoints)

    @pytest.fixture
    def controller_client(self, mqtt_mocks, state):
        mqtt_mocks["client_class"](
            id="controller",
            topics="controller/#",
            callback=c_running,
            obj=state,
        )
        return mqtt_mocks["client_instance"]

    @pytest.fixture
    def mock_c_end(self, autouse=True):
        with patch("src.on_controller_message.c_end") as mock_c_end:
            mock_c_end.return_value = None
            mock_c_end.__name__ = "mock_c_end"
            yield mock_c_end

    # ========================================

    def test_incompatible_request(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running

        msg = MockMessage(
            topic="controller/something_else", payload=json.dumps({"uid": "123"})
        )
        c_running(controller_client, msg, state)

        assert state.status == "ready"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller is ready. Cannot act on controller/something_else"
            in messages[0].payload
        )

    def test_accepts_stop_signal(
        self, message_bus, state, controller_client, mock_c_stopping
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running

        msg = MockMessage(topic="controller/stop", payload="not important")
        c_running(controller_client, msg, state)

        assert mock_c_stopping.called

    def test_sends_end_signal_when_setpoints_empty(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert controller_client.callback == c_running
        state.setpoints = []

        msg = MockMessage(
            topic="controller/run",
            payload=json.dumps({"uid": "123"}),
        )
        c_running(controller_client, msg, state)

        assert controller_client.callback.__name__ == "c_stopping"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/end"
        assert messages[0].payload == json.dumps({"uid": "123"})

    def test_updates_state_on_first_setpoint_only(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        # Should update state on first setpoint
        assert state.status == "running"
        assert state.current_setpoint is not None

        # Should not update state on second setpoint
        state.status = "idle"
        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        assert state.status == "idle"

    def test_saves_past_setpoints(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        # Should not have saved "None" as past setpoint
        assert state.past_setpoints == []
        assert state.current_setpoint is not None
        new_sp = state.current_setpoint

        # Should save current setpoint on next run
        c_running(controller_client, msg, state)

        assert state.past_setpoints == [new_sp]

    def test_sets_current_setpoint(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        all_setpoints = state.setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        assert state.current_setpoint == all_setpoints[0]

    def test_drops_current_setpoint_from_list(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        all_setpoints = state.setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        assert state.setpoints == all_setpoints[1:]

    def test_sends_setpoint(
        self, message_bus, state, controller_client, mock_experiment_dict
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        first_sp = state.setpoints[0]
        sensors = [k for k in first_sp if k != "duration"]

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1 + len(sensors)

        for i, sensor in enumerate(sensors):
            assert messages[i].topic == f"sensor/{sensor}/setpoint"
            assert json.loads(messages[i].payload) == {
                "duration": first_sp["duration"],
                sensor: first_sp[sensor],
            }

    def test_starts_setpoint_timer(
        self, message_bus, state, controller_client, mock_experiment_dict
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        first_sp = state.setpoints[0]
        sensors = [k for k in first_sp if k != "duration"]

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1 + len(sensors)
        assert messages[-1].topic == "timer/start/setpoint"
        assert json.loads(messages[-1].payload) == {
            "uid": "123",
            "duration": first_sp["duration"],
        }

    def test_saves_and_clears_last_setpoint(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert controller_client.callback == c_running
        state.status == "running"
        last_setpoint = state.setpoints[-1].copy()
        state.current_setpoint = last_setpoint.copy()
        state.setpoints = []

        msg = MockMessage(topic="controller/run", payload=json.dumps({"uid": "123"}))
        c_running(controller_client, msg, state)

        assert state.current_setpoint is None
        assert state.past_setpoints == [last_setpoint]


class TestStopping:
    @pytest.fixture
    def state(self, mock_experiment_dict, mock_setpoints):
        return mock_state("end", mock_experiment_dict, mock_setpoints)

    @pytest.fixture
    def controller_client(self, mqtt_mocks, state):
        mqtt_mocks["client_class"](
            id="controller",
            topics="controller/#",
            callback=c_stopping,
            obj=state,
        )
        return mqtt_mocks["client_instance"]

    @pytest.fixture(autouse=True)
    def mock_c_idle(
        self,
    ):
        with patch("src.on_controller_message.c_idle") as mock_c_idle:
            mock_c_idle.return_value = None
            mock_c_idle.__name__ = "mock_c_idle"
            yield mock_c_idle

    @pytest.fixture(autouse=True)
    def mock_dump(
        self,
    ):
        with patch(
            "src.on_controller_message.dump_database_for_experiment"
        ) as mock_dump:
            mock_dump.return_value = None
            yield mock_dump

    # ========================================

    def test_incompatible_request(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(
            topic="controller/something_else",
            payload=json.dumps({"uid": "123"}),
        )
        c_stopping(controller_client, msg, state)

        assert state.status == "running"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[-1].topic == "error/controller"
        assert (
            "Controller is running. Cannot act on controller/something_else"
            in messages[-1].payload
        )

    def test_checks_uid(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(
            topic="controller/stop",
            payload=json.dumps({"uid": "456"}),
        )
        c_stopping(controller_client, msg, state)

        assert state.status == "running"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[-1].topic == "error/controller"
        assert (
            "Current experiment is 123. Cannot act on controller/stop for experiment 456."
            in messages[-1].payload
        )

    def test_valid_stop(self, message_bus, state, controller_client, mock_dump):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(topic="controller/stop", payload=json.dumps({"uid": "123"}))
        c_stopping(controller_client, msg, state)

        assert state.status == "stopping"
        mock_dump.assert_called_once()
        state.reset.assert_called_once()
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/stopped"
        assert messages[0].payload == json.dumps({"uid": "123"})

    def test_controller_stopped_changes_callback_to_idle(
        self, message_bus, state, controller_client
    ):
        assert controller_client.callback == c_stopping
        state.status = "stopping"

        msg = MockMessage(
            topic="controller/stopped", payload=json.dumps({"uid": "123"})
        )
        c_stopping(controller_client, msg, state)

        assert controller_client.callback.__name__ == "mock_c_idle"

    def test_stop_from_any_callback(
        self, message_bus, state, controller_client, mock_dump
    ):
        assert state.experiment_uid == "123"
        state.status == "something"
        controller_client.callback = "mock_callback"

        msg = MockMessage(topic="controller/stop", payload=json.dumps({"uid": "123"}))
        c_stopping(controller_client, msg, state)

        assert state.status == "stopping"
        mock_dump.assert_called_once()
        state.reset.assert_called_once()
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/stopped"
        assert messages[0].payload == json.dumps({"uid": "123"})
