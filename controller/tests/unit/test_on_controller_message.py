import pytest
import json
from unittest.mock import patch, MagicMock

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
from utils.mqtt_validator import MQTTValidationException
from src.validation import ExperimentValidationError


class TestIdle:
    @pytest.fixture
    def idle_mocks(
        self,
        message_bus,
        mock_state,
        mqtt_mocks,
        mqtt_validator_mocks,
        mock_setpoints,
        mock_serial_id,
    ):
        with (
            patch("src.on_controller_message.pub_err") as mock_publish_error,
            patch("src.on_controller_message.val.validate_experiment") as mock_validate,
            patch("src.on_controller_message.split_setpoints") as mock_split_setpoints,
            patch("src.on_controller_message.c_starting") as mock_c_starting,
        ):
            state = mock_state("idle")
            state.set_hb_experiment_config = MagicMock()
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_idle,
                obj=state,
            )
            mock_validate_message = MockMessage(
                topic="controller/command/validate",
                payload=json.dumps({"file": "valid_file.json", "temp_id": "123"}),
            )
            mock_split_setpoints.return_value = mock_setpoints
            mock_c_starting.return_value = None
            mock_c_starting.__name__ = "mock_c_starting"
            mock_validate.return_value = {
                "temp_id": "123",
                "experiment_definition": ["some data"],
                "config": {"resolution": 42},
            }

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "validate_message": mqtt_validator_mocks["validate_message"],
                "msg": mock_validate_message,
                "validate_experiment": mock_validate,
                "split_setpoints": mock_split_setpoints,
                "serial_id": mock_serial_id,
                "c_starting": mock_c_starting,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, idle_mocks):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        msg = MockMessage(topic="controller/command/run", payload="not important")

        c_idle(idle_mocks["controller_client"], msg, idle_mocks["state"])

        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pub_err"].incompatible_controller_status.assert_called_once_with(
            idle_mocks["state"], msg
        )
        idle_mocks["validate_experiment"].assert_not_called()
        idle_mocks["serial_id"].assert_not_called()

    def test_invalid_message(self, idle_mocks):
        err = MQTTValidationException("Invalid JSON")
        idle_mocks["validate_message"].side_effect = err
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["msg"].payload = "this is not json"

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        idle_mocks["validate_message"].assert_called_once_with(
            idle_mocks["msg"].topic, idle_mocks["msg"].payload
        )
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pub_err"].message_validation.assert_called_once_with(err)
        idle_mocks["validate_experiment"].assert_not_called()
        idle_mocks["serial_id"].assert_not_called()

    def test_missing_file(self, idle_mocks, capsys):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        mock_validate = idle_mocks["validate_experiment"]
        mock_validate.side_effect = ExperimentValidationError(
            "Experiment file not found - valid_file.json"
        )

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        captured = capsys.readouterr()
        assert "Validating experiment 123..." in captured.out
        mock_validate.assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pub_err"].experiment_validation_error.assert_called_once_with(
            mock_validate.side_effect, "123"
        )
        idle_mocks["serial_id"].assert_not_called()
        messages = idle_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_file(self, idle_mocks, capsys):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"
        mock_validate = idle_mocks["validate_experiment"]
        mock_validate.side_effect = ExperimentValidationError("Test validation error")

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        captured = capsys.readouterr()
        assert "Validating experiment 123..." in captured.out
        idle_mocks["split_setpoints"].assert_not_called()
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["pub_err"].experiment_validation_error.assert_called_once_with(
            mock_validate.side_effect, "123"
        )
        idle_mocks["serial_id"].assert_not_called()
        messages = idle_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_setpoints(self, idle_mocks, capsys):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["split_setpoints"].side_effect = ValueError("Test setpoints error")

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        captured = capsys.readouterr()
        assert "Validating experiment 123..." in captured.out
        idle_mocks["validate_experiment"].assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        idle_mocks["split_setpoints"].assert_called_once_with(["some data"], 42)
        assert idle_mocks["state"]._status_history == ["validating", "idle"]
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].status == "idle"
        assert idle_mocks["controller_client"].callback == c_idle
        idle_mocks["serial_id"].assert_not_called()
        idle_mocks["pub_err"].experiment_validation_error.assert_called_once_with(
            idle_mocks["split_setpoints"].side_effect, "123"
        )
        messages = idle_mocks["messages"]()
        assert len(messages) == 0
        idle_mocks["state"].set_hb_experiment_config.assert_not_called()

    def test_valid_file(self, idle_mocks, capsys):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        captured = capsys.readouterr()
        assert "Validating experiment 123..." in captured.out
        assert "Experiment 123 valid. Assigned experiment id: D123-456" in captured.out
        idle_mocks["validate_experiment"].assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        # Split setpoints called
        idle_mocks["split_setpoints"].assert_called_once_with(["some data"], 42)
        idle_mocks["serial_id"].assert_called_once_with(idle_mocks["state"])
        assert idle_mocks["state"].experiment_start_time != None
        assert idle_mocks["state"].experiment_id == "D123-456"
        assert idle_mocks["state"].status == "validating"
        assert idle_mocks["controller_client"].callback == idle_mocks["c_starting"]
        messages = idle_mocks["messages"]()
        assert len(messages) == 2
        assert messages[0].topic == "controller/validator/passed"
        assert (
            '{"temp_id": "123", "experiment_id": "D123-456", "valid": true}'
            in messages[0].payload
        )
        assert messages[1].topic == "controller/command/start"
        assert '{"experiment_id": "D123-456"}' in messages[1].payload
        assert idle_mocks["state"].set_hb_experiment_config.call_args_list == [
            (("furnace", {"experiment_id": "D123-456"}),),
            (("pressure", {"experiment_id": "D123-456"}),),
            (("mass_flow", {"experiment_id": "D123-456"}),),
        ]

    def test_valid_file_with_instrument_config(self, idle_mocks, capsys):
        assert idle_mocks["state"].experiment_id == None
        assert idle_mocks["state"].experiment_start_time == None
        assert idle_mocks["state"].status == "idle"
        idle_mocks["validate_experiment"].return_value = {
            "temp_id": "123",
            "experiment_definition": ["some data"],
            "config": {"resolution": 42, "instruments": {"furnace": {"offset": 273}}},
        }

        c_idle(idle_mocks["controller_client"], idle_mocks["msg"], idle_mocks["state"])

        captured = capsys.readouterr()
        assert "Validating experiment 123..." in captured.out
        assert "Experiment 123 valid. Assigned experiment id: D123-456" in captured.out
        idle_mocks["validate_experiment"].assert_called_once_with(
            "valid_file.json", idle_mocks["state"].config
        )
        # Split setpoints called
        idle_mocks["split_setpoints"].assert_called_once_with(["some data"], 42)
        idle_mocks["serial_id"].assert_called_once_with(idle_mocks["state"])
        assert idle_mocks["state"].experiment_start_time != None
        assert idle_mocks["state"].experiment_id == "D123-456"
        assert idle_mocks["state"].status == "validating"
        assert idle_mocks["controller_client"].callback == idle_mocks["c_starting"]
        messages = idle_mocks["messages"]()
        assert len(messages) == 3
        assert messages[0].topic == "controller/validator/passed"
        assert (
            '{"temp_id": "123", "experiment_id": "D123-456", "valid": true}'
            in messages[0].payload
        )
        assert messages[1].topic == "instruments/furnace/configure"
        assert messages[1].payload == '{"offset": 273}'
        assert messages[2].topic == "controller/command/start"
        assert '{"experiment_id": "D123-456"}' in messages[2].payload
        assert idle_mocks["state"].set_hb_experiment_config.call_args_list == [
            (("furnace", {"offset": 273}),),
            (("furnace", {"experiment_id": "D123-456"}),),
            (("pressure", {"experiment_id": "D123-456"}),),
            (("mass_flow", {"experiment_id": "D123-456"}),),
        ]


