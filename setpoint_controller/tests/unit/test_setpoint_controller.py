import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call

from setpoint_controller import main, SetpointController
from tests.conftest import (
    MockMessage,
    parse_message_args,
    message_bus,
    mqtt_mocks,
    mock_pid,
    base_SPC,
)


class Test_main:

    @pytest.fixture(autouse=True)
    def mocks_for_main(self):
        """Patch all functions used in main, to prevent repetition in test."""
        with patch("os.getenv") as mock_getenv, patch(
            "setpoint_controller.SetpointController"
        ) as mock_spc_class:
            # Configure the mocks
            mock_spc_instance = MagicMock()
            start_heartbeat_loop_mock = MagicMock()
            mock_spc_instance.start_heartbeat_loop = start_heartbeat_loop_mock
            mock_spc_class.return_value = mock_spc_instance

            env_values = {}
            mock_getenv.side_effect = lambda var, default=None: env_values.get(
                var, default
            )

            # Yield mocks for use in tests
            yield {
                "env_values": env_values,
                "getenv": mock_getenv,
                "spc_class": mock_spc_class,
            }

    def test_fails_to_start_without_required_env_vars(self, mocks_for_main):
        mocks = mocks_for_main

        # Simulate missing required environment variable
        def getenv_side_effect(var, default=None):
            if var == "MQTT_HOST":
                raise KeyError("MQTT_HOST")
            return default

        mocks["getenv"].side_effect = getenv_side_effect

        with pytest.raises(SystemExit):
            main()

        # Ensure that SetpointController was never initialized
        mocks["spc_class"].assert_not_called()

    def test_parameters_pulled_from_env(self, mocks_for_main):
        mocks = mocks_for_main
        mocks["env_values"].update(
            {
                "SENSOR": "A.B",
                "ACTUATOR": "C.D",
            }
        )

        main()

        assert mocks["getenv"].call_args_list == [
            call("HEARTBEAT_INTERVAL", 1),
            call("MQTT_HOST"),
            call("MQTT_USER"),
            call("MQTT_PASS"),
            call("SENSOR"),
            call("ACTUATOR"),
            call("K_P", None),
            call("K_I", None),
            call("K_D", None),
            call("K_AW", None),
            call("K_DF", None),
            call("OUT_MAX", None),
            call("OUT_MIN", None),
            call("OUT_MAX_R", None),
        ]

    def test_publisher_initialized_once(self, mocks_for_main, mqtt_mocks):
        mocks = mocks_for_main
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "I1.A",
                "ACTUATOR": "I2.B",
            }
        )

        main()

        mqtt_mocks["publisher_class"].get_instance.assert_called_once_with(
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            id="publisher_spc_I1_A__I2_B",
        )

    def test_spc_initialized_with_correct_params(self, mocks_for_main):
        mocks = mocks_for_main

        mocks["env_values"].update(
            {
                "HEARTBEAT_INTERVAL": 2000,
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A.B",
                "ACTUATOR": "C.D",
                "K_P": 1.0,
                "K_I": 0.1,
                "K_D": 0.01,
                "K_AW": 0.5,
                "K_DF": 0.2,
            }
        )

        main()

        mocks["spc_class"].assert_called_once_with(
            mqtt_host="test_host",
            mqtt_user="test_user",
            mqtt_pass="test_pass",
            heartbeat_interval=2,
            spc_id="A/B__C/D",
            topic_id="spc-A.B-C.D",
            sensor_name="A",
            sensor_var="B",
            actuator_name="C",
            actuator_var="D",
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )


class Test_SetpointController_init:

    @pytest.fixture(autouse=True)
    def mocks_for_spc_init(self, mqtt_mocks):
        with patch("setpoint_controller.PID") as mock_pid_class, patch(
            "setpoint_controller.t.sleep"
        ) as mock_sleep, patch(
            "setpoint_controller.SetpointController.publish_heartbeat"
        ) as mock_publish_heartbeat:
            # Configure the mocks
            mock_pid_instance = MagicMock()
            mock_pid_instance.healthy = True
            mock_pid_instance.sensor = "I1/A"
            mock_pid_instance.actuator = "I2/B"
            mock_pid_instance.id = "I1/A__I2/B"
            mock_pid_class.return_value = mock_pid_instance

            mock_sleep.side_effect = lambda *args, **kwargs: setattr(
                mock_pid_instance, "healthy", False
            )

            yield {
                "client_class": mqtt_mocks["client_class"],
                "client": mqtt_mocks["client_instance"],
                "pid_class": mock_pid_class,
                "pid": mock_pid_instance,
                "sleep": mock_sleep,
                "publish_heartbeat": mock_publish_heartbeat,
            }

    def test_pid_initialized_with_correct_params(self, mocks_for_spc_init, base_SPC):
        mocks = mocks_for_spc_init

        spc = base_SPC(
            spc_id="I1/A__I2/B",
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )

        mocks["pid_class"].assert_called_once_with(
            id="I1/A__I2/B",
            sensor="I1/A",
            actuator="I2/B",
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )

    def test_mqtt_client_initialized_with_correct_params(
        self, mocks_for_spc_init, base_SPC
    ):
        mocks = mocks_for_spc_init

        spc = base_SPC(spc_id="I1/A__I2/B")

        mocks["client_class"].assert_called_once_with(
            id="I1/A__I2/B",
            callback=spc.on_message,
            topics=[
                "instruments/I1/A/setpoint",
                "instruments/I1/A/measurement",
                "setpoint_controller/I1/A__I2/B/setup",
            ],
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            obj=spc,
        )

    def test_heartbeat_loop_is_entered(self, mocks_for_spc_init, mqtt_mocks, base_SPC):
        mocks = mocks_for_spc_init

        spc = base_SPC(spc_id="I1/A__I2/B")
        spc.start_heartbeat_loop()

        mocks["publish_heartbeat"].assert_called_once()
        mocks["sleep"].assert_called_once_with(1)


