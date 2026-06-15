import time as t


class PID:
    """This class implements a PID controller."""

    def __init__(
        self,
        k_p=1.0,
        k_i=0.1,
        k_d=0.05,
        k_aw=0.0,
        k_df=0.0,
        max=100.0,
        min=0.0,
        max_rate=None,
    ):
        self.healthy = True  # Health status of the PID controller
        # PID parameters
        self.k_p = k_p  # Proportional gain
        self.k_i = k_i  # Integral gain
        self.k_d = k_d  # Derivative gain
        self.k_aw = k_aw  # Anti-windup gain
        self.k_df = k_df  # Derivative filtering time constant
        # Output constraints
        self.max = max  # Maximum output
        self.min = min  # Minimum output
        self.max_rate = max_rate  # Maximum rate of change of the output
        # Current inputs
        self.measurement = None  # Current measurement of the sensor variable
        self.setpoint = None  # Desired value of the sensor variable
        self.err = None  # Current error
        self.t = None  # Current measurement time
        self.dt = None  # Time step
        # Previous states
        self.proportional = 0  # Proportional term
        self.integral = 0  # Integral term
        self.antiw = 0  # Anti-windup term
        self.derivative = 0  # Derivative term
        self.prev_t = None  # Previous measurement time
        self.prev_err = 0  # Previous error
        self.prev_deriv = 0  # Previous derivative
        self.prev_out = 0  # Previous output
        self.prev_out_sat = 0  # Previous saturated output
        # Output
        self.output = None  # PID output (Actuator setpoint)
        self.output_sat = None  # Current saturated output

        self.configurable = [
            "k_p",
            "k_i",
            "k_d",
            "k_aw",
            "k_df",
            "max",
            "min",
            "max_rate",
        ]

    def get_config(self):
        """Return the current configuration of the PID controller."""
        return {
            "k_p": self.k_p,
            "k_i": self.k_i,
            "k_d": self.k_d,
            "k_aw": self.k_aw,
            "k_df": self.k_df,
            "max": self.max,
            "min": self.min,
            "max_rate": self.max_rate,
        }

    def get_state(self, verbosity=0):
        """
        Return the current state of the PID controller.
        Inputs:
            verbosity: level of detail (0=minimal, 1=medium, 2=full)
        """
        state = {
            "healthy": self.healthy,
            "measurement": self.measurement,
            "setpoint": self.setpoint,
            "output_sat": self.output_sat,
        }
        if verbosity > 0:
            state.update(
                {
                    "k_p": self.k_p,
                    "k_i": self.k_i,
                    "k_d": self.k_d,
                    "k_aw": self.k_aw,
                    "k_df": self.k_df,
                    "max": self.max,
                    "min": self.min,
                    "max_rate": self.max_rate,
                }
            )
            if verbosity > 1:
                state.update(
                    {
                        "t": self.t,
                        "dt": self.dt,
                        "err": self.err,
                        "proportional": self.proportional,
                        "integral": self.integral,
                        "antiw": self.antiw,
                        "derivative": self.derivative,
                        "prev_err": self.prev_err,
                        "prev_t": self.prev_t,
                        "prev_deriv": self.prev_deriv,
                        "prev_out": self.prev_out,
                        "prev_out_sat": self.prev_out_sat,
                        "output": self.output,
                    }
                )
        return state

    def now(self):
        """Return the current time."""
        return t.time()

    def step(self, measurement, setpoint, time=None):
        """
        Execute a step of the PID controller.

        Inputs:
            measurement: current measurement of the sensor variable
            setpoint: desired value of the sensor variable
        """
        # Save previous states
        if self.t is not None:
            self.prev_t = self.t
        if self.prev_t is not None:
            self.prev_err = self.err
            self.prev_deriv = self.derivative
            self.prev_out = self.output
            self.prev_out_sat = self.output_sat

        # Current inputs
        self.measurement = measurement
        self.setpoint = setpoint
        self.t = self.now() if time is None else time
        if self.prev_t is not None:
            self.dt = self.t - self.prev_t
        self.err = self.setpoint - self.measurement

        # Proportional:
        self.proportional = self.k_p * self.err

        if self.dt is not None:
            # Integral:
            self.integral += self.k_i * self.err * self.dt
            # Anti-windup:
            self.antiw += self.k_aw * (self.prev_out_sat - self.prev_out) * self.dt

            ddt = self.dt + self.k_df
            if ddt > 0:
                # Derivative:
                self.derivative = self.k_d * (self.err - self.prev_err) / ddt
                # Filtered derivative:
                self.derivative += self.k_d * self.k_df * self.prev_deriv / ddt

        # Output
        self.output = self.proportional + self.integral + self.antiw + self.derivative

        # Limit output with min and max (saturation)
        if self.output > self.max:
            self.output_sat = self.max
        elif self.output < self.min:
            self.output_sat = self.min
        else:
            self.output_sat = self.output
        # Limit output rate of change
        if self.max_rate is not None:
            self.dt = self.dt if self.dt is not None else 1.0
            max_change = self.max_rate * self.dt
            if self.output_sat > (self.prev_out_sat + max_change):
                self.output_sat = self.prev_out_sat + max_change
            elif self.output_sat < (self.prev_out_sat - max_change):
                self.output_sat = self.prev_out_sat - max_change

        # Return saturated output
        return self.output_sat