class TestStarting:
    @pytest.fixture
    def start_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pub_err") as mock_publish_error,
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
                "pub_err": mock_publish_error,
                "c_ready": mock_c_ready,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, start_mocks):
        assert start_mocks["state"].status == "validating"
        assert start_mocks["controller_client"].callback == c_starting

        msg = MockMessage(topic="controller/command/run", payload="not important")
        c_starting(start_mocks["controller_client"], msg, start_mocks["state"])

        start_mocks["pub_err"].incompatible_controller_status.assert_called_once_with(
            start_mocks["state"], msg
        )
        messages = start_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, start_mocks):
        assert start_mocks["state"].status == "validating"
        assert start_mocks["controller_client"].callback == c_starting

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_starting(start_mocks["controller_client"], msg, start_mocks["state"])

        assert start_mocks["c_stopping"].called
        messages = start_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_start(self, start_mocks, capsys):
        state = start_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "validating"
        assert start_mocks["controller_client"].callback == c_starting

        instrument_names = state.config.instruments.keys()

        msg = MockMessage(
            topic="controller/command/start",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_starting(start_mocks["controller_client"], msg, start_mocks["state"])

        captured = capsys.readouterr()
        assert "Awaiting instruments for experiment D123-456..." in captured.out
        # goes through starting to awaiting_instruments
        assert state._status_history == ["starting", "awaiting_instruments"]
        # State object updated correctly
        assert state.experiment_id == "D123-456"
        assert state.setpoints is not None
        assert state.status == "awaiting_instruments"
        assert start_mocks["controller_client"].callback == start_mocks["c_ready"]
        # Instrument config list updated correctly
        assert len(state.instrument_states) == len(instrument_names)
        assert state.instruments_ready == False
        for instrument_name, instrument in state.instrument_states.items():
            assert instrument_name in instrument_names
            assert instrument == {
                "last_contact": None,
                "config": None,
                "state": None,
                "setpoints": None,
            }
        # Timer message sent
        messages = start_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/timer/command/start"
        assert messages[0].payload == json.dumps(
            {"source": "instrument_setup", "experiment_id": "D123-456"}
        )


class TestReady:
    @pytest.fixture
    def ready_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pub_err") as mock_publish_error,
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
                "pub_err": mock_publish_error,
                "c_running": mock_c_running,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, ready_mocks):
        assert ready_mocks["state"].experiment_id == "D123-456"
        assert ready_mocks["state"].status == "awaiting_instruments"
        assert ready_mocks["controller_client"].callback == c_ready

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_ready(ready_mocks["controller_client"], msg, ready_mocks["state"])

        ready_mocks["pub_err"].incompatible_controller_status.assert_called_once_with(
            ready_mocks["state"], msg
        )
        messages = ready_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, ready_mocks):
        assert ready_mocks["state"].status == "awaiting_instruments"
        assert ready_mocks["controller_client"].callback == c_ready

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_ready(ready_mocks["controller_client"], msg, ready_mocks["state"])

        assert ready_mocks["c_stopping"].called
        messages = ready_mocks["messages"]()
        assert len(messages) == 0

    def test_updates_states_correctly(self, ready_mocks, capsys):
        assert ready_mocks["state"].experiment_id == "D123-456"
        assert ready_mocks["state"].status == "awaiting_instruments"
        assert ready_mocks["controller_client"].callback == c_ready

        msg = MockMessage(
            topic="controller/event/ready",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_ready(ready_mocks["controller_client"], msg, ready_mocks["state"])

        captured = capsys.readouterr()
        assert "Instruments ready, starting experiment D123-456..." in captured.out
        assert ready_mocks["state"].status == "ready"
        assert ready_mocks["state"].experiment_id == "D123-456"
        assert ready_mocks["controller_client"].callback == ready_mocks["c_running"]
        messages = ready_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/run"
        assert messages[0].payload == '{"experiment_id": "D123-456"}'


class TestRunning:
    @pytest.fixture
    def run_mocks(self, message_bus, mock_state, mqtt_mocks):
        with (
            patch("src.on_controller_message.pub_err") as mock_publish_error,
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
                "pub_err": mock_publish_error,
                "c_stopping": mock_c_stopping,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "messages": get_decoded_bus_messages,
            }

    # ========================================

    def test_incompatible_controller_status(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert state.status == "ready"
        run_mocks["pub_err"].incompatible_controller_status.assert_called_once_with(
            state, msg
        )
        messages = run_mocks["messages"]()
        assert len(messages) == 0

    def test_accepts_stop_signal(self, run_mocks):
        state = run_mocks["state"]
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running

        msg = MockMessage(topic="controller/command/stop", payload="not important")
        c_running(run_mocks["controller_client"], msg, state)

        assert run_mocks["c_stopping"].called
        messages = run_mocks["messages"]()
        assert len(messages) == 0

    def test_sends_end_signal_when_setpoints_empty(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert run_mocks["controller_client"].callback == c_running
        state.setpoints = []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert run_mocks["controller_client"].callback == run_mocks["c_stopping"]
        messages = run_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/end"
        assert messages[0].payload == json.dumps({"experiment_id": "D123-456"})

    def test_updates_state_on_first_setpoint_only(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        # Should update state on first setpoint
        assert state.status == "running"
        assert state.current_setpoint is not None

        # Should not update state on second setpoint
        state.status = "idle"
        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert state.status == "idle"

    def test_saves_past_setpoints(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        assert state.setpoints != []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        # Should not have saved "None" as past setpoint
        assert state.past_setpoints == []
        assert state.current_setpoint is not None
        new_sp = state.current_setpoint

        # Should save current setpoint on next run
        c_running(run_mocks["controller_client"], msg, state)

        assert state.past_setpoints == [new_sp]

    def test_sets_current_setpoint(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        all_setpoints = state.setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert state.current_setpoint == all_setpoints[0]

    def test_drops_current_setpoint_from_list(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        all_setpoints = state.setpoints.copy()
        assert all_setpoints != []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert state.setpoints == all_setpoints[1:]

    def test_sends_setpoint(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        first_sp = state.setpoints[0]
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        messages = run_mocks["messages"]()
        assert len(messages) == 1 + len(instruments)

        for i, column in enumerate(instruments):
            instr_name, var_name = column.split("/", 1)
            assert messages[i].topic == f"instruments/{instr_name}/{var_name}/setpoint"
            assert json.loads(messages[i].payload) == {
                "value": first_sp[column],
            }

    def test_starts_setpoint_timer(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert state.status == "ready"
        assert run_mocks["controller_client"].callback == c_running
        assert state.current_setpoint is None
        first_sp = state.setpoints[0]
        instruments = [k for k in first_sp if k != "duration"]

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        messages = run_mocks["messages"]()
        assert len(messages) == 1 + len(instruments)
        assert messages[-1].topic == "controller/timer/command/start"
        assert json.loads(messages[-1].payload) == {
            "source": "setpoint",
            "experiment_id": "D123-456",
            "duration": first_sp["duration"],
        }

    def test_saves_and_clears_last_setpoint(self, run_mocks):
        state = run_mocks["state"]
        assert state.experiment_id == "D123-456"
        assert run_mocks["controller_client"].callback == c_running
        last_setpoint = state.setpoints[-1].copy()
        state.current_setpoint = last_setpoint.copy()
        state.status = "running"
        state.setpoints = []

        msg = MockMessage(
            topic="controller/command/run",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_running(run_mocks["controller_client"], msg, state)

        assert state.current_setpoint is None
        assert state.past_setpoints == [last_setpoint]


class TestStopping:
    @pytest.fixture
    def stop_mocks(self, message_bus, mock_state, mqtt_mocks, mqtt_validator_mocks):
        with (
            patch("src.on_controller_message.pub_err") as mock_publish_error,
            patch("src.on_controller_message.c_idle") as mock_c_idle,
            patch(
                "src.on_controller_message.dump_database_for_experiment"
            ) as mock_dump,
        ):
            state = mock_state("end")
            mqtt_mocks["client_class"](
                id="controller",
                topics="controller/#",
                callback=c_stopping,
                obj=state,
            )
            mock_c_idle.return_value = None
            mock_c_idle.__name__ = "mock_c_idle"
            mock_dump.return_value = None

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "c_idle": mock_c_idle,
                "state": state,
                "controller_client": mqtt_mocks["client_instance"],
                "validate_message": mqtt_validator_mocks["validate_message"],
                "messages": get_decoded_bus_messages,
                "dump": mock_dump,
            }

    # ========================================

    def test_invalid_message(self, stop_mocks):
        err = MQTTValidationException("Invalid JSON")
        stop_mocks["validate_message"].side_effect = err
        assert stop_mocks["state"].status == "running"
        stop_mocks["controller_client"].callback = c_stopping

        msg = MockMessage(topic="controller/command/stop", payload="not json")
        c_stopping(stop_mocks["controller_client"], msg, stop_mocks["state"])

        stop_mocks["validate_message"].assert_called_once_with(msg.topic, msg.payload)
        assert stop_mocks["state"].status == "running"
        assert stop_mocks["controller_client"].callback == c_stopping
        stop_mocks["pub_err"].message_validation.assert_called_once_with(err)
        messages = stop_mocks["messages"]()
        assert len(messages) == 0

    def test_incompatible_controller_status(self, stop_mocks):
        assert stop_mocks["state"].experiment_id == "D123-456"
        assert stop_mocks["state"].status == "running"
        assert stop_mocks["controller_client"].callback == c_stopping

        msg = MockMessage(
            topic="controller/command/something_else",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_stopping(stop_mocks["controller_client"], msg, stop_mocks["state"])

        assert stop_mocks["state"].status == "running"
        stop_mocks["pub_err"].incompatible_controller_status.assert_called_once_with(
            stop_mocks["state"], msg
        )
        messages = stop_mocks["messages"]()
        assert len(messages) == 0

    def test_checks_uid(self, stop_mocks):
        assert stop_mocks["state"].experiment_id == "D123-456"
        assert stop_mocks["state"].status == "running"
        assert stop_mocks["controller_client"].callback == c_stopping

        msg = MockMessage(
            topic="controller/command/stop",
            payload=json.dumps({"experiment_id": "456"}),
        )
        c_stopping(stop_mocks["controller_client"], msg, stop_mocks["state"])

        assert stop_mocks["state"].status == "running"
        stop_mocks["pub_err"].incompatible_uid.assert_called_once_with(
            stop_mocks["state"], msg, "456", "controller"
        )
        messages = stop_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_end(self, stop_mocks, capsys):
        assert stop_mocks["state"].experiment_id == "D123-456"
        assert stop_mocks["state"].status == "running"
        assert stop_mocks["controller_client"].callback == c_stopping

        msg = MockMessage(
            topic="controller/event/end",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_stopping(stop_mocks["controller_client"], msg, stop_mocks["state"])

        assert stop_mocks["state"]._status_history == ["stopping", "idle"]
        assert stop_mocks["state"].status == "idle"
        stop_mocks["dump"].assert_called_once()
        stop_mocks["state"].reset.assert_called_once()
        assert stop_mocks["controller_client"].callback == stop_mocks["c_idle"]
        messages = stop_mocks["messages"]()
        assert len(messages) == 0
        stop_message = (
            f"Experiment D123-456 finished and the controller has been reset."
        )
        assert stop_message in capsys.readouterr().out

    def test_valid_stop_from_any_callback(self, stop_mocks, capsys):
        assert stop_mocks["state"].experiment_id == "D123-456"
        assert stop_mocks["state"].status == "running"
        stop_mocks["controller_client"].callback = "mock_callback"

        msg = MockMessage(
            topic="controller/command/stop",
            payload=json.dumps({"experiment_id": "D123-456"}),
        )
        c_stopping(stop_mocks["controller_client"], msg, stop_mocks["state"])

        assert stop_mocks["state"]._status_history == ["stopping", "idle"]
        assert stop_mocks["state"].status == "idle"
        stop_mocks["dump"].assert_called_once()
        stop_mocks["state"].reset.assert_called_once()
        messages = stop_mocks["messages"]()
        assert len(messages) == 0
        stop_message = (
            f"Experiment D123-456 was stopped and the controller has been reset."
        )
        assert stop_message in capsys.readouterr().out
