import pytest
import json
from unittest.mock import patch

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
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
    def idle_mocks(self, message_bus, mock_state, mqtt_mocks, mock_setpoints):
        with (
            patch("src.on_controller_message.pe") as mock_publish_error,
            patch("src.on_controller_message.validate_experiment") as mock_validate,
            patch("src.on_controller_message.split_setpoints") as mock_split_setpoints,
            patch("src.on_controller_message.c_starting") as mock_c_starting,
        ):
            state = mock_state("idle")
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_idle,
                obj=state,
            )
            mock_validate_message = MockMessage(
                topic="controller/command/validate",
                payload=json.dumps({"id": "123", "file": "valid_file.json"}),
            )
            mock_split_setpoints.return_value = mock_setpoints
            mock_c_starting.return_value = None
            mock_c_starting.__name__ = "mock_c_starting"
            mock_validate.return_value = {
                "id": "123",
                "experiment_definition": ["some data"],
                "config": {"resolution": 42},
            }

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "msg": mock_validate_message,
                "validate_experiment": mock_validate,
                "split_setpoints": mock_split_setpoints,
                "c_starting": mock_c_starting,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        msg = MockMessage(topic="controller/command/run", payload="not important")

        c_idle(idle_mocks["controller_client"], msg, idle_mocks["state"])

        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            idle_mocks["state"], msg
        )
        idle_mocks["validate_experiment"].assert_not_called()

    def test_wrong_json(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["msg"].payload = "this is not json"

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].wrong_json.assert_called_once()
        idle_mocks["validate_experiment"].assert_not_called()

    def test_json_missing_file_key(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["msg"].payload = json.dumps({"id": "123"})

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].missing_keys.assert_called_once()
        idle_mocks["validate_experiment"].assert_not_called()

    def test_missing_file(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        mock_validate = idle_mocks["validate_experiment"]
        mock_validate.side_effect = ExperimentValidationError(
            "Experiment file not found - valid_file.json"
        )

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        mock_validate.assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].experiment_validation_error.assert_called_once_with(
            mock_validate.side_effect, "123"
        )
        messages = idle_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_file(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"
        mock_validate = idle_mocks["validate_experiment"]
        mock_validate.side_effect = ExperimentValidationError("Test validation error")

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        idle_mocks["split_setpoints"].assert_not_called()
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].experiment_validation_error.assert_called_once_with(
            mock_validate.side_effect, "123"
        )
        messages = idle_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_setpoints(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["split_setpoints"].side_effect = ValueError("Test setpoints error")

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        idle_mocks["validate_experiment"].assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        idle_mocks["split_setpoints"].assert_called_once_with(["some data"], 42)
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pe"].experiment_validation_error.assert_called_once_with(
            idle_mocks["split_setpoints"].side_effect, "123"
        )
        messages = idle_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_file(self, idle_mocks):
        assert idle_mocks["state"].experiment_uid == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        idle_mocks["validate_experiment"].assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        # Split setpoints called
        idle_mocks["split_setpoints"].assert_called_once_with(["some data"], 42)

        assert idle_mocks["state"].experiment_start_time != None
        assert idle_mocks["state"].experiment_uid == "123"
        assert idle_mocks["state"].status == "validating"
        assert idle_mocks["controller_client"].callback == idle_mocks["c_starting"]
        messages = idle_mocks["messages"]()
        assert len(messages) == 2
        assert messages[0].topic == "controller/validator/passed"
        assert '{"id": "123", "valid": true}' in messages[0].payload
        assert messages[1].topic == "controller/command/start"
        assert '{"id": "123"}' in messages[1].payload


