import random

class BaseSensor:
    """ Base class for all sensors

    This class is used to register all sensors and create them based on the input name.

    Attributes:
        sensor_map: dict: The map of sensor name to sensor class 
    """
    sensor_map = {}  # Map of sensor name to sensor class

    @classmethod
    def register_sensor(cls, sensor_name):
        """ Register the sensor

        Args:
            sensor_name: str: The name of the sensor

        Returns:
            function: The decorator function
        """
        
        def decorator(sensor):
            print(f"Registering sensor: {sensor_name}")
            cls.sensor_map[sensor_name] = sensor
            return sensor
        return decorator

    @classmethod
    def create_sensor(cls, input_name, dummy=False):
        """ Create the sensor based on the input name

        Args:
            input_name: str: The name of the sensor
            dummy: bool: Whether to create a dummy sensor

        Returns:
            BaseSensor: The sensor object

        Raises:
            ValueError: If the input name is invalid
        """

        # If dummy is specified, return the base class
        if dummy:
            return cls()

        # Otherwise, get the sensor from the map
        print(f"Creating sensor: {input_name}")
        sensor = cls.sensor_map.get(input_name)
        if sensor:
            return sensor()
        else:
            raise ValueError(f"Invalid sensor name: {input_name}")

    def get_measurement(self, state):
        """ Get the measurement

        Returns:
            float: The measurement
        """
        
        # Since this is a dummys sensor, move a little toward the setpoint
        setpoint = state.status['setpoint']
        value = state.measurement

        difference = setpoint - value
        half_diff = difference / 2
        
        measurement = half_diff + value

        distance = abs(measurement - state.status["setpoint"])
        if distance < state.status["config"]["tolerance"]:
            state.client.publish(f"sensor/{state.config['SENSOR_ID']}/setpoint_reached", "true")

        state.measurement = measurement
        return measurement
    
@BaseSensor.register_sensor("distance")
class Distance(BaseSensor):
    def get_measurement(self):
        """ Get the measurement from a distance sensor

        Returns:
            float: The measurement
        """
        
        return "The distance is x"

    def go_to_setpoint(self, setpoint):
        """ Go to the setpoint

        Args:
            setpoint: float: The setpoint

        Returns:
            None
        """
        pass

@BaseSensor.register_sensor("temp_main")
class TempMain(BaseSensor):
    host = None
    measurement = 25.0
    setpoint = 25.0

    def __init__(self):
        return

    # def get_measurement(self, state):
    #     """ Get the measurement

    #     Returns:
    #         float: A random temperature value for testing purposes
    #     """
        # value = float(self.measurement)
        # setpoint = float(self.setpoint)
        # tolerance = float(state.status["config"]["tolerance"])

        # # Randomness
        # vary_by = random.randrange(-1, 1)

        # # Move a little toward the setpoint
        # difference = setpoint - value
        # half_diff = max(difference/2, 5)

        # measurement = half_diff + value + vary_by

        # distance = abs(value - setpoint)
        # if distance < tolerance:
        #     state.client.publish(f"sensor/{state.config['SENSOR_ID']}/setpoint_reached", "true")

        # state.measurement = measurement
        # return measurement



    def go_to_setpoint(self, setpoint):
        """ Go to the setpoint
        Args:
            setpoint: float: The setpoint
        Returns:
            None
        """
        self.setpoint = setpoint

    def set_config(self, config):
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

@BaseSensor.register_sensor("temp_left")
class TempLeft(BaseSensor):
    host = None

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass
