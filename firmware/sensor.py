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

    # Base behaviour, not to be overriden
    def _get_measurement(self, state):
        if not state.config["SIMULATE"] == "True":
            return self.get_measurement(self, state)
        else:
            if state.status['setpoint'] is None:
                return 0

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
        
    # Actual behaviour, to be overriden
    def get_measurement(self, state):
        """
        Get measurement from the sensor.
        """
        pass
    
    def _go_to_setpoint(self, setpoint):
        """
        Go to the setpoint

        The default implementation just sets the setpoint.

        Args:
            setpoint: float: The setpoint
        Returns:
            None
        """
        if not state.config["SIMULATE"] == "True":
            return self.go_to_stepoint(self, setpoint)
        else:
            self.setpoint = setpoint

    # Actual behaviour to be overriden
    def go_to_setpoint(self, setpoint):
        """
        Go to the setpoint
        """
        pass