class TestStarting:
    @pytest.fixture
    def s_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pe") as mock_publish_error,
            patch("src.on_controller_message.c_ready") as mock_c_ready,
            patch("src.on_controller_message.c_stopping") as mock_c_stopping,
        ):
            state = mock_state("starting")
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_starting,
                obj=state,
            )
            mock_c_ready.return_value = None
            mock_c_ready.__name__ = "mock_c_ready"

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "c_ready": mock_c_ready,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, s_mocks):
        assert s_mocks["state"].experiment_uid == "123"
        assert s_mocks["state"].status == "validating"
        assert s_mocks["controller_client"].callback == c_starting

        msg = MockMessage(topic="controller/command/run", payload="not important")
        c_starting(s_mocks["controller_client"], msg, s_mocks["state"])

        s_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            s_mocks["state"], msg
        )
        messages = s_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, s_mocks):
        assert s_mocks["state"].experiment_uid == "123"
        assert s_mocks["state"].status == "validating"
        assert s_mocks["controller_client"].callback == c_starting

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_starting(s_mocks["controller_client"], msg, s_mocks["state"])

        assert s_mocks["c_stopping"].called
        messages = s_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_start(self, s_mocks):
        assert s_mocks["state"].experiment_uid == "123"
        assert s_mocks["state"].status == "validating"
        assert s_mocks["controller_client"].callback == c_starting

        instrument_names = [ins for ins in s_mocks["state"].config.instruments.keys()]

        msg = MockMessage(
            topic="controller/command/start", payload=json.dumps({"id": "123"})
        )
        c_starting(s_mocks["controller_client"], msg, s_mocks["state"])

        # goes through starting to awaiting_instruments
        assert s_mocks["state"]._status_history == ["starting", "awaiting_instruments"]
        # State object updated correctly
        assert s_mocks["state"].experiment_uid == "123"
        assert s_mocks["state"].setpoints is not None
        assert s_mocks["state"].status == "awaiting_instruments"
        assert s_mocks["controller_client"].callback == s_mocks["c_ready"]
        # Instrument config list updated correctly
        assert len(s_mocks["state"].instrument_states) == len(instrument_names)
        assert s_mocks["state"].instruments_ready == False
        for instrument_name, instrument in s_mocks["state"].instrument_states.items():
            assert instrument_name in instrument_names
            assert instrument == {
                "last_contact": None,
                "config": None,
                "state": None,
                "setpoints": None,
            }
        # Timer message sent
        messages = s_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/command/start"
        assert messages[0].payload == json.dumps(
            {"source": "instrument_setup", "experiment_id": "123"}
        )


class TestReady:
    @pytest.fixture
    def rdy_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pe") as mock_publish_error,
            patch("src.on_controller_message.c_running") as mock_c_running,
            patch("src.on_controller_message.c_stopping") as mock_c_stopping,
        ):
            state = mock_state("ready")
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_ready,
                obj=state,
            )
            mock_c_running.return_value = None
            mock_c_running.__name__ = "mock_c_running"

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "c_running": mock_c_running,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, rdy_mocks):
        assert rdy_mocks["state"].experiment_uid == "123"
        assert rdy_mocks["state"].status == "awaiting_instruments"
        assert rdy_mocks["controller_client"].callback == c_ready

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"id": "123"}),
        )
        c_ready(rdy_mocks["controller_client"], msg, rdy_mocks["state"])

        rdy_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            rdy_mocks["state"], msg
        )
        messages = rdy_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, rdy_mocks):
        assert rdy_mocks["state"].experiment_uid == "123"
        assert rdy_mocks["state"].status == "awaiting_instruments"
        assert rdy_mocks["controller_client"].callback == c_ready

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_ready(rdy_mocks["controller_client"], msg, rdy_mocks["state"])

        assert rdy_mocks["c_stopping"].called
        messages = rdy_mocks["messages"]()
        assert len(messages) == 0

    def test_updates_states_correctly(self, rdy_mocks):
        assert rdy_mocks["state"].experiment_uid == "123"
        assert rdy_mocks["state"].status == "awaiting_instruments"
        assert rdy_mocks["controller_client"].callback == c_ready

        with patch("src.on_controller_message.assign_serial_id") as mock_assign:
            mock_assign.return_value = None
            msg = MockMessage(
                topic="controller/event/ready",
                payload=json.dumps({"experiment_id": "123"}),
            )
            c_ready(rdy_mocks["controller_client"], msg, rdy_mocks["state"])

            mock_assign.assert_called_once_with(rdy_mocks["state"])
            assert rdy_mocks["state"].status == "ready"
            assert rdy_mocks["state"].experiment_uid == "123"
            assert rdy_mocks["controller_client"].callback == rdy_mocks["c_running"]
            messages = rdy_mocks["messages"]()
            assert len(messages) == 1
            assert messages[0].topic == "controller/command/run"
            assert messages[0].payload == '{"experiment_id": "123"}'


