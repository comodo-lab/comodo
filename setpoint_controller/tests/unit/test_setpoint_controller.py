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

    def test_fails_to_start_without_required_env_vars(self, mocks_for_main, capsys):
        mocks = mocks_for_main

        # Simulate missing required environment variable
        mocks["env_values"].update({"MQTT_HOST": "some_host"})  # not missing
        missing_vars = ["MQTT_USER", "MQTT_PASS", "SENSOR", "ACTUATOR"]

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Missing required environment variables" in captured.out
        assert all(var in captured.out for var in missing_vars)
        assert "MQTT_HOST" not in captured.out
        # Ensure that SetpointController was never initialized
        mocks["spc_class"].assert_not_called()

    def test_parameters_pulled_from_env(self, mocks_for_main):
        mocks = mocks_for_main
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A/B",
                "ACTUATOR": "C/D",
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
                "SENSOR": "I1/A",
                "ACTUATOR": "I2/B",
            }
        )

        main()

        mqtt_mocks["publisher_class"].get_instance.assert_called_once_with(
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            id="publisher_I1-A--I2-B",
        )

    def test_spc_initialized_with_correct_params(self, mocks_for_main):
        mocks = mocks_for_main

        mocks["env_values"].update(
            {
                "HEARTBEAT_INTERVAL": 2000,
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A/B",
                "ACTUATOR": "C/D",
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
            spc_id="A-B--C-D",
            sensor_instrument="A",
            sensor_variable="B",
            actuator_instrument="C",
            actuator_variable="D",
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
            mock_pid_instance.id = "I1-A--I2-B"
            mock_pid_class.return_value = mock_pid_instance

            mock_sleep.side_effect = lambda *args, **kwargs: setattr(
                mock_pid_instance, "healthy", False
            )

            # Yield mocks for use in tests
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
            k_p=1.0,
            k_i=0.1,
            k_d=0.01,
            k_aw=0.5,
            k_df=0.2,
        )

        mocks["pid_class"].assert_called_once_with(
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

        spc = base_SPC()

        mocks["client_class"].assert_called_once_with(
            id="I1-A--I2-B",
            callback=spc.on_message,
            topics=[
                "instruments/I1/A/setpoint",
                "instruments/I1/A/measurement",
                "setpoint_controller/I1-A--I2-B/setup",
            ],
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            obj=spc,
        )

    def test_heartbeat_loop_is_entered(self, mocks_for_spc_init, mqtt_mocks, base_SPC):
        mocks = mocks_for_spc_init

        spc = base_SPC()
        spc.start_heartbeat_loop()

        mocks["publish_heartbeat"].assert_called_once()
        mocks["sleep"].assert_called_once_with(1)


class Test_SetpointController_State:

    def test_initialization(self, base_SPC):
        spc = base_SPC()

        assert spc.status.enabled == True
        assert spc.status.state == "idle"
        assert spc.status.sensor_setpoint is None
        assert spc.status.sensor_measurement is None
        assert spc.status.actuator_setpoint is None
        assert spc.status.experiment_id is None

    def test_state_validation(self, base_SPC):
        spc = base_SPC()

        # Valid state
        for valid_state in spc.status.allowed_state:
            spc.status.state = valid_state
            assert spc.status.state == valid_state

        spc.status.state = "idle"  # Reset to default

        # Invalid state should raise ValueError
        with pytest.raises(ValueError) as e:
            spc.status.state = "invalid_state"
        assert "Invalid state: invalid_state" in str(e.value)

        assert spc.status.state == "idle"  # Should not have changed

    def test_type_checking(self, base_SPC):
        spc = base_SPC()

        # Type checking for enabled
        with pytest.raises(TypeError):
            spc.status.enabled = "not_a_boolean"

        # Type checking for sensor_setpoint
        with pytest.raises(TypeError):
            spc.status.sensor_setpoint = "not_a_float"

        # Type checking for sensor_measurement
        with pytest.raises(TypeError):
            spc.status.sensor_measurement = "not_a_float"

        # Type checking for actuator_setpoint
        with pytest.raises(TypeError):
            spc.status.actuator_setpoint = "not_a_float"

    def test_cannot_get_or_set_random_keys(self, base_SPC):
        spc = base_SPC()

        with pytest.raises(AttributeError):
            _ = spc.status.new_attribute

        with pytest.raises(AttributeError):
            spc.status.new_attribute = "value"

    def test_get_and_set(self, base_SPC):
        spc = base_SPC()

        # set values as attributes
        spc.status.enabled = False
        spc.status.state = "ready"
        spc.status.sensor_setpoint = 42.0
        spc.status.sensor_measurement = 40.0
        spc.status.actuator_setpoint = 5.0
        spc.status.experiment_id = "exp123"

        # get values as attributes
        assert spc.status.enabled == False
        assert spc.status.state == "ready"
        assert spc.status.sensor_setpoint == 42.0
        assert spc.status.sensor_measurement == 40.0
        assert spc.status.actuator_setpoint == 5.0
        assert spc.status.experiment_id == "exp123"

    def test_state_reset_on_disable(self, base_SPC):
        spc = base_SPC()
        spc.status.state = "ready"
        spc.status.sensor_setpoint = 42.0
        spc.status.sensor_measurement = 40.0
        spc.status.actuator_setpoint = 5.0
        spc.status.experiment_id = "exp123"

        spc.status.enabled = False

        assert spc.status.enabled == False
        assert spc.status.state == "idle"
        assert spc.status.sensor_setpoint is None
        assert spc.status.sensor_measurement is None
        assert spc.status.actuator_setpoint is None
        assert spc.status.experiment_id is None

    def test_state_reset_on_idle(self, base_SPC):
        spc = base_SPC()
        spc.status.enabled = True
        spc.status.sensor_setpoint = 42.0
        spc.status.sensor_measurement = 40.0
        spc.status.actuator_setpoint = 5.0
        spc.status.experiment_id = "exp123"

        spc.status.state = "idle"

        assert spc.status.state == "idle"
        assert spc.status.enabled == True
        assert spc.status.sensor_setpoint is None
        assert spc.status.sensor_measurement is None
        assert spc.status.actuator_setpoint is None
        assert spc.status.experiment_id is None

    def test_state_as_dict(self, base_SPC):
        spc = base_SPC()
        spc.status.enabled = True
        spc.status.state = "ready"
        spc.status.sensor_setpoint = 42.0
        spc.status.sensor_measurement = 40.0
        spc.status.actuator_setpoint = 5.0
        spc.status.experiment_id = "exp123"

        expected_dict = {
            "status": {
                "state": "ready",
                "enabled": True,
                "sensor_measurement": 40.0,
                "actuator_setpoint": 5.0,
                "experiment_id": "exp123",
            },
            "setpoints": {
                "sensor_setpoint": 42.0,
            },
        }
        assert spc.status.as_dict() == expected_dict


class Test_on_message:

    def test_invalid_json_publishes_error(self, mock_spc, mqtt_mocks, capsys):
        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            "this is not valid json {",
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "error"
        mqtt_mocks["publisher_instance"].publish.assert_called_once()
        topic, message = parse_message_args(
            mqtt_mocks["publisher_instance"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "json_decode_error"
        exp_err = f"Cannot decode instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint message, wrong JSON:"
        assert exp_err in message["message"]
        assert f"ERROR: {exp_err}" in capsys.readouterr().out


class Test_on_setpoint_message:

    def test_skips_if_not_enabled(self, mock_spc, mqtt_mocks):
        mock_spc.status.enabled = False
        assert mock_spc.status.enabled == False

        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            json.dumps({"value": 50.0}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_setpoint == None
        mqtt_mocks["publisher_instance"].publish.assert_not_called()

    def test_updates_sensor_setpoint(self, mock_spc, mqtt_mocks):
        assert mock_spc.status.sensor_setpoint == None
        client = Mock()
        setpoint_value = 50.0
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            json.dumps({"value": setpoint_value}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_setpoint == setpoint_value
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0

    def test_zero_is_valid_setpoint(self, mock_spc, mqtt_mocks):
        client = Mock()
        setpoint_value = 0.0
        assert mock_spc.status.sensor_setpoint != setpoint_value
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            json.dumps({"value": setpoint_value}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_setpoint == setpoint_value
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0

    def test_ignores_message_without_value(self, mock_spc, mqtt_mocks):
        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            json.dumps({"some_other_key": 42.42}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_setpoint is None
        assert mqtt_mocks["publisher_instance"].publish.call_count == 0


class Test_on_measurement_message:

    def test_skips_if_not_enabled(self, mock_spc, mqtt_mocks):
        mock_spc.status.enabled = False
        assert mock_spc.status.enabled == False

        client = Mock()
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/measurement",
            json.dumps({"value": 50.0}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_measurement == None
        mqtt_mocks["publisher_instance"].publish.assert_not_called()

    def test_skips_pid_step_if_setpoint_undefined(self, mock_spc, mqtt_mocks):
        client = Mock()
        assert mock_spc.status.sensor_setpoint == None
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/measurement",
            json.dumps({"value": 45.0}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.state == "idle"
        assert mock_spc.status.sensor_measurement == 45.0
        mock_spc.pid.step.assert_not_called()
        mqtt_mocks["publisher_instance"].publish.assert_not_called()

    def test_moves_to_adjusting_and_publishes_actuator_setpoint(
        self, mock_spc, mqtt_mocks
    ):
        client = Mock()
        setpoint_value = 50.0
        mock_spc.status.sensor_setpoint = setpoint_value
        measurement_value = 45.0
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/measurement",
            json.dumps({"value": measurement_value}),
        )
        mock_spc.pid.step = MagicMock(return_value=6.7)

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.sensor_setpoint == setpoint_value
        assert mock_spc.status.sensor_measurement == measurement_value
        assert mock_spc.status.state == "adjusting"
        mock_spc.pid.step.assert_called_once_with(measurement_value, setpoint_value)
        mqtt_mocks["publisher_instance"].publish.assert_called_once_with(
            f"instruments/{mock_spc.actuator_instrument}/{mock_spc.actuator_variable}/setpoint",
            json.dumps({"value": 6.7}),
        )


class Test_on_setup_message:

    def test_checks_top_level_keys(self, mock_spc, mqtt_mocks):
        client = Mock()
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps(
                {
                    "enabled": True,
                    "experiment_id": "exp123",
                    "pid": {"k_p": 2.0, "k_i": 1.0},
                    "something_else": "unexpected",
                }
            ),
        )

        SetpointController.on_message(client, msg, mock_spc)

        mqtt_mocks["publisher_instance"].publish.assert_called_once()
        topic, message = parse_message_args(
            mqtt_mocks["publisher_instance"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "spc_configuration_error"
        assert (
            "Cannot configure spc parameter: something_else. Aborting setup."
            in message["message"]
        )
        assert mock_spc.status.experiment_id == None
        mock_spc.publish_heartbeat.assert_called_once()

    def test_accepts_enabled_by_itself(self, mock_spc, mqtt_mocks):
        client = Mock()
        assert mock_spc.status.enabled == True
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps(
                {
                    "enabled": False,
                }
            ),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.enabled == False
        mock_spc.publish_heartbeat.assert_called_once()

    def test_can_enable_when_disabled(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.status.enabled = False
        assert mock_spc.status.enabled == False
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps(
                {
                    "enabled": True,
                    "experiment_id": "exp789",
                }
            ),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.enabled == True
        assert mock_spc.status.experiment_id == "exp789"
        mock_spc.publish_heartbeat.assert_called_once()

    def test_accepts_experiment_id_by_itself(self, mock_spc, mqtt_mocks):
        client = Mock()
        assert mock_spc.status.experiment_id == None
        assert mock_spc.status.enabled == True
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps(
                {
                    "experiment_id": "exp456",
                }
            ),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.experiment_id == "exp456"
        assert mock_spc.status.enabled == True
        mock_spc.publish_heartbeat.assert_called_once()

    def test_updates_configurable_parameters(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps({"pid": {"k_p": new_k_p, "k_i": new_k_i}}),
        )

        SetpointController.on_message(client, msg, mock_spc)

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
            json.dumps(
                {"pid": {"k_p": new_k_p, "k_i": new_k_i, "non_configurable_param": 123}}
            ),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.pid.k_p == 1.0
        assert mock_spc.pid.k_i == 10
        mqtt_mocks["publisher_instance"].publish.assert_called_once()
        topic, message = parse_message_args(
            mqtt_mocks["publisher_instance"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "pid_configuration_error"
        assert (
            "Cannot configure PID parameter: non_configurable_param. Aborting setup."
            in message["message"]
        )

    def test_can_configure_while_disabled(self, mock_spc, mqtt_mocks):
        client = Mock()
        mock_spc.status.enabled = False
        assert mock_spc.status.enabled == False
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        msg = MockMessage(
            f"setpoint_controller/{mock_spc.spc_id}/setup",
            json.dumps({"pid": {"k_p": new_k_p, "k_i": new_k_i}}),
        )

        SetpointController.on_message(client, msg, mock_spc)

        assert mock_spc.status.enabled == False
        assert mock_spc.pid.k_p == new_k_p
        assert mock_spc.pid.k_i == new_k_i
        mock_spc.publish_heartbeat.assert_called_once()


class TestPublishHeartbeat:
    def test_uses_status_and_pid(self, mqtt_mocks, base_SPC, mock_spc_status, mock_pid):
        spc = base_SPC()
        spc.status = mock_spc_status
        spc.pid = mock_pid
        spc.status.as_dict.side_effect = lambda: {
            "status": {"state": "testing_state"},
            "setpoints": {"sensor_setpoint": 42.0},
        }
        spc.pid.get_config.side_effect = lambda: {"mock": "config"}

        spc.publish_heartbeat()

        assert mqtt_mocks["publisher_instance"].publish.call_args_list == [
            call(
                "setpoint_controller/I1-A--I2-B/heartbeat",
                json.dumps(
                    {
                        "status": {"state": "testing_state"},
                        "setpoints": {"sensor_setpoint": 42.0},
                        "config": {
                            "sensor": "I1/A",
                            "actuator": "I2/B",
                            "pid": {"mock": "config"},
                        },
                    }
                ),
            ),
        ]
