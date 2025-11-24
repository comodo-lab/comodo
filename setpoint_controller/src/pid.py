class PID:
    """This class implements a PID controller."""

    def __init__(
        self,
        id,
        sensor,
        actuator,
        Kp=1.0,
        Ki=0.1,
        Kd=0.05,
    ):
        self.healthy = True  # Health status of the PID controller
        self.id = id  # Name for the PID controller
        self.sensor = sensor  # Name of the sensor to read
        self.actuator = actuator  # Name of the actuator to control
        self.Kp = Kp  # Proportional gain
        self.Ki = Ki  # Integral gain
        self.Kd = Kd  # Derivative gain
        self.setpoint = None  # Current setpoint

    def step(self, measurement, setpoint):
        """Execute a step of the PID controller.

        Inputs:
            measurement: current measurement of the process variable
            setpoint: desired value of the process variable
        """

        return 42

    def get_state(self):
        """
        Return the current state of the PID controller.
        """
        state = {
            "healthy": self.healthy,
            "id": self.id,
            "p": self.Kp,
            "i": self.Ki,
            "d": self.Kd,
            "setpoint": self.setpoint,
        }
        return state
