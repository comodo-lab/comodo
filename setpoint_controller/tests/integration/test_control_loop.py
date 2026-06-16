"""
Integration tests for the complete control loop.

These tests simulate the full control loop with mock sensor, actuator, and setpoint controller
communicating via an in-memory message bus, without requiring external services.
"""

from tracemalloc import stop
from unittest.mock import patch
import pytest
import time
import threading
import queue
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
import fnmatch

from src.pid import PID
from setpoint_controller import SetpointController
from utils.mqtt_clients import load_message
from tests.conftest import (
    MockMessage,
    InMemoryMessageBus,
    message_bus,
    mqtt_mocks,
    base_SPC,
    mock_pid_time,
)


def wait_for_equilibrium(
    sensors,
    targets,
    tolerance=0.01,
    timeout=2.0,
    n_steps=10,
    stop=True,
):
    s_is_list = isinstance(sensors, list)
    t_is_list = isinstance(targets, list)
    assert (
        s_is_list == t_is_list
    ), "sensors and targets must both be lists or both be single values"

    if not s_is_list:
        sensors = [sensors]
        targets = [targets]
    # Wait for equilibrium or timeout
    step_count = [0] * len(sensors)
    t_start = time.time()
    reached = [False] * len(sensors)
    while (time.time() - t_start) < timeout:
        for i, sensor in enumerate(sensors):
            # Equilibrium check
            if sensor.running:
                abs_error = abs(sensor.value - targets[i])
                sensor.bus.publish(
                    "--debug--",
                    f"Sensor: {sensor.instrument_name}/{sensor.variable_name}, Error: {abs_error=}, Reached: {step_count[i]}",
                )
                time.sleep(0.001)
                step_count[i] = step_count[i] + 1 if abs_error < tolerance else 0
            if step_count[i] >= n_steps:
                reached[i] = True
                if stop:
                    sensor.stop()
        if all(reached):
            break

    return reached if s_is_list else reached[0]


class MockSensor:
    """
    Simulates a sensor that allows its value to be set (e.g. by the effect of an actuator)
    and publishes its new value (which would e.g. trigger a setpoint controller).
    """

    def __init__(
        self,
        instrument_name: str,
        variable_name: str,
        bus: InMemoryMessageBus,
        initial_value: float = 20.0,
    ):
        self.instrument_name = instrument_name
        self.variable_name = variable_name
        self.bus = bus
        self.value = initial_value
        self.running = True
        self.thread = None

        # Subscribe to setpoint messages (trigger measurement publishing)
        self.bus.subscribe(
            f"instruments/{self.instrument_name}/{self.variable_name}/setpoint",
            self.publish_measurement,
        )

    def stop(self):
        """Stop reacting to setpoint changes."""
        self.running = False

    def publish_measurement(self, topic: str = None, payload: str = None):
        """
        Publishes the sensor's current value.
        """
        payload = json.dumps({"value": self.value})
        self.bus.publish(
            f"instruments/{self.instrument_name}/{self.variable_name}/measurement",
            payload,
        )

    def set_value(self, value: float):
        """
        Sets a new value for the sensor and publishes it.
        """
        if self.running:
            self.value = value
            self.publish_measurement()


