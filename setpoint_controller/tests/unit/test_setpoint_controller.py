import pytest
import json
from unittest.mock import Mock, patch

from setpoint_controller import on_sensor_message
from tests.conftest import (
    MockMessage,
    parse_message_args,
    mock_mqtt_publisher,
    mock_pid,
)


class Test_on_sensor_message:
    def test_invalid_json_publishes_error(self, mock_pid, mock_mqtt_publisher):
        client = Mock()
        msg = MockMessage(
            f"sensor/{mock_pid.sensor}/setpoint",
            "this is not valid json {",
        )

        on_sensor_message(client, msg, mock_pid)

        mock_mqtt_publisher.publish.assert_called_once()
        topic, message = parse_message_args(mock_mqtt_publisher.publish.call_args[0])
        assert topic == f"error/{mock_pid.id}"
        assert "error" in message.keys()
        assert "sensor/mock_sensor/setpoint message, wrong JSON:" in message["error"]


class Test_on_setpoint_message:
    def test_updates_pid_setpoint(self, mock_pid, mock_mqtt_publisher):
        client = Mock()
        setpoint_value = 50.0
        assert mock_pid.setpoint != setpoint_value
        msg = MockMessage(
            f"sensor/{mock_pid.sensor}/setpoint",
            json.dumps({mock_pid.sensor: setpoint_value}),
        )

        on_sensor_message(client, msg, mock_pid)

        assert mock_pid.setpoint == setpoint_value
        mock_mqtt_publisher.publish.assert_not_called()

    def test_ignores_other_setpoints(self, mock_pid, mock_mqtt_publisher):
        client = Mock()
        msg = MockMessage(
            f"sensor/{mock_pid.sensor}/setpoint",
            json.dumps({"some_other_sensor": 42.42}),
        )

        on_sensor_message(client, msg, mock_pid)

        assert mock_pid.setpoint == None
        assert mock_mqtt_publisher.publish.call_count == 0


class Test_on_measurement_message:
    def test_skips_if_setpoint_undefined(self, mock_pid, mock_mqtt_publisher):
        client = Mock()
        mock_pid.setpoint = None
        msg = MockMessage(f"measurement/{mock_pid.sensor}", json.dumps({"value": 45.0}))

        with patch("src.pid.PID.step") as mock_pid_step:
            on_sensor_message(client, msg, mock_pid)

            mock_pid_step.assert_not_called()
            mock_mqtt_publisher.publish.assert_not_called()

    def test_measurement_publishes_to_actuator(self, mock_pid, mock_mqtt_publisher):
        client = Mock()
        mock_pid.setpoint = 50.0
        measurement_value = 45.0
        msg = MockMessage(
            f"measurement/{mock_pid.sensor}",
            json.dumps({"value": measurement_value}),
        )

        with patch("src.pid.PID.step", return_value=6.7) as mock_pid_step:
            on_sensor_message(client, msg, mock_pid)

            mock_pid_step.assert_called_once_with(measurement_value, mock_pid.setpoint)
            mock_mqtt_publisher.publish.assert_called_once_with(
                f"sensor/{mock_pid.actuator}/setpoint",
                json.dumps({mock_pid.actuator: 6.7}),
            )
