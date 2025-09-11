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
