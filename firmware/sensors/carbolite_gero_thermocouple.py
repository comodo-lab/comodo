"""
Definition of GDSP thermocouple read (left instance)
"""

# Import the BaseSensor class
from sensor import BaseSensor


@BaseSensor.register_sensor("temp_left")
class TempLeft(BaseSensor):
    host = None

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        pass

@BaseSensor.register_sensor("temp_main")
class TempMain(BaseSensor):
    host = None

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        pass

@BaseSensor.register_sensor("temp_right")
class TempRight(BaseSensor):
    host = None

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        pass
