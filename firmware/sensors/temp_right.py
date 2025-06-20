"""
Dummy sensor for the right temperature sensor.
This sensor is used to test the system without a real sensor.
"""


# Import the BaseSensor class
from sensor import BaseSensor

@BaseSensor.register_sensor("temp_right")
class TempRight(BaseSensor):
    host = None

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass
