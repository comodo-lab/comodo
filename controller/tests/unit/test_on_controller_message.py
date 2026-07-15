import pytest
import json
from unittest.mock import patch, ANY

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
from src.validation import ExperimentValidationError


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
    def mock_split_setpoints(self, mock_setpoints):
        with patch("src.on_controller_message.split_setpoints") as mock_split_setpoints:
            mock_split_setpoints.return_value = mock_setpoints
            yield mock_split_setpoints

    @pytest.fixture(autouse=True)
    def mock_c_starting(self):
        with patch("src.on_controller_message.c_starting") as mock_c_starting:
            mock_c_starting.return_value = None
            mock_c_starting.__name__ = "mock_c_starting"
            yield mock_c_starting

    # ========================================

    def test_incompatible_controller_status(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(topic="controller/command/run", payload="not important")
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is idle. Cannot act on controller/command/run."
            in messages[0].payload
        )

    def test_wrong_json(self, message_bus, state, controller_client, capsys):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(
            topic="controller/command/validate", payload="this is not json"
        )
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = "Cannot decode controller/command/validate message, wrong JSON:"
        assert exp_err in messages[0].payload
        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_json_missing_file_key(self, message_bus, state, controller_client, capsys):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(
            topic="controller/command/validate", payload=json.dumps({"id": "123"})
        )
        c_idle(controller_client, msg, state)

        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        exp_err = (
            "Cannot decode controller/command/validate message, missing: \n   'file'"
        )
        m = json.loads(messages[0].payload)
        assert exp_err in m["message"]
        assert f"ERROR: {exp_err}" in capsys.readouterr().out

    def test_missing_file(self, message_bus, state, controller_client):
        assert state.experiment_uid == None
        assert state.status == "idle"

        msg = MockMessage(
            topic="controller/command/validate",
            payload=json.dumps({"id": "123", "file": "missing_file.json"}),
        )
        with patch("src.on_controller_message.validate_experiment") as mock_validate:
            mock_validate.side_effect = ExperimentValidationError(
                "Experiment file not found - missing_file.json"
            )
            c_idle(controller_client, msg, state)

            mock_validate.assert_called_once_with("missing_file.json", ANY)

        assert state._status_history == ["validating", "idle"]
        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        assert "Experiment file not found" in messages[0].payload

    def test_invalid_file(
        self,
        message_bus,
        state,
        controller_client,
        mock_split_setpoints,
    ):
        assert state.experiment_uid == None
        assert state.experiment_start_time == None
        assert state.status == "idle"

        with patch("src.on_controller_message.validate_experiment") as mock_validate:
            mock_validate.side_effect = ExperimentValidationError(
                "Test validation error"
            )
            msg = MockMessage(
                topic="controller/command/validate",
                payload=json.dumps({"id": "123", "file": "invalid_file.json"}),
            )
            c_idle(controller_client, msg, state)

        mock_split_setpoints.assert_not_called()
        assert state._status_history == ["validating", "idle"]
        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        m = json.loads(messages[0].payload)
        assert m["code"] == "experiment_validation"
        assert "Test validation error" in m["message"]

    def test_invalid_setpoints(
        self,
        message_bus,
        state,
        controller_client,
        mock_c_starting,
        mock_split_setpoints,
    ):
        assert state.experiment_uid == None
        assert state.experiment_start_time == None
        assert state.status == "idle"

        with patch("src.on_controller_message.validate_experiment") as mock_validate:
            mock_validate.return_value = {
                "id": "123",
                "experiment_definition": ["some data"],
                "config": {"resolution": 42},
            }
            mock_split_setpoints.side_effect = ValueError("Test setpoints error")
            msg = MockMessage(
                topic="controller/command/validate",
                payload=json.dumps({"id": "123", "file": "valid_file.json"}),
            )
            c_idle(controller_client, msg, state)

            mock_validate.assert_called_once_with("valid_file.json", ANY)
            # Split setpoints called
            mock_split_setpoints.assert_called_once_with(["some data"], 42)

        assert state._status_history == ["validating", "idle"]
        assert state.experiment_uid == None
        assert state.status == "idle"
        assert controller_client.callback == c_idle
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/validator"
        m = json.loads(messages[0].payload)
        assert m["code"] == "experiment_validation"
        assert "Test setpoints error" in m["message"]

    def test_valid_file(
        self,
        message_bus,
        state,
        controller_client,
        mock_c_starting,
        mock_split_setpoints,
    ):
        assert state.experiment_uid == None
        assert state.experiment_start_time == None
        assert state.status == "idle"

        with patch("src.on_controller_message.validate_experiment") as mock_validate:
            mock_validate.return_value = {
                "id": "123",
                "experiment_definition": ["some data"],
                "config": {"resolution": 42},
            }
            msg = MockMessage(
                topic="controller/command/validate",
                payload=json.dumps({"id": "123", "file": "valid_file.json"}),
            )
            c_idle(controller_client, msg, state)

            mock_validate.assert_called_once_with("valid_file.json", ANY)
            # Split setpoints called
            mock_split_setpoints.assert_called_once_with(["some data"], 42)

        assert state.experiment_start_time != None
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == mock_c_starting
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 2
        assert messages[0].topic == "controller/validator/passed"
        assert '{"id": "123", "valid": true}' in messages[0].payload
        assert messages[1].topic == "controller/command/start"
        assert '{"id": "123"}' in messages[1].payload


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
    def mock_c_ready(self):
        with patch("src.on_controller_message.c_ready") as mock_c_ready:
            mock_c_ready.return_value = None
            mock_c_ready.__name__ = "mock_c_ready"
            yield mock_c_ready

    # ========================================

    def test_incompatible_controller_status(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        msg = MockMessage(topic="controller/command/run", payload="not important")
        c_starting(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is validating. Cannot act on controller/command/run."
            in messages[0].payload
        )

    def test_accepts_stop_signal(self, state, controller_client, mock_c_stopping):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_starting(controller_client, msg, state)

        assert mock_c_stopping.called

    def test_valid_start(
        self,
        message_bus,
        state,
        controller_client,
        mock_experiment_dict,
        mock_c_ready,
    ):
        assert state.experiment_uid == "123"
        assert state.status == "validating"
        assert controller_client.callback == c_starting

        instrument_names = ["furnace_centre", "furnace_left", "mass_flow"]

        msg = MockMessage(
            topic="controller/command/start", payload=json.dumps({"id": "123"})
        )
        c_starting(controller_client, msg, state)

        # goes through starting to awaiting_instruments
        assert state._status_history == ["starting", "awaiting_instruments"]
        # State object updated correctly
        assert state.experiment_uid == "123"
        assert state.setpoints is not None
        assert state.status == "awaiting_instruments"
        assert controller_client.callback == mock_c_ready
        # Instrument config list updated correctly
        assert len(state.instrument_states) == len(instrument_names)
        assert state.instruments_ready == False
        for instrument_name, instrument in state.instrument_states.items():
            assert instrument_name in instrument_names

            assert "last_contact" in instrument
            assert instrument["last_contact"] is None
            assert "config" in instrument
            assert instrument["config"] is None
            assert "state" in instrument
            assert instrument["state"] is None
            assert "setpoints" in instrument
            assert instrument["setpoints"] is None
        # Timer message sent
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/command/start"
        assert messages[0].payload == json.dumps(
            {"source": "instrument_setup", "experiment_id": "123"}
        )


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

    @pytest.fixture
    def mock_c_running(self, autouse=True):
        with patch("src.on_controller_message.c_running") as mock_c_running:
            mock_c_running.return_value = None
            mock_c_running.__name__ = "mock_c_running"
            yield mock_c_running

    # ========================================

    def test_incompatible_controller_status(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_instruments"
        assert controller_client.callback == c_ready

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"id": "123"}),
        )
        c_ready(controller_client, msg, state)

        assert state.status == "awaiting_instruments"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is awaiting_instruments. Cannot act on controller/command/something_else."
            in messages[0].payload
        )

    def test_accepts_stop_signal(
        self, message_bus, state, controller_client, mock_c_stopping
    ):
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_instruments"
        assert controller_client.callback == c_ready

        msg = MockMessage(topic="controller/command/stop", payload="not important")
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
        assert state.status == "awaiting_instruments"
        assert controller_client.callback == c_ready

        with patch("src.on_controller_message.assign_serial_id") as mock_assign:
            mock_assign.return_value = None
            msg = MockMessage(
                topic="controller/event/ready",
                payload=json.dumps({"experiment_id": "123"}),
            )
            c_ready(controller_client, msg, state)

            mock_assign.assert_called_once_with(state)
            assert state.status == "ready"
            assert state.experiment_uid == "123"
            assert controller_client.callback == mock_c_running
            messages = message_bus.get_messages(decoded=True)
            assert len(messages) == 1
            assert messages[0].topic == "controller/command/run"
            assert messages[0].payload == '{"experiment_id": "123"}'


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

    # ========================================

    def test_incompatible_controller_status(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running

        msg = MockMessage(
            topic="controller/command/something_else", payload=json.dumps({"id": "123"})
        )
        c_running(controller_client, msg, state)

        assert state.status == "ready"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "error/controller"
        assert (
            "Controller status is ready. Cannot act on controller/command/something_else."
            in messages[0].payload
        )

    def test_accepts_stop_signal(
        self, message_bus, state, controller_client, mock_c_stopping
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_running(controller_client, msg, state)

        assert mock_c_stopping.called

    def test_sends_end_signal_when_setpoints_empty(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert controller_client.callback == c_running
        state.setpoints = []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "123"}),
        )
        c_running(controller_client, msg, state)

        assert controller_client.callback.__name__ == "c_stopping"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/end"
        assert messages[0].payload == json.dumps({"experiment_id": "123"})

    def test_updates_state_on_first_setpoint_only(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(controller_client, msg, state)

        # Should update state on first setpoint
        assert state.status == "running"
        assert state.current_setpoint is not None

        # Should not update state on second setpoint
        state.status = "idle"
        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(controller_client, msg, state)

        assert state.status == "idle"

    def test_saves_past_setpoints(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
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

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
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

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
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
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1 + len(instruments)

        for i, column in enumerate(instruments):
            instr_name, var_name = column.split("/", 1)
            assert messages[i].topic == f"instruments/{instr_name}/{var_name}/setpoint"
            assert json.loads(messages[i].payload) == {
                "value": first_sp[column],
            }

    def test_starts_setpoint_timer(
        self, message_bus, state, controller_client, mock_experiment_dict
    ):
        assert state.experiment_uid == "123"
        assert state.status == "ready"
        assert controller_client.callback == c_running
        assert state.current_setpoint is None
        first_sp = state.setpoints[0]
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(controller_client, msg, state)

        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1 + len(instruments)
        assert messages[-1].topic == "controller/timer/command/start"
        assert json.loads(messages[-1].payload) == {
            "source": "setpoint",
            "experiment_id": "123",
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

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
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

    def test_incompatible_controller_status(
        self, message_bus, state, controller_client
    ):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"id": "123"}),
        )
        c_stopping(controller_client, msg, state)

        assert state.status == "running"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[-1].topic == "error/controller"
        assert (
            "Controller status is running. Cannot act on controller/command/something_else."
            in messages[-1].payload
        )

    def test_checks_uid(self, message_bus, state, controller_client):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(
            topic="controller/command/stop",
            payload=json.dumps({"id": "456"}),
        )
        c_stopping(controller_client, msg, state)

        assert state.status == "running"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 1
        assert messages[-1].topic == "error/controller"
        assert (
            "Current experiment is 123. Controller cannot act on controller/command/stop for experiment 456."
            in messages[-1].payload
        )

    def test_valid_end(self, message_bus, state, controller_client, mock_dump, capsys):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        assert controller_client.callback == c_stopping

        msg = MockMessage(
            topic="controller/event/end", payload=json.dumps({"experiment_id": "123"})
        )
        c_stopping(controller_client, msg, state)

        assert state._status_history == ["stopping", "idle"]
        assert state.status == "idle"
        mock_dump.assert_called_once()
        state.reset.assert_called_once()
        assert controller_client.callback.__name__ == "mock_c_idle"
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0
        stop_message = f"Experiment 123 finished and the controller has been reset."
        assert stop_message in capsys.readouterr().out

    def test_valid_stop_from_any_callback(
        self, message_bus, state, controller_client, mock_dump, capsys
    ):
        assert state.experiment_uid == "123"
        assert state.status == "running"
        controller_client.callback = "mock_callback"

        msg = MockMessage(
            topic="controller/command/stop", payload=json.dumps({"id": "123"})
        )
        c_stopping(controller_client, msg, state)

        assert state._status_history == ["stopping", "idle"]
        assert state.status == "idle"
        mock_dump.assert_called_once()
        state.reset.assert_called_once()
        messages = message_bus.get_messages(decoded=True)
        assert len(messages) == 0
        stop_message = f"Experiment 123 was stopped and the controller has been reset."
        assert stop_message in capsys.readouterr().out
