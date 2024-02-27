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
            cls.sensor_map[sensor_name] = sensor
            return sensor
        return decorator

    @classmethod
    def create_sensor(cls, input_name):
        """ Create the sensor based on the input name

        Args:
            input_name: str: The name of the sensor

        Returns:
            BaseSensor: The sensor object

        Raises:
            ValueError: If the input name is invalid
        """
        
        sensor = cls.sensor_map.get(input_name)
        if sensor:
            return sensor()
        else:
            raise ValueError(f"Invalid sensor name: {input_name}")

    def get_measurement(self):
        """ Get the measurement

        Returns:
            float: The measurement
        """
        
        print("BaseSensor is not a sensor!")
        return None

    
@BaseSensor.register_sensor("dummy")
class Dummy(BaseSensor):
    def get_measurement(self):
        """ Get the measurement from a dummy sensor

        Returns:
            float: The measurement
        """
        
        # Get a random value for now
        measurement = random.random()
        return measurement

    
@BaseSensor.register_sensor("microepsilon")
class MicroEpsilon(BaseSensor):
    def get_measurement(self):
        """ Get the measurement from a micro epsilon sensor

        Returns:
            float: The measurement
        """
        
        return "MicroEpsilon way of getting x"

