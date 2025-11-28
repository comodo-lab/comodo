"""
Dummy sensor for a temperature sensor.
This sensor is used to test the system without a real sensor.
"""

# Import the BaseSensor class
from sensor import BaseSensor

import random


@BaseSensor.register_sensor("test_sensor")
class TestSensor(BaseSensor):

    host = None
    measurement = 25.0
    setpoint = 25.0

    def __init__(self):
        return

    def get_measurement(self, state):
        """Get the measurement

        Returns:
            float: A random temperature value for testing purposes
        """
        value = float(self.measurement)
        setpoint = float(self.setpoint)
        tolerance = float(state.status["config"]["tolerance"])

        # Randomness
        vary_by = random.randrange(-1, 1)

        # Move a little toward the setpoint
        difference = setpoint - value
        half_diff = max(difference / 2, 5)

        measurement = half_diff + value + vary_by

        distance = abs(value - setpoint)
        if distance < tolerance:
            state.client.publish(
                f"sensor/{state.config['SENSOR_ID']}/setpoint_reached", "true"
            )

        state.measurement = measurement
        return measurement

    def go_to_setpoint(self, setpoint):
        """Go to the setpoint
        Args:
            setpoint: float: The setpoint
        Returns:
            None
        """
        self.setpoint = setpoint

    def set_config(self, config):
        pass