class TestRunning:
    @pytest.fixture
    def r_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pe") as mock_publish_error,
            patch("src.on_controller_message.c_stopping") as mock_c_stopping,
        ):
            state = mock_state("running")
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_running,
                obj=state,
            )

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pe": mock_publish_error,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running

        msg = MockMessage(
            topic="controller/command/something_else", payload=json.dumps({"id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].status == "ready"
        r_mocks["pe"].incompatible_controller_status.assert_called_once_with(
            r_mocks["state"], msg
        )
        messages = r_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["c_stopping"].called
        messages = r_mocks["messages"]()
        assert len(messages) == 0

    def test_sends_end_signal_when_setpoints_empty(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["controller_client"].callback == c_running
        r_mocks["state"].setpoints = []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "123"}),
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["controller_client"].callback == r_mocks["c_stopping"]
        messages = r_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/end"
        assert messages[0].payload == json.dumps({"experiment_id": "123"})

    def test_updates_state_on_first_setpoint_only(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        assert r_mocks["state"].setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        # Should update state on first setpoint
        assert r_mocks["state"].status == "running"
        assert r_mocks["state"].current_setpoint is not None

        # Should not update state on second setpoint
        r_mocks["state"].status = "idle"
        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].status == "idle"

    def test_saves_past_setpoints(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        assert r_mocks["state"].setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        # Should not have saved "None" as past setpoint
        assert r_mocks["state"].past_setpoints == []
        assert r_mocks["state"].current_setpoint is not None
        new_sp = r_mocks["state"].current_setpoint

        # Should save current setpoint on next run
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].past_setpoints == [new_sp]

    def test_sets_current_setpoint(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        all_setpoints = r_mocks["state"].setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].current_setpoint == all_setpoints[0]

    def test_drops_current_setpoint_from_list(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        all_setpoints = r_mocks["state"].setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].setpoints == all_setpoints[1:]

    def test_sends_setpoint(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        first_sp = r_mocks["state"].setpoints[0]
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        messages = r_mocks["messages"]()
        assert len(messages) == 1 + len(instruments)

        for i, column in enumerate(instruments):
            instr_name, var_name = column.split("/", 1)
            assert messages[i].topic == f"instruments/{instr_name}/{var_name}/setpoint"
            assert json.loads(messages[i].payload) == {
                "value": first_sp[column],
            }

    def test_starts_setpoint_timer(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["state"].status == "ready"
        assert r_mocks["controller_client"].callback == c_running
        assert r_mocks["state"].current_setpoint is None
        first_sp = r_mocks["state"].setpoints[0]
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        messages = r_mocks["messages"]()
        assert len(messages) == 1 + len(instruments)
        assert messages[-1].topic == "controller/timer/command/start"
        assert json.loads(messages[-1].payload) == {
            "source": "setpoint",
            "experiment_id": "123",
            "duration": first_sp["duration"],
        }

    def test_saves_and_clears_last_setpoint(self, r_mocks):
        assert r_mocks["state"].experiment_uid == "123"
        assert r_mocks["controller_client"].callback == c_running
        last_setpoint = r_mocks["state"].setpoints[-1].copy()
        r_mocks["state"].current_setpoint = last_setpoint.copy()
        r_mocks["state"].status = "running"
        r_mocks["state"].setpoints = []

        msg = MockMessage(
            topic="controller/command/run", payload=json.dumps({"experiment_id": "123"})
        )
        c_running(r_mocks["controller_client"], msg, r_mocks["state"])

        assert r_mocks["state"].current_setpoint is None
        assert r_mocks["state"].past_setpoints == [last_setpoint]


class TestStopping:
    @pytest.fixture
    def state(self, mock_state):
        return mock_state("end")

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