class MockActuator:
    """
    Simulates an actuator that receives setpoints and affects the sensor.

    The dynamics of actuator-sensor can be controlled via the gain, loss and
    equilibrium parameters:
        gain -- Impact of actuator value on sensor value (e.g. heating rate)
            defaults to: 0.01
        loss -- Restoring force (e.g., heat loss)
            defaults to: 0.01
        equilibrium -- Restoration setpoint (e.g. ambient temperature)
            defaults to: 20.0
    """

    def __init__(
        self,
        instrument_name: str,
        variable_name: str,
        bus: InMemoryMessageBus,
        sensor: MockSensor,
        gain: float = 0.2,
        loss: float = 0.1,
        equilibrium: float = 20.0,
    ):
        # Parameters for actuator-sensor dynamics
        self.gain = gain
        self.loss = loss
        self.equilibrium = equilibrium

        # Connect to message bus and sensor
        self.instrument_name = instrument_name
        self.variable_name = variable_name
        self.bus = bus
        self.sensor = sensor
        self.setpoint = None
        self.thread = None
        # Subscribe to setpoint messages
        self.bus.subscribe(
            f"instruments/{self.instrument_name}/{self.variable_name}/setpoint",
            self.on_setpoint,
        )

    def on_setpoint(self, topic: str, msg):
        """
        Receives a setpoint and triggers effect on sensor.

        The actuator is assumed to reach its own setpoint immediately,
        that is, the actuator value is assumed to be equal to its setpoint.
        """
        try:
            data = load_message(msg)
            value = data.get("value")
            if value is not None:
                self.setpoint = value
                self.affect_sensor()
        except (json.JSONDecodeError, KeyError):
            pass

    def affect_sensor(self):
        """
        Affect the sensor value based on the current actuator's value (=setpoint).
        """
        # Calculate the effect of the actuator on the sensor value
        sensor_gain = self.setpoint * self.gain
        sensor_loss = (self.sensor.value - self.equilibrium) * self.loss
        # Update sensor value
        new_sensor_value = self.sensor.value + sensor_gain - sensor_loss
        self.sensor.set_value(new_sensor_value)


class TestMessagingBasics:

    def test_sensor_can_publish_measurements(self, message_bus):
        bus = message_bus
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )

        sensor.publish_measurement()

        messages = bus.get_messages("instruments/thermocouple/temperature/measurement")
        assert len(messages) == 1, "Sensor should be able to publish measurements"

        # Verify message format
        msg = messages[0]
        data = json.loads(msg.payload)
        assert "value" in data

    def test_sensor_publishes_on_pid_setpoint(self, message_bus):
        bus = message_bus
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )

        # Publish a setpoint to trigger measurement publishing
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": 30.0})
        )
        time.sleep(0.1)

        messages = bus.get_messages("instruments/thermocouple/temperature/measurement")
        assert len(messages) == 1, "Sensor should publish measurement on setpoint"

    def test_sensor_publishes_on_set_value(self, message_bus):
        bus = message_bus
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )

        # Set a new value to trigger measurement publishing
        sensor.set_value(35.0)

        messages = bus.get_messages("instruments/thermocouple/temperature/measurement")
        assert len(messages) == 1, "Sensor should publish measurement on set_value"

        assert sensor.value == 35.0, "Sensor value should be updated"

    def test_actuator_subscribed_to_sensor_setpoint(self, message_bus):
        bus = message_bus
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )
        actuator = MockActuator("heater", "temperature", message_bus, sensor)

        # Publish a setpoint to the actuator
        bus.publish(
            "instruments/heater/temperature/setpoint", json.dumps({"value": 50.0})
        )

        # Allow some time for the message to be processed
        time.sleep(0.1)

        assert actuator.setpoint == 50.0, "Should have updated its setpoint"
        # check it called affect_sensor

        # check it called set value
        assert sensor.value != 20.0, "Sensor value should be affected by actuator"

    def test_spc_receives_sensor_setpoint(self, message_bus, mqtt_mocks, base_SPC):
        bus = message_bus
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )

        mqtt_mocks["client_class"].assert_called_once()

        # Publish a setpoint
        setpoint_payload = json.dumps({"value": 50.0})
        bus.publish("instruments/thermocouple/temperature/setpoint", setpoint_payload)

        # Allow some time for the message to be processed
        time.sleep(0.1)

        assert spc.status.sensor_setpoint == 50.0, "SPC should update setpoint"

    def test_spc_receives_sensor_measurement(self, message_bus, base_SPC):
        bus = message_bus
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )
        spc.status.sensor_setpoint = 50.0

        with patch("src.pid.PID.step") as mock_step:
            mock_step.return_value = 75.0
            # Publish a measurement
            measurement_payload = json.dumps({"value": 20.0})
            bus.publish(
                "instruments/thermocouple/temperature/measurement", measurement_payload
            )

            mock_step.assert_called_once_with(20.0, 50.0)

    def test_spc_updates_state_on_setpoint(self, message_bus, base_SPC):
        bus = message_bus
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )

        # Publish a setpoint
        setpoint_payload = json.dumps({"value": 50.0})
        bus.publish("instruments/thermocouple/temperature/setpoint", setpoint_payload)

        # Allow some time for the message to be processed
        time.sleep(0.1)

        assert spc.status.sensor_setpoint == 50.0
        assert spc.status.state == "idle"

    def test_spc_publishes_actuator_setpoint(self, message_bus, base_SPC):
        bus = message_bus
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )

        # Set a setpoint
        spc.status.sensor_setpoint = 50.0

        # Publish a measurement
        measurement_payload = json.dumps({"value": 20.0})
        bus.publish(
            "instruments/thermocouple/temperature/measurement", measurement_payload
        )

        # Allow some time for the message to be processed
        time.sleep(0.1)

        # Check that actuator setpoint was published
        messages = bus.get_messages("instruments/heater/temperature/setpoint")
        assert len(messages) >= 1, "SPC should publish actuator setpoint"


