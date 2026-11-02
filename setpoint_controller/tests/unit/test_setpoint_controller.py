import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call

from setpoint_controller import main, SetpointController

from utils.mqtt_validator import MQTTValidationException

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
        with (
            patch("os.getenv") as mock_getenv,
            patch("setpoint_controller.SetpointController") as mock_spc_class,
        ):
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
        missing_vars = [
            "MQTT_USER",
            "MQTT_PASS",
            "SENSOR",
            "DEFAULT_SETPOINT",
            "ACTUATOR",
        ]

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Missing required environment variables" in captured.out
        assert all(var in captured.out for var in missing_vars)
        assert "MQTT_HOST" not in captured.out
        # Ensure that SetpointController was never initialized
        mocks["spc_class"].assert_not_called()

    def test_fails_to_start_with_invalid_sensor_format(self, mocks_for_main, capsys):
        mocks = mocks_for_main

        # Simulate invalid SENSOR value
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "invalid_sensor",  # Missing '/'
                "DEFAULT_SETPOINT": "4.2",
                "ACTUATOR": "test/actuator",
            }
        )

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Invalid environment variable" in captured.out
        assert "SENSOR must be instrument_name/variable_name" in captured.out

    def test_fails_to_start_with_invalid_default_setpoint(self, mocks_for_main, capsys):
        mocks = mocks_for_main

        # Simulate invalid ACTUATOR value
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "test/sensor",
                "DEFAULT_SETPOINT": "invalid_value",
                "ACTUATOR": "test/actuator",
            }
        )

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Invalid DEFAULT_SETPOINT value: 'invalid_value'." in captured.out

    def test_fails_to_start_with_invalid_actuator_format(self, mocks_for_main, capsys):
        mocks = mocks_for_main

        # Simulate invalid ACTUATOR value
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "test/sensor",
                "DEFAULT_SETPOINT": "4.2",
                "ACTUATOR": "invalid_actuator",  # Missing '/'
            }
        )

        with pytest.raises(SystemExit):
            main()

        captured = capsys.readouterr()
        assert "Invalid environment variable" in captured.out
        assert "ACTUATOR must be instrument_name/variable_name" in captured.out

    def test_parameters_pulled_from_env(self, mocks_for_main):
        mocks = mocks_for_main
        mocks["env_values"].update(
            {
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A/B",
                "DEFAULT_SETPOINT": "4.2",
                "ACTUATOR": "C/D",
            }
        )

        main()

        assert mocks["getenv"].call_args_list == [
            call("HEARTBEAT_INTERVAL", "1.0"),
            call("MQTT_HOST"),
            call("MQTT_USER"),
            call("MQTT_PASS"),
            call("SENSOR"),
            call("DEFAULT_SETPOINT"),
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
                "DEFAULT_SETPOINT": "4.2",
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
                "HEARTBEAT_INTERVAL": 2,
                "MQTT_HOST": "test_host",
                "MQTT_USER": "test_user",
                "MQTT_PASS": "test_pass",
                "SENSOR": "A/B",
                "DEFAULT_SETPOINT": "4.2",
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
            default_setpoint=4.2,
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
    def spci_mocks(self, mqtt_mocks):
        with (
            patch("setpoint_controller.PID") as mock_pid_class,
            patch("setpoint_controller.t.sleep") as mock_sleep,
            patch(
                "setpoint_controller.SetpointController.publish_heartbeat"
            ) as mock_publish_heartbeat,
        ):
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

    def test_pid_initialized_with_correct_params(self, spci_mocks, base_SPC, capsys):
        mocks = spci_mocks

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
        captured = capsys.readouterr()
        assert "SPC initialised: I1-A--I2-B" in captured.out
        assert "Default setpoint set: 0.0" in captured.out

    def test_mqtt_client_initialized_with_correct_params(self, spci_mocks, base_SPC):
        mocks = spci_mocks

        spc = base_SPC()

        mocks["client_class"].assert_called_once_with(
            id="I1-A--I2-B",
            callback=spc.on_message,
            topics=[
                "instruments/I1/A/setpoint",
                "instruments/I1/A/measurement",
                "setpoint_controllers/I1-A--I2-B/configure",
                "controller/command/start",
                "controller/event/end",
                "controller/command/stop",
            ],
            broker_address="test_host",
            user="test_user",
            password="test_pass",
            obj=spc,
        )

    def test_heartbeat_loop_is_entered(self, spci_mocks, mqtt_mocks, base_SPC):
        mocks = spci_mocks

        spc = base_SPC()
        spc.start_heartbeat_loop()

        mocks["publish_heartbeat"].assert_called_once()
        mocks["sleep"].assert_called_once_with(1)


class Test_SetpointController_Status:

    def test_initialization(self, base_SPC):
        spc = base_SPC()

        assert spc.state.enabled == True
        assert spc.state.status == "idle"
        assert spc.state.sensor_setpoint == spc.default_setpoint
        assert spc.state.sensor_measurement is None
        assert spc.state.actuator_setpoint is None
        assert spc.state.experiment_id is None

    def test_status_validation(self, base_SPC):
        spc = base_SPC()

        # Valid status
        for valid_status in spc.state.allowed_status:
            spc.state.status = valid_status
            assert spc.state.status == valid_status

        spc.state.status = "idle"  # Reset to default

        # Invalid status should raise ValueError
        with pytest.raises(ValueError) as e:
            spc.state.status = "invalid_status"
        assert "Invalid status: invalid_status" in str(e.value)

        assert spc.state.status == "idle"  # Should not have changed

    def test_type_checking(self, base_SPC):
        spc = base_SPC()

        # Type checking for enabled
        with pytest.raises(TypeError):
            spc.state.enabled = "not_a_boolean"

        # Type checking for sensor_setpoint
        with pytest.raises(TypeError):
            spc.state.sensor_setpoint = "not_a_float"

        # Type checking for sensor_measurement
        with pytest.raises(TypeError):
            spc.state.sensor_measurement = "not_a_float"

        # Type checking for actuator_setpoint
        with pytest.raises(TypeError):
            spc.state.actuator_setpoint = "not_a_float"

    def test_cannot_get_or_set_random_keys(self, base_SPC):
        spc = base_SPC()

        with pytest.raises(AttributeError):
            _ = spc.state.new_attribute

        with pytest.raises(AttributeError):
            spc.state.new_attribute = "value"

    def test_get_and_set(self, base_SPC):
        spc = base_SPC()

        # set values as attributes
        spc.state.enabled = False
        spc.state.status = "ready"
        spc.state.sensor_setpoint = 42.0
        spc.state.sensor_measurement = 40.0
        spc.state.actuator_setpoint = 5.0
        spc.state.experiment_id = "exp123"

        # get values as attributes
        assert spc.state.enabled == False
        assert spc.state.status == "ready"
        assert spc.state.sensor_setpoint == 42.0
        assert spc.state.sensor_measurement == 40.0
        assert spc.state.actuator_setpoint == 5.0
        assert spc.state.experiment_id == "exp123"

    def test_status_reset_on_disable(self, base_SPC):
        spc = base_SPC()
        spc.state.status = "ready"
        spc.state.sensor_setpoint = 42.0
        spc.state.sensor_measurement = 40.0
        spc.state.actuator_setpoint = 5.0
        spc.state.experiment_id = "exp123"

        spc.state.enabled = False

        assert spc.state.enabled == False
        assert spc.state.status == "idle"
        assert spc.state.sensor_setpoint is None
        assert spc.state.sensor_measurement is None
        assert spc.state.actuator_setpoint is None
        assert spc.state.experiment_id is None

    def test_status_reset_on_idle(self, base_SPC):
        spc = base_SPC()
        spc.state.enabled = True
        spc.state.sensor_setpoint = 42.0
        spc.state.sensor_measurement = 40.0
        spc.state.actuator_setpoint = 5.0
        spc.state.experiment_id = "exp123"

        spc.state.status = "idle"

        assert spc.state.status == "idle"
        assert spc.state.enabled == True
        assert spc.state.sensor_setpoint is None
        assert spc.state.sensor_measurement is None
        assert spc.state.actuator_setpoint is None
        assert spc.state.experiment_id is None

    def test_status_as_dict(self, base_SPC):
        spc = base_SPC()
        spc.state.enabled = True
        spc.state.status = "ready"
        spc.state.sensor_setpoint = 42.0
        spc.state.sensor_measurement = 40.0
        spc.state.actuator_setpoint = 5.0
        spc.state.experiment_id = "exp123"

        expected_dict = {
            "state": {
                "status": "ready",
                "enabled": True,
                "sensor_measurement": 40.0,
                "actuator_setpoint": 5.0,
                "experiment_id": "exp123",
            },
            "setpoints": {
                "sensor_setpoint": 42.0,
            },
        }
        assert spc.state.as_dict() == expected_dict


class Test_on_message:

    def test_invalid_message_publishes_error(self, mock_spc, mqtt_validator_mocks):
        client = Mock()
        err = MQTTValidationException("Invalid JSON")
        mqtt_validator_mocks["validate_message"].side_effect = err
        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            "this is not valid json {",
        )

        SetpointController.on_message(client, msg, mock_spc)

        mqtt_validator_mocks["validate_message"].assert_called_once_with(
            msg.topic, msg.payload
        )
        mqtt_validator_mocks["print_and_publish_error"].assert_called_once_with(
            "error/setpoint_controller", err
        )
        assert mock_spc.state.status == "error"


