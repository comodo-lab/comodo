import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call

from setpoint_controller import main, SetpointController
from tests.conftest import (
    MockMessage,
    parse_message_args,
    mock_MQTTPublisher,
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

    def test_publisher_initialized_once(self, mocks_for_main, mock_MQTTPublisher):
        mocks = mocks_for_main
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A",
                "ACTUATOR": "B",
            }
        )

        with patch("setpoint_controller.MQTTPublisher") as mock_publisher_class:
            main()

            mock_publisher_class.get_instance.assert_called_once_with(
                broker_address="test_host",
                user="test_user",
                password="test_pass",
                id="publisher_pid_A__B",
            )

    def test_spc_initialized_with_correct_params(self, mocks_for_main):
        mocks = mocks_for_main

        mocks["env_values"].update(
            {
                "HEARTBEAT_INTERVAL": 2000,
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A",
                "ACTUATOR": "B",
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
            sensor="A",
            actuator="B",
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )


class Test_SetpointController_init:

    @pytest.fixture(autouse=True)
    def mocks_for_spc_init(self):
        with patch("setpoint_controller.MQTTClient") as mock_mqtt_client_class, patch(
            "setpoint_controller.PID"
        ) as mock_pid_class, patch("setpoint_controller.t.sleep") as mock_sleep, patch(
            "setpoint_controller.SetpointController.publish_heartbeat"
        ) as mock_publish_heartbeat:
            # Configure the mocks
            mock_client_instance = MagicMock()
            mock_mqtt_client_class.return_value = mock_client_instance

            mock_pid_instance = MagicMock()
            mock_pid_instance.healthy = True
            mock_pid_instance.sensor = "test_sensor"
            mock_pid_instance.actuator = "test_actuator"
            mock_pid_instance.id = "pid/A__B"
            mock_pid_class.return_value = mock_pid_instance

            mock_sleep.side_effect = lambda *args, **kwargs: setattr(
                mock_pid_instance, "healthy", False
            )

            # Yield mocks for use in tests
            yield {
                "client_class": mock_mqtt_client_class,
                "client": mock_client_instance,
                "pid_class": mock_pid_class,
                "pid": mock_pid_instance,
                "sleep": mock_sleep,
                "publish_heartbeat": mock_publish_heartbeat,
            }

    def test_pid_initialized_with_correct_params(self, mocks_for_spc_init):
        mocks = mocks_for_spc_init

        spc = base_SPC(
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )

        mocks["pid_class"].assert_called_once_with(
            id=f"pid/A__B",
            sensor="A",
            actuator="B",
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )

    def test_mqtt_client_initialized_with_correct_params(self, mocks_for_spc_init):
        mocks = mocks_for_spc_init

        spc = base_SPC()

        mocks["client_class"].assert_called_once_with(
            id="pid/A__B",
            callback=spc.on_sensor_message,
            topics=[
                "sensor/A/setpoint",
                "measurement/A",
                "sensor/A/setpoint_reached",
                "pid/A__B/setup",
            ],
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            obj=spc,
        )

    def test_heartbeat_loop_is_entered(self, mocks_for_spc_init, mock_MQTTPublisher):
        mocks = mocks_for_spc_init

        spc = base_SPC()
        spc.start_heartbeat_loop()

        assert mock_MQTTPublisher.publish.call_args_list == [
            # Should publish initial setpoint as None upon creation
            call(f"{mocks['pid'].id}/setpoint", json.dumps({spc.pid.sensor: None})),
            # Then publish heartbeat
        ]
        mocks["publish_heartbeat"].assert_called_once()
        mocks["sleep"].assert_called_once_with(1)


class Test_on_sensor_message:
    def test_invalid_json_publishes_error(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        msg = MockMessage(
            f"sensor/{mock_spc.pid.sensor}/setpoint",
            "this is not valid json {",
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "error"
        mock_MQTTPublisher.publish.assert_called_once()
        topic, message = parse_message_args(mock_MQTTPublisher.publish.call_args[0])
        assert topic == f"error/{mock_spc.pid.id}"
        assert "error" in message.keys()
        assert "sensor/mock_sensor/setpoint message, wrong JSON:" in message["error"]


class Test_on_setpoint_message:
    def test_updates_pid_setpoint(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        setpoint_value = 50.0
        assert mock_spc.pid.setpoint != setpoint_value
        msg = MockMessage(
            f"sensor/{mock_spc.pid.sensor}/setpoint",
            json.dumps({mock_spc.pid.sensor: setpoint_value}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "adjusting"
        assert mock_spc.pid.setpoint == setpoint_value
        # Should publish updated setpoint
        mock_MQTTPublisher.publish.assert_called_once_with(
            f"{mock_spc.pid.id}/setpoint",
            json.dumps({mock_spc.pid.sensor: setpoint_value}),
        )

    def test_zero_is_valid_setpoint(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        setpoint_value = 0.0
        assert mock_spc.pid.setpoint != setpoint_value
        msg = MockMessage(
            f"sensor/{mock_spc.pid.sensor}/setpoint",
            json.dumps({mock_spc.pid.sensor: setpoint_value}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "adjusting"
        assert mock_spc.pid.setpoint == setpoint_value
        # Should publish updated setpoint
        mock_MQTTPublisher.publish.assert_called_once_with(
            f"{mock_spc.pid.id}/setpoint",
            json.dumps({mock_spc.pid.sensor: setpoint_value}),
        )

    def test_ignores_other_setpoints(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        msg = MockMessage(
            f"sensor/{mock_spc.pid.sensor}/setpoint",
            json.dumps({"some_other_sensor": 42.42}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "no_setpoint"
        assert mock_spc.pid.setpoint == None
        assert mock_MQTTPublisher.publish.call_count == 0


class Test_on_measurement_message:

    def test_skips_if_setpoint_undefined(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        mock_spc.pid.setpoint = None
        msg = MockMessage(
            f"measurement/{mock_spc.pid.sensor}", json.dumps({"value": 45.0})
        )

        with patch("src.pid.PID.step") as mock_spc.pid_step:
            SetpointController.on_sensor_message(client, msg, mock_spc)

            assert mock_spc.state["status"] == "no_setpoint"
            mock_spc.pid_step.assert_not_called()
            mock_MQTTPublisher.publish.assert_not_called()

    def test_measurement_publishes_to_actuator(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        mock_spc.pid.setpoint = 50.0
        measurement_value = 45.0
        msg = MockMessage(
            f"measurement/{mock_spc.pid.sensor}",
            json.dumps({"value": measurement_value}),
        )

        with patch("src.pid.PID.step", return_value=6.7) as mock_spc.pid_step:
            SetpointController.on_sensor_message(client, msg, mock_spc)

            assert mock_spc.state["status"] == "adjusting"
            mock_spc.pid_step.assert_called_once_with(
                measurement_value, mock_spc.pid.setpoint
            )
            mock_MQTTPublisher.publish.assert_called_once_with(
                f"sensor/{mock_spc.pid.actuator}/setpoint",
                json.dumps({mock_spc.pid.actuator: 6.7}),
            )


class Test_on_setpoint_reached_message:

    def test_resets_setpoint_on_reached(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        mock_spc.pid.setpoint = 50.0
        msg = MockMessage(
            f"sensor/{mock_spc.pid.sensor}/setpoint_reached",
            json.dumps({mock_spc.pid.sensor: True}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "ready"
        assert mock_spc.pid.setpoint is None
        mock_MQTTPublisher.publish.assert_called_once_with(
            f"{mock_spc.pid.id}/setpoint_reached",
            json.dumps({mock_spc.pid.sensor: True}),
        )


class Test_on_setup_message:

    def test_updates_configurable_parameters(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        msg = MockMessage(
            f"{mock_spc.pid.id}/setup",
            json.dumps({"k_p": new_k_p, "k_i": new_k_i}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "reconfigured"
        assert mock_spc.state["config"]["k_p"] == new_k_p
        assert mock_spc.state["config"]["k_i"] == new_k_i
        assert mock_spc.pid.k_p == new_k_p
        assert mock_spc.pid.k_i == new_k_i
        mock_MQTTPublisher.publish.assert_called_once_with(
            f"heartbeat/{mock_spc.pid.id}",
            f"{mock_spc.pid.get_state(1)}",
        )

    def test_rejects_non_configurable_parameters(self, mock_spc, mock_MQTTPublisher):
        client = Mock()
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        msg = MockMessage(
            f"{mock_spc.pid.id}/setup",
            json.dumps({"k_p": new_k_p, "k_i": new_k_i, "non_configurable_param": 123}),
        )

        SetpointController.on_sensor_message(client, msg, mock_spc)

        assert mock_spc.state["status"] == "error"
        assert mock_spc.pid.k_p == 1.0
        assert mock_spc.pid.k_i == 10
        mock_MQTTPublisher.publish.assert_called_once()
        topic, message = parse_message_args(mock_MQTTPublisher.publish.call_args[0])
        assert topic == f"error/{mock_spc.pid.id}"
        assert "error" in message.keys()
        assert (
            "Cannot configure PID parameter: non_configurable_param. Aborting setup."
            in message["error"]
        )


class TestPublishHeartbeat:
    def test_uses_status(self, mock_MQTTPublisher):
        spc = base_SPC()
        spc.state = {"status": "testing_status"}

        spc.publish_heartbeat()

        assert mock_MQTTPublisher.publish.call_args_list == [
            call("pid/A__B/setpoint", '{"A": null}'),
            call(f"heartbeat/{spc.pid.id}", json.dumps({"status": "testing_status"})),
        ]

    def test_fields_included(self, mock_MQTTPublisher):
        spc = base_SPC()

        spc.publish_heartbeat()

        expected = {
            "name": "pid_A__B",
            "status": "no_setpoint",
            "setpoint": None,
            "config": {
                "k_p": 1.0,
                "k_i": 0.1,
                "k_d": 0.05,
                "k_aw": 0.0,
                "k_df": 0.0,
                "max": 100.0,
                "min": 0.0,
                "max_rate": None,
            },
        }
        assert mock_MQTTPublisher.publish.call_args_list == [
            call("pid/A__B/setpoint", '{"A": null}'),
            call(f"heartbeat/{spc.pid.id}", json.dumps(expected)),
        ]
