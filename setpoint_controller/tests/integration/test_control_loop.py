"""
Integration tests for the complete control loop.

These tests simulate the full control loop with mock sensor, actuator, and controller
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
                    f"Sensor: {sensor.name}, Error: {abs_error=}, Reached: {step_count[i]}",
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

    def __init__(self, name: str, bus: InMemoryMessageBus, initial_value: float = 20.0):
        self.name = name
        self.bus = bus
        self.value = initial_value
        self.running = True
        self.thread = None

        # Subscribe to setpoint messages (trigger measurement publishing)
        self.bus.subscribe(f"pid/*", self.publish_measurement)

    def stop(self):
        """Stop reacting to setpoint changes."""
        self.running = False

    def publish_measurement(self, topic: str = None, payload: str = None):
        """
        Publishes the sensor's current value.
        """
        payload = json.dumps({"value": self.value})
        self.bus.publish(f"measurement/{self.name}", payload)

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
        name: str,
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
        self.name = name
        self.bus = bus
        self.sensor = sensor
        self.setpoint = None
        self.thread = None
        # Subscribe to setpoint messages
        self.bus.subscribe(f"instrument/{self.name}/setpoint", self.on_setpoint)

    def on_setpoint(self, topic: str, msg):
        """
        Receives a setpoint and triggers effect on sensor.

        The actuator is assumed to reach its own setpoint immediately,
        that is, the actuator value is assumed to be equal to its setpoint.
        """
        try:
            data = load_message(msg)
            if self.name in data:
                self.setpoint = data[self.name]
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
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)

        sensor.publish_measurement()

        messages = bus.get_messages("measurement/temperature")
        assert len(messages) == 1, "Sensor should be able to publish measurements"

        # Verify message format
        msg = messages[0]
        data = json.loads(msg.payload)
        assert "value" in data

    def test_sensor_publishes_on_pid_setpoint(self, message_bus):
        bus = message_bus
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)

        # Publish a setpoint to trigger measurement publishing
        bus.publish("pid/whatever", json.dumps({"setpoint": 30.0}))
        time.sleep(0.1)

        messages = bus.get_messages("measurement/temperature")
        assert len(messages) == 1, "Sensor should publish measurement on PID setpoint"

    def test_sensor_publishes_on_set_value(self, message_bus):
        bus = message_bus
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)

        # Set a new value to trigger measurement publishing
        sensor.set_value(35.0)

        messages = bus.get_messages("measurement/temperature")
        assert len(messages) == 1, "Sensor should publish measurement on set_value"

        assert sensor.value == 35.0, "Sensor value should be updated"

    def test_actuator_subscribed_to_sensor_setpoint(self, message_bus):
        bus = message_bus
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)
        actuator = MockActuator("heater", message_bus, sensor)

        # Publish a setpoint to the actuator
        bus.publish("instrument/heater/setpoint", json.dumps({"heater": 50.0}))

        # Allow some time for the message to be processed
        time.sleep(0.1)

        assert actuator.setpoint == 50.0, "Should have updated its setpoint"
        # check it called affect_sensor

        # check it called set value
        assert sensor.value != 20.0, "Sensor value should be affected by actuator"

    def test_controller_receives_sensor_setpoint(
        self, message_bus, mqtt_mocks, base_SPC
    ):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")

        mqtt_mocks["client_class"].assert_called_once()

        # Publish a setpoint
        setpoint_payload = json.dumps({"temperature": 50.0})
        bus.publish("instrument/temperature/setpoint", setpoint_payload)

        # Allow some time for the message to be processed
        time.sleep(0.1)

        assert controller.pid.setpoint == 50.0, "Controller should update setpoint"

    def test_controller_receives_sensor_measurement(self, message_bus, base_SPC):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")
        controller.pid.setpoint = 50.0

        with patch("src.pid.PID.step") as mock_step:
            mock_step.return_value = 75.0
            # Publish a measurement
            measurement_payload = json.dumps({"value": 20.0})
            bus.publish("measurement/temperature", measurement_payload)

            mock_step.assert_called_once_with(20.0, 50.0)

    def test_controller_publishes_when_ready(self, message_bus, base_SPC):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")

        messages = bus.get_messages(f"{controller.pid.id}/*")
        assert len(messages) == 1, "Controller should publish ready message"
        topic = messages[0].topic
        message = json.loads(messages[0].payload.decode("utf-8"))
        assert topic == f"{controller.pid.id}/setpoint"
        assert message == {"temperature": None}

    def test_controller_publishes_when_setpoint_set(self, message_bus, base_SPC):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")

        # Publish a setpoint
        setpoint_payload = json.dumps({"temperature": 50.0})
        bus.publish("instrument/temperature/setpoint", setpoint_payload)

        # Allow some time for the message to be processed
        time.sleep(0.1)

        messages = bus.get_messages(f"{controller.pid.id}/*")
        assert len(messages) == 2, "Expected one null and one with 50"
        topic = messages[1].topic
        message = json.loads(messages[1].payload.decode("utf-8"))
        assert topic == f"{controller.pid.id}/setpoint"
        assert message == {"temperature": 50.0}

    def test_controller_publishes_actuator_setpoint(self, message_bus, base_SPC):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")

        # Set a setpoint
        controller.pid.setpoint = 50.0

        # Publish a measurement
        measurement_payload = json.dumps({"value": 20.0})
        bus.publish("measurement/temperature", measurement_payload)

        # Allow some time for the message to be processed
        time.sleep(0.1)

        # Check that actuator setpoint was published
        messages = bus.get_messages("instrument/heater/setpoint")
        assert len(messages) >= 1, "Controller should publish actuator setpoint"


class TestControlLoop:

    def test_heartbeat_published(self, message_bus, mock_pid_time, base_SPC):
        bus = message_bus
        controller = base_SPC(sensor="temperature", actuator="heater")

        controller.publish_heartbeat()

        messages = bus.get_messages(f"heartbeat/{controller.pid.id}")
        assert len(messages) == 1, "Controller should publish heartbeat message"
        assert messages[0].payload.decode("utf-8") == json.dumps(
            {
                "name": "pid_temperature__heater",
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
        )
        # assert False

    def test_reaches_setpoint(self, message_bus, mock_pid_time, base_SPC):
        bus = message_bus
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)
        actuator = MockActuator("heater", message_bus, sensor)
        controller = base_SPC(sensor="temperature", actuator="heater")

        # Set initial conditions
        actuator.equilibrium = 20.0
        sensor.set_value(actuator.equilibrium)
        target = 50.0

        # Set sensor setpoint
        bus.publish("instrument/temperature/setpoint", json.dumps({"temperature": target}))

        reached = wait_for_equilibrium(sensor, target, tolerance=0.01, timeout=2.0)

        assert reached, "Control loop timed out trying to reach equilibrium"

    def test_responds_to_setpoint_changes(self, message_bus, mock_pid_time, base_SPC):
        sensor = MockSensor("temperature", message_bus, initial_value=20.0)
        actuator = MockActuator("heater", message_bus, sensor)
        controller = base_SPC(sensor="temperature", actuator="heater")
        bus = message_bus

        # Set initial conditions
        actuator.equilibrium = 0.0
        sensor.set_value(actuator.equilibrium)

        # First setpoint
        t1 = 30.0
        bus.publish("instrument/temperature/setpoint", json.dumps({"temperature": t1}))
        reached_t1 = wait_for_equilibrium(
            sensor, t1, tolerance=1.0, timeout=1.0, stop=False
        )

        # Second setpoint
        t2 = 50.0
        bus.publish("instrument/temperature/setpoint", json.dumps({"temperature": t2}))
        reached_t2 = wait_for_equilibrium(
            sensor, t2, tolerance=1.0, timeout=1.0, stop=False
        )

        # Third setpoint
        t3 = 10.0
        bus.publish("instrument/temperature/setpoint", json.dumps({"temperature": t3}))
        reached_t3 = wait_for_equilibrium(
            sensor, t3, tolerance=1.0, timeout=1.0, stop=False
        )

        assert reached_t1 and reached_t2 and reached_t3

    def test_multiple_pid_controllers_can_coexist(
        self, message_bus, mock_pid_time, base_SPC
    ):
        sensor1 = MockSensor("temp1", message_bus, initial_value=20.0)
        actuator1 = MockActuator("heater1", message_bus, sensor1)
        controller1 = base_SPC(sensor="temp1", actuator="heater1")

        sensor2 = MockSensor("temp2", message_bus, initial_value=20.0)
        actuator2 = MockActuator("heater2", message_bus, sensor2)
        controller2 = base_SPC(sensor="temp2", actuator="heater2")

        # Set different setpoints
        target1 = 40.0
        target2 = 60.0
        message_bus.publish("instrument/temp1/setpoint", json.dumps({"temp1": target1}))
        message_bus.publish("instrument/temp2/setpoint", json.dumps({"temp2": target2}))

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
        sensor1 = MockSensor("temp1", message_bus, initial_value=20.0)
        actuator1 = MockActuator("heater1", message_bus, sensor1)
        controller1 = base_SPC(
            sensor="temp1",
            actuator="heater1",
            k_p=1.0,
            k_i=0.1,
            k_d=0.0,
            max=100.0,
            min=0.0,
        )

        sensor2 = MockSensor("temp2", message_bus, initial_value=20.0)
        actuator2 = MockActuator("heater2", message_bus, sensor2)
        controller2 = base_SPC(
            sensor="temp2",
            actuator="heater2",
            k_p=5.0,
            k_i=0.5,
            k_d=0.0,
            max=100.0,
            min=0.0,
        )

        # Set same setpoint for both
        target = 40.0
        message_bus.publish("instrument/temp1/setpoint", json.dumps({"temp1": target}))
        message_bus.publish("instrument/temp2/setpoint", json.dumps({"temp2": target}))

        reached1 = wait_for_equilibrium(sensor1, target, tolerance=0.01, timeout=2.0)
        reached2 = wait_for_equilibrium(sensor2, target, tolerance=0.01, timeout=2.0)

        # Characterize final values
        value1 = sensor1.value
        value2 = sensor2.value
        time1 = controller1.pid.t
        time2 = controller2.pid.t

        assert (
            value1 != value2 or time1 != time2
        ), "Different PID parameters should lead to different responses"
