import json

import pytest
from unittest.mock import patch, call

from tests.conftest import (
    MockMessage,
    message_bus,
    mqtt_mocks,
    mock_state,
    mock_experiment_dict,
    mock_setpoints,
)

from src.on_heartbeat_message import (
    on_heartbeat_message,
    handle_instrument_heartbeat,
    heartbeat_valid,
    MQTTValidationException,
)

# =============== Fixtures ===============


@pytest.fixture
def state(mock_state, mock_experiment_dict, mock_setpoints):
    return mock_state("awaiting_instruments", mock_experiment_dict, mock_setpoints)


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
    def on_heartbeat_message_mocks(self, state, heartbeat_client):
        with (
            patch("src.on_heartbeat_message.incompatible_topic") as inc_topic,
            patch("src.on_heartbeat_message.validate_message") as validate_msg,
            patch("src.on_heartbeat_message.heartbeat_validation_error") as hb_val_err,
            patch(
                "src.on_heartbeat_message.handle_instrument_heartbeat"
            ) as handle_i_hb,
            patch("src.on_heartbeat_message.unconfigured_instrument") as unconfigured_i,
        ):
            yield {
                "inc_topic": inc_topic,
                "validate_msg": validate_msg,
                "hb_val_err": hb_val_err,
                "handle_i_hb": handle_i_hb,
                "unconfigured_i": unconfigured_i,
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

        on_heartbeat_message_mocks["inc_topic"].assert_called_once_with(
            state, msg, "heartbeat_callback"
        )
        on_heartbeat_message_mocks["validate_msg"].assert_not_called()

    def test_wrong_json(self, on_heartbeat_message_mocks):
        err = MQTTValidationException("Invalid JSON payload...")
        on_heartbeat_message_mocks["validate_msg"].side_effect = err
        msg = MockMessage(
            topic="instruments/instrument_1/heartbeat",
            payload="not a json",
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["inc_topic"].assert_not_called()
        on_heartbeat_message_mocks["validate_msg"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks["hb_val_err"].assert_called_once_with(msg, err)

    def test_hb_ignored_if_pre_awaiting_instruments(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]

        vm_calls = []
        for pre_state in ["idle", "validating", "starting"]:
            state.status = pre_state

            msg = MockMessage(
                topic="instruments/furnace/heartbeat",
                payload=json.dumps({"state": "ready"}),
            )
            on_heartbeat_message(heartbeat_client, msg, state)

            on_heartbeat_message_mocks["inc_topic"].assert_not_called()
            vm_calls.append(call(msg.topic, msg.payload))
            on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
            on_heartbeat_message_mocks["hb_val_err"].assert_not_called()
            on_heartbeat_message_mocks["unconfigured_i"].assert_not_called()
        assert on_heartbeat_message_mocks["validate_msg"].call_args_list == vm_calls

    def test_unconfigured_instrument(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_instruments"
        assert "unconfigured_instrument" not in state.instrument_states

        msg = MockMessage(
            topic="instruments/unconfigured_instrument/heartbeat",
            payload=json.dumps(
                {
                    "state": "ready",
                    "setpoints": {},
                    "config": {"tolerance": 1, "experiment_id": None},
                }
            ),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["inc_topic"].assert_not_called()
        on_heartbeat_message_mocks["validate_msg"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks["hb_val_err"].assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_not_called()
        on_heartbeat_message_mocks["unconfigured_i"].assert_called_once_with(
            msg, "unconfigured_instrument"
        )

    def test_configured_instrument(self, on_heartbeat_message_mocks):
        state = on_heartbeat_message_mocks["state"]
        heartbeat_client = on_heartbeat_message_mocks["heartbeat_client"]
        assert state.experiment_uid == "123"
        assert state.status == "awaiting_instruments"
        assert "furnace" in state.instrument_states

        msg_payload = {
            "state": "ready",
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        msg = MockMessage(
            topic="instruments/furnace/heartbeat",
            payload=json.dumps(msg_payload),
        )
        on_heartbeat_message(heartbeat_client, msg, state)

        on_heartbeat_message_mocks["inc_topic"].assert_not_called()
        on_heartbeat_message_mocks["validate_msg"].assert_called_once_with(
            msg.topic, msg.payload
        )
        on_heartbeat_message_mocks["hb_val_err"].assert_not_called()
        on_heartbeat_message_mocks["unconfigured_i"].assert_not_called()
        on_heartbeat_message_mocks["handle_i_hb"].assert_called_once_with(
            state, msg_payload, "furnace"
        )


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
            instrument["state"] = "ready"
        state.instrument_states["furnace"]["state"] = None
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": "ready",
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] == 1234.56
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == "ready"
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        # Because not in awaiting_instruments, should not set instruments_ready
        assert state.instruments_ready == False
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_awaiting_not_all_ready(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        assert len(state.instrument_states) > 1
        for instrument in state.instrument_states.values():
            instrument["state"] = "None"
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": "ready",
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] is not None
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == "ready"
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        # Because not all instruments are ready, should not set instruments_ready
        assert state.instruments_ready == False
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 0

    def test_valid_heartbeat_awaiting_not_all_ready(self, handle_i_hb_mocks):
        state = handle_i_hb_mocks["state"]
        handle_i_hb_mocks["hb_valid"].return_value = True
        assert len(state.instrument_states) > 1
        for instrument in state.instrument_states.values():
            instrument["state"] = "ready"
        state.instrument_states["furnace"]["state"] = "None"
        assert state.instrument_states["furnace"]["last_contact"] is None
        assert state.instruments_ready == False

        heartbeat = {
            "state": "ready",
            "setpoints": {},
            "config": {"tolerance": 1, "experiment_id": None},
        }
        handle_instrument_heartbeat(state, heartbeat, "furnace")

        assert state.instrument_states["furnace"]["last_contact"] is not None
        handle_i_hb_mocks["hb_valid"].assert_called_once_with(
            state, heartbeat, "furnace"
        )
        # Should update instrument state
        assert state.instrument_states["furnace"]["state"] == "ready"
        assert state.instrument_states["furnace"]["setpoints"] == {}
        assert state.instrument_states["furnace"]["config"] == {
            "tolerance": 1,
            "experiment_id": None,
        }
        assert state.instruments_ready == True
        messages = handle_i_hb_mocks["messages"]()
        assert len(messages) == 1
        assert messages[0].topic == "controller/event/ready"
        assert json.loads(messages[0].payload)["experiment_id"] == "123"


class TestHeartbeatValid:
    @pytest.fixture
    def hb_valid_mocks(self, state, message_bus):
        expected_hb_config = {
            "firmware": "test_firmware",
            "device_address": "test_address",
            "simulate": "test_true",
            "variables": ["some", "variables"],
        }
        state.config.get_expected_heartbeat.return_value = expected_hb_config

        def get_decoded_bus_messages(topic=None):
            return message_bus.get_messages(topic=topic, decoded=True)

        yield {
            "state": state,
            "expected_hb_config": expected_hb_config,
            "messages": get_decoded_bus_messages,
        }

    def test_valid_heartbeat(self, hb_valid_mocks):
        state = hb_valid_mocks["state"]
        heartbeat = {"config": hb_valid_mocks["expected_hb_config"]}
        res = heartbeat_valid(state, heartbeat, "furnace")
        assert res == True
        messages = hb_valid_mocks["messages"]()
        assert len(messages) == 0

    def test_invalid_heartbeat(self, hb_valid_mocks, capsys):
        state = hb_valid_mocks["state"]
        heartbeat = {"config": {"some": "nonsense"}}
        res = heartbeat_valid(state, heartbeat, "furnace")
        assert res == False
        captured = capsys.readouterr()
        assert "ERROR: Instrument 'furnace'" in captured.out
        assert "Expected: {" in captured.out
        assert "; Received: {" in captured.out
        assert "Stopping experiment." in captured.out
        messages = hb_valid_mocks["messages"]()
        assert len(messages) == 2
        assert messages[0].topic == "error/instrument"
        assert json.loads(messages[0].payload)["code"] == "configuration"
        assert "misconfigured" in json.loads(messages[0].payload)["message"]
        assert messages[1].topic == "controller/command/stop"
        assert json.loads(messages[1].payload)["id"] == "123"
