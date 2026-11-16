from unittest.mock import patch, MagicMock
import pytest

from utils.mqtt_clients import MQTTMessageError

import json

from tests.conftest import (
    MockMessage,
    firmware_env,
    mock_load_config,
    expected_config,
)

import src.state as state


class TestInstrumentState:
    @pytest.fixture
    def is_mocks(self, firmware_env, mqtt_mocks):
        with (
            patch("src.state.mqtt_val") as mock_mqtt_val,
            patch("src.state.inst.create_instrument") as mock_create_instrument,
        ):
            mock_mqtt_val.validate_message.side_effect = (
                lambda topic, payload: json.loads(payload)
            )
            setpoints = {"pressure": 2.5, "temperature": 125.0}
            instrument_instance = MagicMock()
            instrument_instance.setpoints = setpoints
            instrument_instance.config = mock_load_config(firmware_env)
            mock_create_instrument.return_value = instrument_instance
            instrument_instance.print_config.return_value = {"some": "config"}
            yield {
                "config": mock_load_config(firmware_env),
                "client_class": mqtt_mocks["client_class"],
                "client": mqtt_mocks["client_instance"],
                "publisher": mqtt_mocks["publisher_instance"],
                "mqtt_val": mock_mqtt_val,
                "create_instrument": mock_create_instrument,
                "instrument": instrument_instance,
                "setpoints": setpoints,
                "printed_config": instrument_instance.print_config.return_value,
            }

    def test_init(self, is_mocks):
        mock_config = is_mocks["config"]

        istate = state.InstrumentState(mock_config)

        name = mock_config["INSTRUMENT_NAME"]
        expected_topics = [
            "controller/command/start",
            f"instruments/{name}/configure",
            f"instruments/{name}/+/setpoint",
            "controller/event/end",
            "controller/command/stop",
        ]
        is_mocks["client_class"].assert_called_once()
        assert is_mocks["client_class"].call_args[1]["id"] == name
        assert is_mocks["client_class"].call_args[1]["topics"] == expected_topics
        assert istate._client == is_mocks["client"](name)
        is_mocks["create_instrument"].assert_called_once_with(mock_config)
        assert istate._instrument == is_mocks["instrument"]
        assert istate.status == "initialising"

    def test_slots_are_protected(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        with pytest.raises(AttributeError):
            istate.something = None

    def test_can_get_client(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        assert istate.client == istate._client

    def test_cannot_set_client(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        with pytest.raises(AttributeError):
            istate.client = None

    def test_can_get_instrument(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        assert istate.instrument == istate._instrument

    def test_cannot_set_instrument(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        with pytest.raises(AttributeError):
            istate.instrument = None

    def test_can_get_status(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        assert istate.status == istate._status

    def test_cannot_set_status_to_invalid_value(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        assert istate._status == "initialising"
        assert istate.client.callback == istate.initialising_cb

        with pytest.raises(ValueError) as e:
            istate.status = "jumping"

        assert str(e.value) == "Invalid status: jumping"
        assert istate._status == "initialising"
        assert istate.client.callback == istate.initialising_cb

    def test_can_set_status_and_updates_callback(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        assert istate._status == "initialising"
        assert istate.client.callback == istate.initialising_cb

        istate.status = "awaiting_experiment"
        assert istate._status == "awaiting_experiment"
        assert istate.client.callback == istate.awaiting_experiment_cb

        istate.status = "running"
        assert istate._status == "running"
        assert istate.client.callback == istate.running_cb

        istate.status = "error"
        assert istate._status == "error"
        assert istate.client.callback == istate.error_cb

        istate.status = "safe_stop"
        assert istate._status == "safe_stop"
        assert istate.client.callback == istate.safe_stop_cb

    @pytest.mark.parametrize("new_status", state.InstrumentState.allowed_status)
    def test_cannot_set_status_during_safe_stop(self, is_mocks, capsys, new_status):
        istate = state.InstrumentState(is_mocks["config"])
        istate.status = "safe_stop"

        istate.status = new_status

        assert istate._status == "safe_stop"
        assert istate.client.callback == istate.safe_stop_cb
        captured = capsys.readouterr()
        assert (
            f"WARNING: Cannot update status from 'safe_stop' to '{new_status}'."
            in captured.out
        )

    def test_publish_heartbeat(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "running"
        is_mocks["instrument"].config["ACTIVE_VARIABLES"] = ["temperature", "pressure"]
        # Pressure not measured yet, and an external sensor saved while simulating
        is_mocks["instrument"].previous_measurements = {
            "temperature": 120.5,
            "mass_flow/mass_flow": 3.0,
        }

        istate.publish_heartbeat()

        expected_topic = f"instruments/{mock_config['INSTRUMENT_NAME']}/heartbeat"
        expected_payload = {
            "state": {
                "status": "running",
                "measurements": {"temperature": 120.5, "pressure": None},
            },
            "setpoints": is_mocks["setpoints"],
            "config": is_mocks["printed_config"],
        }
        is_mocks["publisher"].publish.assert_called_once_with(
            expected_topic, json.dumps(expected_payload)
        )

    def test_publish_heartbeat_does_not_raise_if_it_fails(self, is_mocks, capsys):
        istate = state.InstrumentState(is_mocks["config"])
        is_mocks["instrument"].previous_measurements = {}
        is_mocks["publisher"].publish.side_effect = MQTTMessageError("not connected")

        istate.publish_heartbeat()

        is_mocks["publisher"].publish.assert_called_once()
        captured = capsys.readouterr()
        assert "WARNING: Could not publish heartbeat: not connected" in captured.out

    def test_initialising_cb(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)

        mock_msg = MockMessage(topic="some/topic", payload=json.dumps({"some": "data"}))
        istate.initialising_cb(istate.client, mock_msg)

        is_mocks["client"].publish.assert_not_called()
        captured = capsys.readouterr()
        assert (
            "WARNING: Received some/topic while instrument is initialising. Ignoring..."
            in captured.out
        )
        assert istate.status == "initialising"

    def test_awaiting_experiment_incompatible_topic(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "awaiting_experiment"

        mock_msg = MockMessage(
            topic="some/other/topic", payload=json.dumps({"some": "data"})
        )
        istate.awaiting_experiment_cb(istate.client, mock_msg)

        is_mocks["mqtt_val"].validate_message.assert_called_once()
        is_mocks["client"].publish.assert_not_called()
        captured = capsys.readouterr()
        assert (
            "WARNING: Received some/other/topic while instrument is awaiting experiment. Ignoring..."
            in captured.out
        )
        assert istate.status == "awaiting_experiment"

    def test_awaiting_experiment_configure(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "awaiting_experiment"
        istate.instrument.config["experiment"] = {"some": "info"}

        mock_msg = MockMessage(
            topic=f"instruments/{mock_config['INSTRUMENT_NAME']}/configure",
            payload=json.dumps({"some_other": "data"}),
        )
        istate.awaiting_experiment_cb(istate.client, mock_msg)

        is_mocks["mqtt_val"].validate_message.assert_called_once()
        is_mocks["mqtt_val"].validate_message.assert_called_once()
        assert istate.instrument.config["experiment"] == {
            "some": "info",
            "some_other": "data",
        }
        assert istate.status == "awaiting_experiment"

    def test_awaiting_experiment_start_missing_id(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "awaiting_experiment"

        mock_msg = MockMessage(topic="controller/command/start", payload=json.dumps({}))
        istate.awaiting_experiment_cb(istate.client, mock_msg)

        is_mocks["mqtt_val"].validate_message.assert_called_once()
        assert istate.instrument.config["experiment"]["experiment_id"] is None
        assert istate.status == "awaiting_experiment"  # Status should remain unchanged
        assert istate.client.callback == istate.awaiting_experiment_cb
        captured = capsys.readouterr()
        assert (
            "WARNING: Received controller/command/start without an experiment id. Ignoring..."
            in captured.out
        )

    def test_awaiting_experiment_start_ok(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "awaiting_experiment"

        mock_msg = MockMessage(
            topic="controller/command/start",
            payload=json.dumps({"experiment_id": "e-123"}),
        )
        istate.awaiting_experiment_cb(istate.client, mock_msg)

        is_mocks["mqtt_val"].validate_message.assert_called_once()
        assert istate.instrument.config["experiment"]["experiment_id"] == "e-123"
        assert istate.status == "running"
        assert istate.client.callback == istate.running_cb

    def test_awaiting_experiment_setpoint(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "awaiting_experiment"

        with patch.object(state.InstrumentState, "running_cb") as mock_running_cb:
            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"some": "setpoint"}),
            )
            istate.awaiting_experiment_cb(istate.client, mock_msg)

        is_mocks["mqtt_val"].validate_message.assert_called_once()
        is_mocks["client"].publish.assert_not_called()
        captured = capsys.readouterr()
        assert "WARNING:" not in captured.out
        mock_running_cb.assert_called_once_with(istate.client, mock_msg, None)
        assert istate.status == "awaiting_experiment"

    def test_running_cb_incompatible_topic(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="some/other/topic", payload=json.dumps({"some": "data"})
            )
            istate.running_cb(istate.client, mock_msg)

            mock_reset.assert_not_called()
            is_mocks["mqtt_val"].validate_message.assert_not_called()
            is_mocks["client"].publish.assert_not_called()
            captured = capsys.readouterr()
            assert (
                "WARNING: Received some/other/topic while instrument is running. Ignoring..."
                in captured.out
            )
            assert istate.status == "running"

    def test_running_cb_end(self, is_mocks):
        mock_config = is_mocks["config"]
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(topic="controller/event/end", payload=json.dumps({}))
            istate.running_cb(istate.client, mock_msg)

            mock_reset.assert_called_once()
            is_mocks["mqtt_val"].validate_message.assert_not_called()

    def test_running_cb_stop(self, is_mocks):
        mock_config = is_mocks["config"]
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="controller/command/stop", payload=json.dumps({})
            )
            istate.running_cb(istate.client, mock_msg)

            mock_reset.assert_called_once()
            is_mocks["mqtt_val"].validate_message.assert_not_called()

    def test_running_cb_setpoint_invalid(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"some": "nonsense"}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            captured = capsys.readouterr()
            assert "WARNING: Invalid setpoint received: None" in captured.out
            mock_reset.assert_not_called()

    def test_running_cb_setpoint_non_numeric(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"value": "nonsense"}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            captured = capsys.readouterr()
            assert "WARNING: Invalid setpoint received: nonsense" in captured.out
            mock_reset.assert_not_called()

    def test_running_cb_setpoint_ok(self, is_mocks):
        mock_config = is_mocks["config"]
        mock_set_and_go = is_mocks["instrument"].set_and_go_to_setpoint
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"value": 42}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            mock_set_and_go.assert_called_once_with("var", 42)
            mock_reset.assert_not_called()

    def test_running_cb_setpoint_raises(self, is_mocks, capsys):
        mock_config = is_mocks["config"]
        mock_set_and_go = is_mocks["instrument"].set_and_go_to_setpoint
        mock_set_and_go.side_effect = ValueError("Some error")
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.status = "running"

            mock_msg = MockMessage(
                topic="instruments/inst/my_var/setpoint",
                payload=json.dumps({"value": 42}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            mock_set_and_go.assert_called_once_with("my_var", 42)
            captured = capsys.readouterr()
            assert (
                "ERROR: Failed to set the setpoint for my_var: Some error"
                in captured.out
            )
            assert istate.status == "error"
            assert istate.client.callback == istate.error_cb
            mock_reset.assert_not_called()

    def test_running_cb_can_move_from_error_to_running(self, is_mocks):
        mock_config = is_mocks["config"]
        mock_set_and_go = is_mocks["instrument"].set_and_go_to_setpoint
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate.instrument.config["experiment"]["experiment_id"] = "e-123"
            istate._can_measure = True
            istate._can_set_setpoint = False
            istate.status = "error"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"value": 42}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            mock_set_and_go.assert_called_once_with("var", 42)
            assert istate._can_set_setpoint == True
            assert istate.status == "running"
            mock_reset.assert_not_called()

    def test_running_cb_can_move_from_error_to_awaiting_experiment(self, is_mocks):
        mock_config = is_mocks["config"]
        mock_set_and_go = is_mocks["instrument"].set_and_go_to_setpoint
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate._can_measure = True
            istate._can_set_setpoint = False
            istate.status = "error"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"value": 42}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            mock_set_and_go.assert_called_once_with("var", 42)
            assert istate._can_set_setpoint == True
            assert istate.status == "awaiting_experiment"
            mock_reset.assert_not_called()

    def test_running_cb_only_move_off_error_state_if_can_measure(self, is_mocks):
        mock_config = is_mocks["config"]
        mock_set_and_go = is_mocks["instrument"].set_and_go_to_setpoint
        with patch.object(state.InstrumentState, "reset") as mock_reset:
            istate = state.InstrumentState(mock_config)
            istate._can_measure = False
            istate._can_set_setpoint = False
            istate.status = "error"

            mock_msg = MockMessage(
                topic="instruments/inst/var/setpoint",
                payload=json.dumps({"value": 42}),
            )
            istate.running_cb(istate.client, mock_msg)

            is_mocks["mqtt_val"].validate_message.assert_called_once()
            mock_set_and_go.assert_called_once_with("var", 42)
            assert istate._can_set_setpoint == True
            assert istate.status == "error"
            mock_reset.assert_not_called()

    def test_running_cb_ignores_setpoint_after_safe_stop(self, is_mocks, capsys):
        # The watchdog may safe stop the instrument while a setpoint message is being handled
        istate = state.InstrumentState(is_mocks["config"])
        istate._status = "safe_stop"
        msg = MockMessage(
            topic="instruments/test_instrument/temperature/setpoint",
            payload=json.dumps({"value": 40}),
        )

        istate.running_cb(istate.client, msg)

        is_mocks["instrument"].set_and_go_to_setpoint.assert_not_called()
        captured = capsys.readouterr()
        assert (
            "WARNING: Ignoring setpoint for temperature during safe stop."
            in captured.out
        )

    def test_reset(self, is_mocks):
        mock_config = is_mocks["config"]
        istate = state.InstrumentState(mock_config)
        istate.status = "running"
        istate.instrument.config["experiment"]["experiment_id"] = "e-123"

        istate.reset()

        for variable, setpoint in mock_config["DEFAULT_SETPOINTS"].items():
            is_mocks["instrument"].set_and_go_to_setpoint.assert_any_call(
                variable, setpoint
            )
        assert istate.instrument.config["experiment"]["experiment_id"] is None
        assert istate.status == "awaiting_experiment"
        assert istate.client.callback == istate.awaiting_experiment_cb

    def test_reset_leaves_safe_stop(self, is_mocks):
        istate = state.InstrumentState(is_mocks["config"])
        istate.status = "safe_stop"
        assert istate._status == "safe_stop"
        assert istate.client.callback == istate.safe_stop_cb

        istate.reset()

        assert istate._status == "awaiting_experiment"
        assert istate.client.callback == istate.awaiting_experiment_cb

    def test_error_cb_awaiting_experiment(self, is_mocks):
        mock_config = is_mocks["config"]
        with (
            patch.object(state.InstrumentState, "awaiting_experiment_cb") as mock_awe,
            patch.object(state.InstrumentState, "running_cb") as mock_run,
        ):
            istate = state.InstrumentState(mock_config)
            istate.status = "error"

            mock_msg = MockMessage(
                topic="some/topic", payload=json.dumps({"some": "data"})
            )
            istate.error_cb(istate.client, mock_msg)

            mock_awe.assert_called_once()
            mock_run.assert_not_called()
            assert istate.status == "error"

    def test_error_cb_running(self, is_mocks):
        mock_config = is_mocks["config"]
        with (
            patch.object(state.InstrumentState, "awaiting_experiment_cb") as mock_awe,
            patch.object(state.InstrumentState, "running_cb") as mock_run,
        ):
            istate = state.InstrumentState(mock_config)
            istate.instrument.config["experiment"]["experiment_id"] = "e-123"
            istate.status = "error"

            mock_msg = MockMessage(
                topic="some/topic", payload=json.dumps({"some": "data"})
            )
            istate.error_cb(istate.client, mock_msg)

            mock_awe.assert_not_called()
            mock_run.assert_called_once()
            assert istate.status == "error"

    def test_safe_stop(self, is_mocks, message_bus, capsys):
        istate = state.InstrumentState(is_mocks["config"])
        istate.status = "running"
        istate.instrument.config["experiment"]["experiment_id"] = "e-123"
        # The status is set first, so setpoints being handled meanwhile are ignored
        status_when_setting = []
        is_mocks["instrument"].set_and_go_to_setpoint.side_effect = (
            lambda variable, setpoint: status_when_setting.append(istate.status)
        )

        istate.safe_stop("Some reason.")

        is_mocks["instrument"].set_and_go_to_setpoint.assert_called_once_with(
            "temperature", 0
        )
        assert status_when_setting == ["safe_stop"]
        assert istate.instrument.config["experiment"]["experiment_id"] is None
        assert istate.status == "safe_stop"
        message = "[test_instrument] Safe stop triggered: Some reason."
        captured = capsys.readouterr()
        assert f"ERROR: {message}" in captured.out
        assert "Safe stop setpoint for temperature applied: 0" in captured.out

        messages = message_bus.get_messages("error/instrument", decoded=True)
        assert len(messages) == 1
        assert json.loads(messages[0].payload) == {
            "code": "safe_stop",
            "message": message,
        }

    def test_safe_stop_does_not_raise_if_publishing_fails(self, is_mocks, capsys):
        istate = state.InstrumentState(is_mocks["config"])
        is_mocks["publisher"].publish.side_effect = MQTTMessageError("not connected")
        capsys.readouterr()  # Creating the exception prints it: only check what is printed after

        istate.safe_stop("Some reason.")

        is_mocks["instrument"].set_and_go_to_setpoint.assert_called_once_with(
            "temperature", 0
        )
        assert istate.status == "safe_stop"
        captured = capsys.readouterr()
        assert (
            "ERROR: [test_instrument] Safe stop triggered: Some reason." in captured.out
        )
        assert "Safe stop setpoint for temperature applied: 0" in captured.out
        assert "WARNING: Could not publish safe stop: not connected" in captured.out

    def test_safe_stop_continues_if_a_setpoint_fails(self, is_mocks, capsys):
        istate = state.InstrumentState(is_mocks["config"])
        istate.instrument.config["SAFE_STOP_SETPOINTS"] = {
            "temperature": 0,
            "pressure": 1,
        }
        is_mocks["instrument"].set_and_go_to_setpoint.side_effect = [
            RuntimeError("instrument unreachable"),
            None,
        ]

        istate.safe_stop("Some reason.")

        assert is_mocks["instrument"].set_and_go_to_setpoint.call_count == 2
        assert istate.status == "safe_stop"
        captured = capsys.readouterr()
        assert (
            "ERROR: Failed to set the safe stop setpoint for temperature: instrument unreachable"
        ) in captured.out
        assert ("Safe stop setpoint for pressure applied: 1") in captured.out

    def test_safe_stop_cb_ignores_messages(self, is_mocks, capsys):
        istate = state.InstrumentState(is_mocks["config"])
        istate.status = "safe_stop"
        msg = MockMessage(
            topic="instruments/test_instrument/temperature/setpoint",
            payload=json.dumps({"value": 40}),
        )

        istate.safe_stop_cb(istate.client, msg)

        is_mocks["instrument"].set_and_go_to_setpoint.assert_not_called()
        assert istate.status == "safe_stop"
        captured = capsys.readouterr()
        assert (
            f"WARNING: Received {msg.topic} during safe stop. Ignoring..."
            in captured.out
        )