class Test_on_sensor_message:
    def test_invalid_json_publishes_error(self, mock_spc, mqtt_mocks, capsys):
        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/setpoint",
            "this is not valid json {",
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "error"
        mqtt_mocks["publisher_instance"].publish.assert_called_once()
        topic, message = parse_message_args(
            mqtt_mocks["publisher_instance"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "json_decode_error"
        exp_err = f"Cannot decode instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/setpoint message, wrong JSON:"
        assert exp_err in message["message"]
        assert f"ERROR: {exp_err}" in capsys.readouterr().out


class Test_on_setpoint_message:
    def test_updates_pid_setpoint(self, mock_spc, mqtt_mocks):
        client = Mock()
        setpoint_value = 50.0
        assert mock_spc.pid.setpoint != setpoint_value
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/setpoint",
            json.dumps({"value": setpoint_value}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "adjusting"
        assert mock_spc.pid.setpoint == setpoint_value
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0

    def test_zero_is_valid_setpoint(self, mock_spc, mqtt_mocks):
        client = Mock()
        setpoint_value = 0.0
        assert mock_spc.pid.setpoint != setpoint_value
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/setpoint",
            json.dumps({"value": setpoint_value}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "adjusting"
        assert mock_spc.pid.setpoint == setpoint_value
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0

    def test_ignores_message_without_value(self, mock_spc, mqtt_mocks):
        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/setpoint",
            json.dumps({"some_other_key": 42.42}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "idle"
        assert mock_spc.pid.setpoint is None
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0


class Test_on_measurement_message:

    def test_skips_if_setpoint_undefined(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.pid.setpoint = None
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/measurement",
            json.dumps({"value": 45.0}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "idle"
        mock_spc.pid.step.assert_not_called()
        mqtt_mocks["publisher_instance"].publish.assert_not_called()

    def test_measurement_publishes_to_actuator(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.pid.setpoint = 50.0
        measurement_value = 45.0
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_name}/{mock_spc.sensor_var}/measurement",
            json.dumps({"value": measurement_value}),
        )
        mock_spc.pid.step = MagicMock(return_value=6.7)
        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "adjusting"
        mock_spc.pid.step.assert_called_once_with(
            measurement_value, mock_spc.pid.setpoint
        )
        mqtt_mocks["publisher_instance"].publish.assert_called_once_with(
            f"instruments/{mock_spc.actuator_name}/{mock_spc.actuator_var}/setpoint",
            json.dumps({"value": 6.7}),
        )


class Test_on_setup_message:

    def test_updates_configurable_parameters(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps({"k_p": new_k_p, "k_i": new_k_i}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "idle"
        assert mock_spc.status["config"]["k_p"] == new_k_p
        assert mock_spc.status["config"]["k_i"] == new_k_i
        assert mock_spc.pid.k_p == new_k_p
        assert mock_spc.pid.k_i == new_k_i
        mock_spc.publish_heartbeat.assert_called_once()

    def test_rejects_non_configurable_parameters(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps({"k_p": new_k_p, "k_i": new_k_i, "non_configurable_param": 123}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status["state"] == "error"
        assert mock_spc.pid.k_p == 1.0
        assert mock_spc.pid.k_i == 10
        mqtt_mocks["publisher_instance"].publish.assert_called_once()
        topic, message = parse_message_args(
            mqtt_mocks["publisher_instance"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "configuration_error"
        assert (
            "Cannot configure PID parameter: non_configurable_param. Aborting setup."
            in message["message"]
        )


class TestPublishHeartbeat:
    def test_uses_status(self, mqtt_mocks, base_SPC):
        spc = base_SPC()
        spc.status = {"state": "testing_state", "setpoints": {}, "config": {}}

        spc.publish_heartbeat()

        assert mqtt_mocks["publisher_instance"].publish.call_args_list == [
            call("setpoint_controller/spc-I1.A-I2.B/heartbeat", json.dumps(
                {"state": "testing_state", "setpoints": {}, "config": {}}
            )),
        ]

    def test_fields_included(self, mqtt_mocks, base_SPC):
        spc = base_SPC()

        spc.publish_heartbeat()

        expected = {
            "state": "idle",
            "setpoints": {},
            "config": {
                "sensor": "I1/A",
                "actuator": "I2/B",
                "active": True,
                "k_p": 1.0,
                "k_i": 0.1,
                "k_d": 0.05,
                "k_aw": 0.0,
                "k_df": 0.0,
                "max": 100.0,
                "min": 0.0,
                "max_rate": None,
                "experiment_id": None,
            },
        }
        assert mqtt_mocks["publisher_instance"].publish.call_args_list == [
            call("setpoint_controller/spc-I1.A-I2.B/heartbeat", json.dumps(expected)),
        ]