class Test_on_setpoint_message:

    @pytest.fixture
    def osm_mocks(self, mock_spc, mqtt_mocks, mqtt_validator_mocks):
        def make_msg(setpoint_value):
            return MockMessage(
                f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
                json.dumps({"value": setpoint_value}),
            )

        return {
            "client": Mock(),
            "spc": mock_spc,
            "publisher": mqtt_mocks["publisher_instance"],
            "make_msg": make_msg,
        }

    def test_skips_if_not_enabled(self, osm_mocks):
        mock_spc = osm_mocks["spc"]
        mock_spc.state.enabled = False

        msg = osm_mocks["make_msg"](setpoint_value=50)
        SetpointController.on_message(osm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint == None
        osm_mocks["publisher"].publish.assert_not_called()

    def test_updates_sensor_setpoint(self, osm_mocks, capsys):
        mock_spc = osm_mocks["spc"]
        setpoint = 50
        assert mock_spc.state.sensor_setpoint == None

        msg = osm_mocks["make_msg"](setpoint_value=setpoint)
        SetpointController.on_message(osm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint == setpoint
        assert osm_mocks["publisher"].publish.call_count == 0
        captured = capsys.readouterr()
        assert f"New setpoint received: {setpoint}." in captured.out

    def test_zero_is_valid_setpoint(self, osm_mocks, capsys):
        mock_spc = osm_mocks["spc"]
        setpoint = 0
        assert mock_spc.state.sensor_setpoint != setpoint

        msg = osm_mocks["make_msg"](setpoint_value=setpoint)
        SetpointController.on_message(osm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint == setpoint
        assert osm_mocks["publisher"].publish.call_count == 0
        captured = capsys.readouterr()
        assert f"New setpoint received: {setpoint}." in captured.out

    def test_only_print_if_setpoint_new(self, osm_mocks, capsys):
        mock_spc = osm_mocks["spc"]
        setpoint = 50
        mock_spc.state.sensor_setpoint = setpoint

        msg = osm_mocks["make_msg"](setpoint_value=setpoint)
        SetpointController.on_message(osm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint == setpoint
        assert osm_mocks["publisher"].publish.call_count == 0
        captured = capsys.readouterr()
        assert "New setpoint received" not in captured.out

    def test_ignores_message_without_value(self, osm_mocks, capsys):
        mock_spc = osm_mocks["spc"]

        msg = MockMessage(
            f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/setpoint",
            json.dumps({"some_other_key": 42.42}),
        )
        SetpointController.on_message(osm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint is None
        assert osm_mocks["publisher"].publish.call_count == 0
        captured = capsys.readouterr()
        assert "New setpoint received" not in captured.out


class Test_on_measurement_message:

    @pytest.fixture
    def omm_mocks(self, mock_spc, mqtt_mocks, mqtt_validator_mocks):
        def make_msg(measurement_value):
            return MockMessage(
                f"instruments/{mock_spc.sensor_instrument}/{mock_spc.sensor_variable}/measurement",
                json.dumps({"value": measurement_value}),
            )

        return {
            "client": Mock(),
            "spc": mock_spc,
            "publisher": mqtt_mocks["publisher_instance"],
            "make_msg": make_msg,
        }

    def test_skips_if_not_enabled(self, omm_mocks):
        mock_spc = omm_mocks["spc"]
        mock_spc.state.enabled = False

        msg = omm_mocks["make_msg"](measurement_value=50)
        SetpointController.on_message(omm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.status == "idle"
        assert mock_spc.state.sensor_measurement == None
        omm_mocks["publisher"].publish.assert_not_called()

    def test_skips_pid_step_if_setpoint_undefined(self, omm_mocks):
        mock_spc = omm_mocks["spc"]
        assert mock_spc.state.sensor_setpoint == None

        msg = omm_mocks["make_msg"](measurement_value=45.0)
        SetpointController.on_message(omm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.status == "idle"
        assert mock_spc.state.sensor_measurement == 45.0
        mock_spc.pid.step.assert_not_called()
        omm_mocks["publisher"].publish.assert_not_called()

    def test_moves_to_adjusting_and_publishes_actuator_setpoint(self, omm_mocks):
        mock_spc = omm_mocks["spc"]
        setpoint_value = 50.0
        mock_spc.state.sensor_setpoint = setpoint_value
        measurement_value = 45.0
        msg = omm_mocks["make_msg"](measurement_value=measurement_value)
        mock_spc.pid.step = MagicMock(return_value=6.7)

        SetpointController.on_message(omm_mocks["client"], msg, mock_spc)

        assert mock_spc.state.sensor_setpoint == setpoint_value
        assert mock_spc.state.sensor_measurement == measurement_value
        assert mock_spc.state.status == "adjusting"
        mock_spc.pid.step.assert_called_once_with(measurement_value, setpoint_value)
        omm_mocks["publisher"].publish.assert_called_once_with(
            f"instruments/{mock_spc.actuator_instrument}/{mock_spc.actuator_variable}/setpoint",
            json.dumps({"value": 6.7}),
        )


class Test_on_configure_message:

    @pytest.fixture
    def osum_mocks(self, mock_spc, mqtt_mocks, mqtt_validator_mocks):
        def make_msg(config):
            return MockMessage(
                f"setpoint_controllers/{mock_spc.spc_id}/configure",
                json.dumps(config),
            )

        return {
            "client": Mock(),
            "spc": mock_spc,
            "publisher": mqtt_mocks["publisher_instance"],
            "make_msg": make_msg,
        }

    def test_checks_top_level_keys(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        config = {
            "enabled": True,
            "experiment_id": "exp123",
            "pid": {"k_p": 2.0, "k_i": 1.0},
            "something_else": "unexpected",
        }

        msg = osum_mocks["make_msg"](config)
        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        osum_mocks["publisher"].publish.assert_called_once()
        topic, message = parse_message_args(
            osum_mocks["publisher"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "spc_configuration_error"
        assert (
            "Cannot configure spc parameter: something_else. Aborting configuration."
            in message["message"]
        )
        assert mock_spc.state.experiment_id == None
        mock_spc.publish_heartbeat.assert_called_once()

    def test_accepts_enabled_by_itself(self, osum_mocks, capsys):
        mock_spc = osum_mocks["spc"]
        assert mock_spc.state.enabled == True
        config = {"enabled": False}

        msg = osum_mocks["make_msg"](config)
        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.state.enabled == False
        mock_spc.publish_heartbeat.assert_called_once()
        captured = capsys.readouterr()
        assert "SPC disabled." in captured.out

    def test_can_enable_when_disabled(self, osum_mocks, capsys):
        mock_spc = osum_mocks["spc"]
        mock_spc.state.enabled = False
        assert mock_spc.state.enabled == False
        config = {"enabled": True, "experiment_id": "exp789"}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.state.enabled == True
        assert mock_spc.state.experiment_id == "exp789"
        mock_spc.publish_heartbeat.assert_called_once()
        captured = capsys.readouterr()
        assert "SPC enabled." in captured.out

    def test_accepts_experiment_id_by_itself(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        assert mock_spc.state.experiment_id == None
        assert mock_spc.state.enabled == True
        config = {"experiment_id": "exp456"}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.state.experiment_id == "exp456"
        assert mock_spc.state.enabled == True
        mock_spc.publish_heartbeat.assert_called_once()

    def test_updates_configurable_parameters(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        config = {"pid": {"k_p": new_k_p, "k_i": new_k_i}}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.pid.k_p == new_k_p
        assert mock_spc.pid.k_i == new_k_i
        mock_spc.publish_heartbeat.assert_called_once()

    def test_rejects_non_configurable_parameters(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        config = {
            "pid": {"k_p": new_k_p, "k_i": new_k_i, "non_configurable_param": 123}
        }
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.pid.k_p == 1.0
        assert mock_spc.pid.k_i == 10
        osum_mocks["publisher"].publish.assert_called_once()
        topic, message = parse_message_args(
            osum_mocks["publisher"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "pid_configuration_error"
        assert (
            "Cannot configure PID parameter: non_configurable_param. Aborting configuration."
            in message["message"]
        )

    def test_can_configure_while_disabled(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        mock_spc.state.enabled = False
        assert mock_spc.state.enabled == False
        mock_spc.pid.k_p = 1.0
        new_k_p = 4.2
        mock_spc.pid.k_i = 10
        new_k_i = 42
        mock_spc.pid.configurable = ["k_p", "k_i"]
        config = {"pid": {"k_p": new_k_p, "k_i": new_k_i}}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.state.enabled == False
        assert mock_spc.pid.k_p == new_k_p
        assert mock_spc.pid.k_i == new_k_i
        mock_spc.publish_heartbeat.assert_called_once()

    def test_rejects_pid_while_experiment_running(self, osum_mocks):
        mock_spc = osum_mocks["spc"]
        mock_spc.state.experiment_id = "exp123"
        mock_spc.pid.k_p = 1.0
        mock_spc.pid.configurable = ["k_p"]
        config = {"enabled": False, "pid": {"k_p": 4.2}}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.pid.k_p == 1.0
        assert mock_spc.state.enabled == True
        assert mock_spc.state.experiment_id == "exp123"
        osum_mocks["publisher"].publish.assert_called_once()
        topic, message = parse_message_args(
            osum_mocks["publisher"].publish.call_args[0]
        )
        assert topic == "error/setpoint_controller"
        assert message["code"] == "pid_configuration_error"
        assert (
            "Cannot configure PID while experiment exp123 is running. "
            "Aborting configuration." in message["message"]
        )
        mock_spc.publish_heartbeat.assert_called_once()

    def test_accepts_non_pid_configuration_while_experiment_running(
        self, osum_mocks
    ):
        mock_spc = osum_mocks["spc"]
        mock_spc.state.experiment_id = "exp123"
        config = {"enabled": False}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.state.enabled == False
        osum_mocks["publisher"].publish.assert_not_called()
        mock_spc.publish_heartbeat.assert_called_once()

    def test_accepts_pid_with_experiment_id_before_experiment_starts(
        self, osum_mocks
    ):
        mock_spc = osum_mocks["spc"]
        assert mock_spc.state.experiment_id == None
        mock_spc.pid.k_p = 1.0
        mock_spc.pid.configurable = ["k_p"]
        config = {"experiment_id": "exp123", "pid": {"k_p": 4.2}}
        msg = osum_mocks["make_msg"](config)

        SetpointController.on_message(osum_mocks["client"], msg, mock_spc)

        assert mock_spc.pid.k_p == 4.2
        assert mock_spc.state.experiment_id == "exp123"
        osum_mocks["publisher"].publish.assert_not_called()
        mock_spc.publish_heartbeat.assert_called_once()


class Test_on_controller_start_message:

    @pytest.fixture
    def ocsm_mocks(self, mock_spc, mqtt_mocks, mqtt_validator_mocks):
        start_msg = MockMessage(
            "controller/command/start",
            json.dumps({"experiment_id": "exp-123"}),
        )

        return {
            "client": Mock(),
            "spc": mock_spc,
            "publisher": mqtt_mocks["publisher_instance"],
            "start_msg": start_msg,
        }

    def test_skips_if_not_enabled(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = False
        assert mock_spc.state.experiment_id == None

        msg = ocsm_mocks["start_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == None
        captured = capsys.readouterr()
        assert captured.out == ""  # No print output when disabled

    def test_sets_experiment_id_when_enabled(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = True
        assert mock_spc.state.experiment_id == None

        msg = ocsm_mocks["start_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == "exp-123"
        captured = capsys.readouterr()
        assert "Experiment started: exp-123" in captured.out


class Test_on_controller_end_message:

    @pytest.fixture
    def ocsm_mocks(self, mock_spc, mqtt_mocks, mqtt_validator_mocks):
        end_msg = MockMessage(
            "controller/event/end",
            json.dumps({"experiment_id": "exp-123"}),
        )
        stop_msg = MockMessage(
            "controller/command/stop",
            json.dumps({"experiment_id": "exp-123"}),
        )

        return {
            "client": Mock(),
            "spc": mock_spc,
            "publisher": mqtt_mocks["publisher_instance"],
            "end_msg": end_msg,
            "stop_msg": stop_msg,
        }

    def test_skips_if_not_enabled(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = False
        mock_spc.state.experiment_id = "exp-123"

        msg = ocsm_mocks["end_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == "exp-123"
        captured = capsys.readouterr()
        assert captured.out == ""  # No print output when disabled

    def test_unsets_experiment_id_when_enabled_end(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = True
        mock_spc.state.experiment_id = "exp-123"

        msg = ocsm_mocks["end_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == None
        captured = capsys.readouterr()
        assert "Experiment ended: exp-123" in captured.out
        assert "Moving to default setpoint" in captured.out
        assert f"{mock_spc.default_setpoint}" in captured.out
        assert mock_spc.state.sensor_setpoint == mock_spc.default_setpoint

    def test_unsets_experiment_id_when_enabled_stop(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = True
        mock_spc.state.experiment_id = "exp-123"

        msg = ocsm_mocks["stop_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == None
        captured = capsys.readouterr()
        assert "Experiment ended: exp-123" in captured.out
        assert "Moving to default setpoint" in captured.out
        assert f"{mock_spc.default_setpoint}" in captured.out
        assert mock_spc.state.sensor_setpoint == mock_spc.default_setpoint

    def test_skips_if_experiment_id_does_not_match(self, ocsm_mocks, capsys):
        mock_spc = ocsm_mocks["spc"]
        mock_spc.state.enabled = True
        mock_spc.state.experiment_id = "exp-456"  # Mismatched experiment ID

        msg = ocsm_mocks["end_msg"]
        SetpointController.on_message(ocsm_mocks["client"], msg, mock_spc)

        ocsm_mocks["publisher"].publish.assert_not_called()
        assert mock_spc.state.experiment_id == "exp-456"
        captured = capsys.readouterr()
        assert "Received end/stop for experiment exp-123" in captured.out
        assert "but current experiment is exp-456. Ignoring..." in captured.out


class TestPublishHeartbeat:
    def test_uses_state_and_pid(self, mqtt_mocks, base_SPC, mock_spc_state, mock_pid):
        spc = base_SPC()
        spc.state = mock_spc_state
        spc.pid = mock_pid
        spc.state.as_dict.side_effect = lambda: {
            "state": {"status": "testing_status"},
            "setpoints": {"sensor_setpoint": 42.0},
        }
        spc.pid.get_config.side_effect = lambda: {"mock": "config"}

        spc.publish_heartbeat()

        assert mqtt_mocks["publisher_instance"].publish.call_args_list == [
            call(
                "setpoint_controllers/I1-A--I2-B/heartbeat",
                json.dumps(
                    {
                        "state": {"status": "testing_status"},
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
