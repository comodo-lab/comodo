class BaseSensor:
    """
    Base class for all sensors

    This class is used to register all sensors and create them based on the input name.

    Attributes:
        sensor_map: dict: The map of sensor name to sensor class
    """

    sensor_map = {}  # Map of sensor name to sensor class

    @classmethod
    def register_sensor(cls, sensor_name):
        """
        Register the sensor

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
        """
        Create the sensor based on the input name

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

    def __init__(self):
        """
        Initialisations that are safe when either hardware or simulation is used

        To be extended by subclasses, if needed.
        """
        
        pass

    def initialise(self):
        """
        Initialisations that are only safe when hardware is used
        """
        pass

    def get_measurement(self, state):
        """
        Get a measurement from the sensor
        """
        raise NotImplemented

    def simulate_get_measurement(self, state):
        """
        Get a simulated measurement, default implementation
        """

        setpoint = state.status['setpoint']
        value = state.measurement
        
        if setpoint is None:
            return 0
        
        difference = setpoint - value
        half_diff = difference / 2
            
        measurement = half_diff + value
        
        distance = abs(measurement - state.status["setpoint"])
        if distance < state.status["config"]["tolerance"]:
            state.client.publish(f"sensor/{state.config['SENSOR_ID']}/setpoint_reached", "true")
            
        state.measurement = measurement
        return measurement

    def go_to_setpoint(self, setpoint):
        """
        Go to the setpoint
        """
        raise NotImplemented
    
    def simulate_go_to_setpoint(self, setpoint):
        """
        Go to the setpoint 
        """
        pass
