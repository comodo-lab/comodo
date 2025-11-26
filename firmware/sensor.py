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
            print(f"Registering sensor: {sensor_name}")
            cls.sensor_map[sensor_name] = sensor
            return sensor

        return decorator

    @classmethod
    def create_sensor(cls, input_name, dummy=False):
        """
        Create the sensor based on the input name

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
        """
        Get measurement from the sensor.

        The default implementation is a dummy sensor, that moves toward the setpoint
        in steps of half the distance to the setpoint.
        If the measurement is within tolerance of the setpoint, it publishes a setpoint_reached message.

        Returns:
            float: The measurement
        """
        # Only move toward the setpoint if it is set
        if state.status["setpoint"] is not None:
            half_diff = (state.status["setpoint"] - state.measurement) / 2

            state.measurement = half_diff + state.measurement

            # If within tolerance to setpoint, publish setpoint_reached
            distance = abs(state.measurement - state.status["setpoint"])
            if distance < state.status["config"]["tolerance"]:
                state.client.publish(
                    f"sensor/{state.config['SENSOR_ID']}/setpoint_reached", "true"
                )

        return state.measurement

    def go_to_setpoint(self, setpoint):
        """
        Go to the setpoint

        The default implementation just sets the setpoint.

        Args:
            setpoint: float: The setpoint
        Returns:
            None
        """
        self.setpoint = setpoint