class TestControlLoop:

    def test_heartbeat_published(self, message_bus, mock_pid_time, base_SPC):
        bus = message_bus
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )

        spc.publish_heartbeat()

        messages = bus.get_messages(f"setpoint_controller/{spc.spc_id}/heartbeat")
        assert len(messages) == 1, "SPC should publish heartbeat message"
        assert json.loads(messages[0].payload) == {
            "status": {
                "state": "idle",
                "enabled": True,
                "sensor_measurement": None,
                "actuator_setpoint": None,
                "experiment_id": None,
            },
            "setpoints": {"sensor_setpoint": None},
            "config": {
                "sensor": "thermocouple/temperature",
                "actuator": "heater/temperature",
                "pid": {
                    "k_p": 1.0,
                    "k_i": 0.1,
                    "k_d": 0.05,
                    "k_aw": 0.0,
                    "k_df": 0.0,
                    "max": 100.0,
                    "min": 0.0,
                    "max_rate": None,
                },
            },
        }

    def test_reaches_setpoint(self, message_bus, mock_pid_time, base_SPC):
        bus = message_bus
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )
        actuator = MockActuator("heater", "temperature", message_bus, sensor)
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )

        # Set initial conditions
        actuator.equilibrium = 20.0
        sensor.set_value(actuator.equilibrium)
        target = 50.0

        # Set sensor setpoint
        bus.publish(
            "instruments/thermocouple/temperature/setpoint",
            json.dumps({"value": target}),
        )

        reached = wait_for_equilibrium(sensor, target, tolerance=0.01, timeout=2.0)

        assert reached, "Control loop timed out trying to reach equilibrium"

    def test_responds_to_setpoint_changes(self, message_bus, mock_pid_time, base_SPC):
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )
        actuator = MockActuator("heater", "temperature", message_bus, sensor)
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )
        bus = message_bus

        # Set initial conditions
        actuator.equilibrium = 0.0
        sensor.set_value(actuator.equilibrium)

        # First setpoint
        t1 = 30.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t1})
        )
        reached_t1 = wait_for_equilibrium(
            sensor, t1, tolerance=1.0, timeout=1.0, stop=False
        )

        # Second setpoint
        t2 = 50.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t2})
        )
        reached_t2 = wait_for_equilibrium(
            sensor, t2, tolerance=1.0, timeout=1.0, stop=False
        )

        # Third setpoint
        t3 = 10.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t3})
        )
        reached_t3 = wait_for_equilibrium(
            sensor, t3, tolerance=1.0, timeout=1.0, stop=False
        )

        assert reached_t1 and reached_t2 and reached_t3

    def test_controller_can_be_disabled_and_reenabled(
        self, message_bus, mock_pid_time, base_SPC
    ):
        sensor = MockSensor(
            "thermocouple", "temperature", message_bus, initial_value=20.0
        )
        actuator = MockActuator("heater", "temperature", message_bus, sensor)
        spc = base_SPC(
            sensor_instrument="thermocouple",
            sensor_variable="temperature",
            actuator_instrument="heater",
            actuator_variable="temperature",
        )
        bus = message_bus

        # Set initial conditions
        actuator.equilibrium = 0.0
        sensor.set_value(actuator.equilibrium)

        # First setpoint
        t1 = 30.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t1})
        )
        reached_t1 = wait_for_equilibrium(
            sensor, t1, tolerance=1.0, timeout=1.0, stop=False
        )

        # Deactivate spc
        bus.publish(
            f"setpoint_controller/{spc.spc_id}/setup", json.dumps({"enabled": False})
        )

        # Second setpoint (should be ignored)
        t2 = 50.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t2})
        )
        reached_t2 = wait_for_equilibrium(
            sensor, t2, tolerance=1.0, timeout=1.0, stop=False
        )

        assert reached_t1 and not reached_t2
        assert abs(sensor.value - t1) < 1.0, "Sensor should still be at first setpoint"

        # Reactivate spc
        bus.publish(
            f"setpoint_controller/{spc.spc_id}/setup", json.dumps({"enabled": True})
        )
        # Third setpoint
        t3 = 10.0
        bus.publish(
            "instruments/thermocouple/temperature/setpoint", json.dumps({"value": t3})
        )
        reached_t3 = wait_for_equilibrium(
            sensor, t3, tolerance=1.0, timeout=1.0, stop=False
        )
        assert reached_t3

    def test_multiple_pid_controllers_can_coexist(
        self, message_bus, mock_pid_time, base_SPC
    ):
        sensor1 = MockSensor(
            "thermocouple_1", "temperature", message_bus, initial_value=20.0
        )
        actuator1 = MockActuator("heater_1", "temperature", message_bus, sensor1)
        spc1 = base_SPC(
            sensor_instrument="thermocouple_1",
            sensor_variable="temperature",
            actuator_instrument="heater_1",
            actuator_variable="temperature",
        )

        sensor2 = MockSensor(
            "thermocouple_2", "temperature", message_bus, initial_value=20.0
        )
        actuator2 = MockActuator("heater_2", "temperature", message_bus, sensor2)
        spc2 = base_SPC(
            sensor_instrument="thermocouple_2",
            sensor_variable="temperature",
            actuator_instrument="heater_2",
            actuator_variable="temperature",
        )

        # Set different setpoints
        target1 = 40.0
        target2 = 60.0
        message_bus.publish(
            "instruments/thermocouple_1/temperature/setpoint",
            json.dumps({"value": target1}),
        )
        message_bus.publish(
            "instruments/thermocouple_2/temperature/setpoint",
            json.dumps({"value": target2}),
        )

        reached = wait_for_equilibrium(
            [sensor1, sensor2],
            [target1, target2],
            tolerance=0.1,
            timeout=2.0,
        )

        assert (
            reached[0] and reached[1]
        ), "Both control loops should reach their setpoints"

    def test_pid_parameters_affect_response(self, message_bus, mock_pid_time, base_SPC):
        # Create two systems with different gains
        sensor1 = MockSensor(
            "thermocouple_1", "temperature", message_bus, initial_value=20.0
        )
        actuator1 = MockActuator("heater_1", "temperature", message_bus, sensor1)
        spc1 = base_SPC(
            sensor_instrument="thermocouple_1",
            sensor_variable="temperature",
            actuator_instrument="heater_1",
            actuator_variable="temperature",
            k_p=1.0,
            k_i=0.1,
            k_d=0.0,
            max=100.0,
            min=0.0,
        )

        sensor2 = MockSensor(
            "thermocouple_2", "temperature", message_bus, initial_value=20.0
        )
        actuator2 = MockActuator("heater_2", "temperature", message_bus, sensor2)
        spc2 = base_SPC(
            sensor_instrument="thermocouple_2",
            sensor_variable="temperature",
            actuator_instrument="heater_2",
            actuator_variable="temperature",
            k_p=5.0,
            k_i=0.5,
            k_d=0.0,
            max=100.0,
            min=0.0,
        )

        # Set same setpoint for both
        target = 40.0
        message_bus.publish(
            "instruments/thermocouple_1/temperature/setpoint",
            json.dumps({"value": target}),
        )
        message_bus.publish(
            "instruments/thermocouple_2/temperature/setpoint",
            json.dumps({"value": target}),
        )

        reached1 = wait_for_equilibrium(sensor1, target, tolerance=0.01, timeout=2.0)
        reached2 = wait_for_equilibrium(sensor2, target, tolerance=0.01, timeout=2.0)

        # Characterize final values
        value1 = sensor1.value
        value2 = sensor2.value
        time1 = spc1.pid.t
        time2 = spc2.pid.t

        assert (
            value1 != value2 or time1 != time2
        ), "Different PID parameters should lead to different responses"
