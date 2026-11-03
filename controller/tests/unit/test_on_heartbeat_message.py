import copy
import json

import pytest
from unittest.mock import patch, call

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
)

from src.on_heartbeat_message import (
    on_heartbeat_message,
    handle_instrument_heartbeat,
    handle_spc_heartbeat,
    heartbeat_valid,
    spc_heartbeat_valid,
)
from utils.mqtt_validator import MQTTValidationException

# =============== Fixtures ===============


@pytest.fixture
def state(mock_state):
    return mock_state("awaiting_instruments")


@pytest.fixture
def heartbeat_client(mqtt_mocks):
    mqtt_mocks["client_class"](
        id="heartbeat",
        topics="instruments/+/heartbeat",
        callback=on_heartbeat_message,
    )
    return mqtt_mocks["client_instance"]


# ========================================


class TestOnHeartbeatMessage:
    @pytest.fixture
    def on_heartbeat_message_mocks(self, state, heartbeat_client, mqtt_validator_mocks):
        with (
            patch("src.on_heartbeat_message.pub_err") as mock_publish_error,
            patch(
                "src.on_heartbeat_message.handle_instrument_heartbeat"
            ) as handle_i_hb,
            patch("src.on_heartbeat_message.handle_spc_heartbeat") as handle_spc_hb,
        ):
            yield {
                "pub_err": mock_publish_error,
                "validate_message": mqtt_validator_mocks["validate_message"],
                "handle_i_hb": handle_i_hb,
                "handle_spc_hb": handle_spc_hb,
                "state": state,
                "heartbeat_client": heartbeat_client,
            }

    def test_incompatible_topic(self, on_heartbeat_message_mocks):
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        state = on_heartbeat_message_mocks["state"]

        msg = MockMessage(
            topic="heartbeat/something_else",
            payload=json.dumps({"experiment_id": "123"}),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks[
            "pub_err"
        ].incompatible_topic.assert_called_once_with(state, msg, "heartbeat_callback")
        on_heartbeat_message_mocks["validate_message"].assert_not_called()

    def test_wrong_json(self, on_heartbeat_message_mocks):
        err = MQTTValidationException("Invalid JSON payload...")
        on_heartbeat_message_mocks["validate_message"].side_effect = err
        msg = MockMessage(
            topic="instruments/instrument_1/heartbeat",
            payload="not a json",
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
        on_heartbeat_message_mocks["validate_message"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks[
            "pub_err"
        ].heartbeat_validation_error.assert_called_once_with(msg, err)

    def test_hb_ignored_if_pre_awaiting_instruments(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]

        vm_calls = []
        for pre_state in ["idle", "validating", "starting"]:
            state.status = pre_state

            msg = MockMessage(
                topic="instruments/furnace/heartbeat",
                payload=json.dumps({"state": {"status": "running"}}),
            )
            on_heartbeat_message(heartbeat_client, msg, state)

            on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
            vm_calls.append(call(msg.topic, msg.payload))
            on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
            on_heartbeat_message_mocks[
                "pub_err"
            ].heartbeat_validation_error.assert_not_called()
            on_heartbeat_message_mocks[
                "pub_err"
            ].unconfigured_instrument.assert_not_called()
        assert on_heartbeat_message_mocks["validate_message"].call_args_list == vm_calls

    def test_unconfigured_instrument(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        assert state.experiment_id == "D123-456"
        assert state.status == "awaiting_instruments"
        assert "unconfigured_instrument" not in state.instrument_states

        msg = MockMessage(
            topic="instruments/unconfigured_instrument/heartbeat",
            payload=json.dumps(
                {
                    "state": {"status": "running"},
                    "setpoints": {},
                    "config": {"tolerance": 1, "experiment_id": None},
                }
            ),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
        on_heartbeat_message_mocks["validate_message"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks[
            "pub_err"
        ].heartbeat_validation_error.assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
        on_heartbeat_message_mocks[
            "pub_err"
        ].unconfigured_instrument.assert_called_once_with(
            msg, "unconfigured_instrument"
        )

    def test_configured_instrument(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        assert state.experiment_id == "D123-456"
        assert state.status == "awaiting_instruments"
        assert "furnace" in state.instrument_states

        msg_payload = {
            "state": {"status": "running"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        msg = MockMessage(
            topic="instruments/furnace/heartbeat",
            payload=json.dumps(msg_payload),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
        on_heartbeat_message_mocks["validate_message"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks[
            "pub_err"
        ].heartbeat_validation_error.assert_not_called()
        on_heartbeat_message_mocks[
            "pub_err"
        ].unconfigured_instrument.assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_called_once_with(
            state, msg_payload, "furnace"
        )


    def test_unconfigured_spc(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        assert "unconfigured_spc" not in state.spc_states

        msg = MockMessage(
            topic="setpoint_controllers/unconfigured_spc/heartbeat",
            payload=json.dumps({"config": {"pid": {}}}),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
        on_heartbeat_message_mocks["handle_spc_hb"].assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
        on_heartbeat_message_mocks["pub_err"].unconfigured_spc.assert_called_once_with(
            msg, "unconfigured_spc"
        )

    def test_configured_spc(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        spc_id = "pressure-pressure--mass_flow-mass_flow"
        assert spc_id in state.spc_states

        msg_payload = {"config": {"pid": {"k_p": 10.0}}}
        msg = MockMessage(
            topic=f"setpoint_controllers/{spc_id}/heartbeat",
            payload=json.dumps(msg_payload),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_not_called()
        on_heartbeat_message_mocks["pub_err"].unconfigured_spc.assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
        on_heartbeat_message_mocks["handle_spc_hb"].assert_called_once_with(
            state, msg_payload, spc_id
        )

    def test_incompatible_spc_topic(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]

        msg = MockMessage(
            topic="setpoint_controllers/some_spc/configure",
            payload=json.dumps({"pid": {}}),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["pub_err"].incompatible_topic.assert_called_once()
        on_heartbeat_message_mocks["validate_message"].assert_not_called()
        on_heartbeat_message_mocks["handle_spc_hb"].assert_not_called()


class TestHandleInstrumentHeartbeat:
    @pytest.fixture
    def handle_i_hb_mocks(self, state, message_bus):
        with (
            patch("src.on_heartbeat_message.heartbeat_valid") as hb_valid,
            patch("src.on_heartbeat_message.t.time") as time_mock,
        ):
            time_mock.return_value = 1234.56

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "hb_valid": hb_valid,
                "time_mock": time_mock,
                "state": state,
                "messages": get_decoded_bus_messages,
            }

    def test_invalid_heartbeat(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = False
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instrument_states["furnace"]["state"] is None

        heartbeat = "nonsense"
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] == 1234.56
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        assert state.instrument_states["furnace"]["state"] is None
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_not_awaiting_instruments(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        state.status = "starting"
        for instrument in state.instrument_states.values():
            instrument["state"] = {"status": "running"}
        state.instrument_states["furnace"]["state"] = None
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": {"status": "running"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] == 1234.56
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == {"status": "running"}
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        # Because not in awaiting_instruments, should not set instruments_ready
        assert state.instruments_ready == False
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_instrument_awaiting_experiment(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        assert len(state.instrument_states) > 1
        for instrument in state.instrument_states.values():
            instrument["state"] = None
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": {"status": "awaiting_experiment"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] is not None
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == {
            "status": "awaiting_experiment"
        }
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        # Because it is idle, should not set instruments_ready
        assert state.instruments_ready == False
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_awaiting_not_all_ready(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        assert len(state.instrument_states) > 1
        for instrument in state.instrument_states.values():
            instrument["state"] = None
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": {"status": "running"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] is not None
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == {"status": "running"}
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        # Because not all instruments are running, should not set instruments_ready
        assert state.instruments_ready == False
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_awaiting_all_ready(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        assert len(state.instrument_states) > 1
        for instrument in state.instrument_states.values():
            instrument["state"] = {"status": "running"}
        state.instrument_states["furnace"]["state"] = None
        assert state.instrument_states["furnace"]["last_contact"] is None
        for spc in state.spc_states.values():
            spc["config"] = {"pid": {}}
        assert state.instruments_ready == False

        heartbeat = {
            "state": {"status": "running"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] is not None
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == {"status": "running"}
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        assert state.instruments_ready == True
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/ready"
        assert json.loads(messages[0].payload)["experiment_id"] == "D123-456"


    def test_valid_heartbeat_awaiting_spc_not_ready(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        for instrument in state.instrument_states.values():
            instrument["state"] = {"status": "running"}
        assert all(spc["config"] is None for spc in state.spc_states.values())

        heartbeat = {
            "state": {"status": "running"},
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        # All instruments are running, but the setpoint controller has not reported
        assert state.instruments_ready == False
        assert handle_i_hb_mocks["messages"]() == []


class TestHeartbeatValid:
    @pytest.fixture
    def hb_valid_mocks(self, state, message_bus):
        with patch("src.on_heartbeat_message.pub_err") as mock_publish_error:

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "state": state,
                "expected_hb_config": state.config.get_expected_heartbeat("_"),
                "messages": get_decoded_bus_messages,
            }

    def test_valid_heartbeat(self, hb_valid_mocks):
        state = hb_valid_mocks["state"]
        heartbeat = {"config": hb_valid_mocks["expected_hb_config"]}
        res = heartbeat_valid(state, heartbeat, "furnace")
        assert res == True
        messages = hb_valid_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_heartbeat_settling_does_not_raise(self, hb_valid_mocks, capsys):
        state = hb_valid_mocks["state"]
        state.status = "awaiting_instruments"
        state.get_expected_heartbeat("furnace")["experiment"] = {
            "experiment_id": "D123-456",
            "temperature": {"offset": 273},
        }
        heartbeat = {"config": copy.deepcopy(hb_valid_mocks["expected_hb_config"])}
        heartbeat["config"]["experiment"] = {
            "experiment_id": "X456-789",
        }

        res = heartbeat_valid(state, heartbeat, "furnace")

        assert res == False
        captured = capsys.readouterr()
        assert captured.out == ""
        messages = hb_valid_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_heartbeat_not_settling_raises(self, hb_valid_mocks, capsys):
        state = hb_valid_mocks["state"]
        state.status = "running"
        heartbeat = {"config": {"some": "nonsense"}}

        res = heartbeat_valid(state, heartbeat, "furnace")

        assert res == False
        hb_valid_mocks["pub_err"].invalid_instrument_config.assert_called_once_with(
            "furnace",
            hb_valid_mocks["expected_hb_config"],
            heartbeat["config"],
        )
        captured = capsys.readouterr()
        assert "Stopping experiment..." in captured.out
        messages = hb_valid_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert json.loads(messages[0].payload)["experiment_id"] == "D123-456"


class TestHandleSpcHeartbeat:
    SPC_ID = "pressure-pressure--mass_flow-mass_flow"

    @pytest.fixture
    def handle_spc_hb_mocks(self, state, message_bus):
        with (
            patch("src.on_heartbeat_message.spc_heartbeat_valid") as hb_valid,
            patch("src.on_heartbeat_message.t.time") as time_mock,
        ):
            time_mock.return_value = 1234.56

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "hb_valid": hb_valid,
                "state": state,
                "messages": get_decoded_bus_messages,
            }

    def test_invalid_heartbeat(self, handle_spc_hb_mocks):
        state = handle_spc_hb_mocks["state"]
        handle_spc_hb_mocks["hb_valid"].return_value = False
        heartbeat = {"config": {"pid": {"k_p": 0.0}}}

        handle_spc_heartbeat(state, heartbeat, self.SPC_ID)

        assert state.spc_states[self.SPC_ID]["last_contact"] == 1234.56
        handle_spc_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, self.SPC_ID
        )
        assert state.spc_states[self.SPC_ID]["config"] is None
        assert handle_spc_hb_mocks["messages"]() == []

    def test_valid_heartbeat_awaiting_instruments_not_ready(self, handle_spc_hb_mocks):
        state = handle_spc_hb_mocks["state"]
        handle_spc_hb_mocks["hb_valid"].return_value = True
        heartbeat = {"config": {"pid": {"k_p": 10.0}}}

        handle_spc_heartbeat(state, heartbeat, self.SPC_ID)

        assert state.spc_states[self.SPC_ID]["config"] == heartbeat["config"]
        # Instruments have not reported running yet
        assert state.instruments_ready == False
        assert handle_spc_hb_mocks["messages"]() == []

    def test_valid_heartbeat_awaiting_all_ready(self, handle_spc_hb_mocks):
        state = handle_spc_hb_mocks["state"]
        handle_spc_hb_mocks["hb_valid"].return_value = True
        for instrument in state.instrument_states.values():
            instrument["state"] = {"status": "running"}
        heartbeat = {"config": {"pid": {"k_p": 10.0}}}

        handle_spc_heartbeat(state, heartbeat, self.SPC_ID)

        assert state.instruments_ready == True
        messages = handle_spc_hb_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/ready"
        assert json.loads(messages[0].payload)["experiment_id"] == "D123-456"

    def test_valid_heartbeat_not_awaiting_instruments(self, handle_spc_hb_mocks):
        state = handle_spc_hb_mocks["state"]
        state.status = "running"
        handle_spc_hb_mocks["hb_valid"].return_value = True
        for instrument in state.instrument_states.values():
            instrument["state"] = {"status": "running"}
        heartbeat = {"config": {"pid": {"k_p": 10.0}}}

        handle_spc_heartbeat(state, heartbeat, self.SPC_ID)

        assert state.spc_states[self.SPC_ID]["config"] == heartbeat["config"]
        assert state.instruments_ready == False
        assert handle_spc_hb_mocks["messages"]() == []


class TestSpcHeartbeatValid:
    SPC_ID = "pressure-pressure--mass_flow-mass_flow"

    @pytest.fixture
    def spc_hb_valid_mocks(self, state, message_bus):
        with patch("src.on_heartbeat_message.pub_err") as mock_publish_error:

            def get_decoded_bus_messages(topic=None):
                return message_bus.get_messages(topic=topic, decoded=True)

            yield {
                "pub_err": mock_publish_error,
                "state": state,
                "expected_pid": state.get_expected_spc_config(self.SPC_ID)["pid"],
                "messages": get_decoded_bus_messages,
            }

    def test_valid_heartbeat(self, spc_hb_valid_mocks):
        state = spc_hb_valid_mocks["state"]
        state.status = "running"
        # Parameters not in the live config (e.g. max) are not checked
        heartbeat = {
            "config": {"pid": {**spc_hb_valid_mocks["expected_pid"], "max": 42.0}}
        }

        res = spc_heartbeat_valid(state, heartbeat, self.SPC_ID)

        assert res == True
        spc_hb_valid_mocks["pub_err"].invalid_spc_config.assert_not_called()
        assert spc_hb_valid_mocks["messages"]() == []

    def test_invalid_heartbeat_settling_does_not_raise(
        self, spc_hb_valid_mocks, capsys
    ):
        state = spc_hb_valid_mocks["state"]
        assert state.status == "awaiting_instruments"
        heartbeat = {
            "config": {"pid": {**spc_hb_valid_mocks["expected_pid"], "k_p": 1.0}}
        }

        res = spc_heartbeat_valid(state, heartbeat, self.SPC_ID)

        assert res == False
        spc_hb_valid_mocks["pub_err"].invalid_spc_config.assert_not_called()
        assert capsys.readouterr().out == ""
        assert spc_hb_valid_mocks["messages"]() == []

    def test_invalid_heartbeat_not_settling_raises(self, spc_hb_valid_mocks, capsys):
        state = spc_hb_valid_mocks["state"]
        state.status = "running"
        expected_pid = spc_hb_valid_mocks["expected_pid"]
        heartbeat = {"config": {"pid": {**expected_pid, "k_p": 1.0}}}

        res = spc_heartbeat_valid(state, heartbeat, self.SPC_ID)

        assert res == False
        spc_hb_valid_mocks["pub_err"].invalid_spc_config.assert_called_once_with(
            self.SPC_ID, expected_pid, {**expected_pid, "k_p": 1.0}
        )
        assert "Stopping experiment..." in capsys.readouterr().out
        messages = spc_hb_valid_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/command/stop"
        assert json.loads(messages[0].payload)["experiment_id"] == "D123-456"
