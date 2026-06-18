import pytest
import time as t

from src.pid import PID


class TestPIDInitialization:

    def test_initialization_defaults(self):
        pid = PID()

        assert pid.k_p == 1.0
        assert pid.k_i == 0.1
        assert pid.k_d == 0.05
        assert pid.k_aw == 0.0
        assert pid.k_df == 0.0
        assert pid.max == 100.0
        assert pid.min == 0.0
        assert pid.max_rate == None

    def test_initialization_sets_parameters(self):
        pid = PID(
            k_p=2.0,
            k_i=0.5,
            k_d=0.1,
            k_aw=0.3,
            k_df=0.2,
            max=50.0,
            min=-10.0,
            max_rate=5.0,
        )

        assert pid.k_p == 2.0
        assert pid.k_i == 0.5
        assert pid.k_d == 0.1
        assert pid.k_aw == 0.3
        assert pid.k_df == 0.2
        assert pid.max == 50.0
        assert pid.min == -10.0
        assert pid.max_rate == 5.0

    def test_initial_state_is_zero(self):
        pid = PID()

        assert pid.healthy is True
        assert pid.err is None
        assert pid.t is None
        assert pid.dt is None
        assert pid.proportional == 0
        assert pid.integral == 0
        assert pid.antiw == 0
        assert pid.derivative == 0
        assert pid.prev_t is None
        assert pid.prev_err == 0
        assert pid.prev_deriv == 0
        assert pid.prev_out == 0
        assert pid.prev_out_sat == 0
        assert pid.output is None
        assert pid.output_sat is None


class TestGetConfig:

    def test_returns_all_configurable(self):
        pid = PID()

        config = pid.get_config()

        assert list(config.keys()) == list(pid.configurable)
        assert config == {
            "k_p": pid.k_p,
            "k_i": pid.k_i,
            "k_d": pid.k_d,
            "k_aw": pid.k_aw,
            "k_df": pid.k_df,
            "max": pid.max,
            "min": pid.min,
            "max_rate": pid.max_rate,
        }


class TestGetState:

    def test_get_state_basic(self, rand_pid):
        state = rand_pid.get_state()

        assert state == {
            "healthy": True,
            "measurement": rand_pid.measurement,
            "setpoint": rand_pid.setpoint,
            "output_sat": None,
        }

    def test_get_state_verbose(self, rand_pid):
        state = rand_pid.get_state(verbosity=1)

        assert state == {
            "healthy": True,
            "measurement": rand_pid.measurement,
            "setpoint": rand_pid.setpoint,
            "output_sat": None,
            "k_p": rand_pid.k_p,
            "k_i": rand_pid.k_i,
            "k_d": rand_pid.k_d,
            "k_aw": rand_pid.k_aw,
            "k_df": rand_pid.k_df,
            "max": rand_pid.max,
            "min": rand_pid.min,
            "max_rate": rand_pid.max_rate,
        }

    def test_get_state_more_verbose(self, rand_pid):
        state = rand_pid.get_state(verbosity=2)
        assert state == {
            "healthy": True,
            "measurement": rand_pid.measurement,
            "setpoint": rand_pid.setpoint,
            "output_sat": None,
            "k_p": rand_pid.k_p,
            "k_i": rand_pid.k_i,
            "k_d": rand_pid.k_d,
            "k_aw": rand_pid.k_aw,
            "k_df": rand_pid.k_df,
            "max": rand_pid.max,
            "min": rand_pid.min,
            "max_rate": rand_pid.max_rate,
            "err": rand_pid.err,
            "t": rand_pid.t,
            "dt": rand_pid.dt,
            "proportional": rand_pid.proportional,
            "integral": rand_pid.integral,
            "antiw": rand_pid.antiw,
            "derivative": rand_pid.derivative,
            "prev_t": rand_pid.prev_t,
            "prev_err": rand_pid.prev_err,
            "prev_deriv": rand_pid.prev_deriv,
            "prev_out": rand_pid.prev_out,
            "prev_out_sat": rand_pid.prev_out_sat,
            "output": rand_pid.output,
        }


class TestProportionalControl:

    def test_positive_error_gives_positive_output(self):
        pid = PID()
        output = pid.step(measurement=40.0, setpoint=50.0)

        assert output > 0

    def test_negative_error_gives_negative_output(self):
        pid = PID(min=-100.0)  # Allow negative outputs
        output = pid.step(measurement=60.0, setpoint=50.0)

        assert output < 0

    def test_zero_error_with_no_history_gives_zero_output(self):
        pid = PID()
        output = pid.step(measurement=50.0, setpoint=50.0)

        assert output == 0.0

    def test_k_p_scaling(self):
        pid_low = PID(k_p=0.5)
        pid_high = PID(k_p=2.0)

        output_low = pid_low.step(measurement=40.0, setpoint=50.0)
        output_high = pid_high.step(measurement=40.0, setpoint=50.0)

        assert output_high > output_low, "Higher k_p should give larger output"


class TestIntegralControl:

    def test_accumulates_over_time(self):
        pid = PID(k_i=100.0)
        states = []
        for i in range(5):
            output = pid.step(measurement=40.0, setpoint=50.0, time=i / 10)
            states.append(pid.get_state(verbosity=2))
        for i in range(4):
            assert states[i]["integral"] <= states[i + 1]["integral"]

    def test_does_not_accumulate_with_zero_k_i(self):
        pid = PID(k_i=0.0, k_aw=0.0)
        outputs = []
        states = []
        for i in range(5):
            output = pid.step(measurement=40.0, setpoint=50.0, time=i / 10)
            outputs.append(output)
            states.append(pid.get_state(verbosity=2))

        for i in range(5):
            assert outputs[0] == outputs[i]
            assert states[0]["integral"] == states[i]["integral"]

    def test_responds_to_sign_change(self):
        pid = PID(k_i=100.0)
        states = []
        # Positive error
        for i in range(5):
            _ = pid.step(measurement=40.0, setpoint=50.0, time=i / 10)
            states.append(pid.get_state(verbosity=2))
        # Negative error
        for i in range(5):
            _ = pid.step(measurement=60.0, setpoint=50.0, time=i + 5 / 10)
            states.append(pid.get_state(verbosity=2))
        # Integral should decrease with negative error
        for i in range(4):
            assert states[4 + i]["integral"] >= states[4 + i + 1]["integral"]

    def test_k_i_scaling(self):
        pid_low = PID(k_i=0.05)
        pid_high = PID(k_i=0.2)

        states = {"low": [], "high": []}
        for pid, name in (pid_low, "low"), (pid_high, "high"):
            for i in range(5):
                pid.step(measurement=40.0, setpoint=50.0, time=i / 10)
                states[name].append(pid.integral)

        for i in range(1, 5):
            assert (
                states["high"][i] > states["low"][i]
            ), "Higher k_i should give larger integral term"


class TestDerivativeControl:

    def test_can_handle_dt_zero(self):
        pid = PID()
        assert pid.k_df == 0.0
        outputs = []
        states = []
        for i in range(5):
            output = pid.step(measurement=40.0, setpoint=50.0, time=123)
            outputs.append(output)
            states.append(pid.get_state(verbosity=2))

        for i in range(5):
            if i > 0:
                assert states[i]["dt"] == 0
            assert outputs[0] == outputs[i]
            assert states[i]["derivative"] == 0

    def test_is_negative_when_approaching_setpoint_from_below(self):
        pid = PID()
        states = []
        for i in range(5):
            _ = pid.step(measurement=i * 10, setpoint=50, time=i / 10)
            states.append(pid.get_state(verbosity=2))
        for i in range(1, 5):
            assert states[i]["derivative"] < 0

    def test_is_positive_when_approaching_setpoint_from_above(self):
        pid = PID()
        states = []
        for i in range(5):
            _ = pid.step(measurement=100 - i * 10, setpoint=50, time=i / 10)
            states.append(pid.get_state(verbosity=2))

        for i in range(1, 5):
            assert states[i]["derivative"] > 0

    def test_derivative_responds_to_rate_of_change(self):
        pid = PID()
        states = []
        for i in range(5):
            # Step through errors with increasing rate: 0 -> 10 -> 30...
            _ = pid.step(measurement=i * i, setpoint=50, time=i / 10)
            states.append(pid.get_state(verbosity=2))

        for i in range(1, 4):
            assert states[i]["derivative"] > states[i + 1]["derivative"]

    def test_k_d_scaling(self):
        pid_low = PID(k_d=0.05)
        pid_high = PID(k_d=0.2)

        states = {"low": [], "high": []}
        for pid, name in (pid_low, "low"), (pid_high, "high"):
            for i in range(5):
                pid.step(measurement=i * i, setpoint=50.0, time=i / 10)
                states[name].append(abs(pid.derivative))

        for i in range(1, 5):
            assert (
                states["high"][i] > states["low"][i]
            ), "Higher k_d should give larger derivative term"


class TestAntiWindup:

    def test_anti_windup_limits_integral_growth(self):
        steps = 20
        pid = PID(k_p=1.0, k_i=1.0, k_d=0.0, k_aw=0.5, max=10.0)

        # Saturate output and continue to drive integral
        states = []
        for i in range(steps):
            pid.step(measurement=0.0, setpoint=100.0, time=i / 10)
            states.append(pid.get_state(2))

        # Integral should decrease wind-up rate
        prev_windup = 100.0
        tot_int = [states[i]["integral"] + states[i]["antiw"] for i in range(steps)]
        for i in range(1, steps):
            assert states[i]["output_sat"] == 10.0
            windup = tot_int[i] - tot_int[i - 1]
            assert windup < prev_windup
            prev_windup = windup

    def test_k_aw_scaling(self):
        steps = 20
        pid_low = PID(k_i=1.0, k_aw=0.1)
        pid_high = PID(k_i=1.0, k_aw=0.5)

        tot_int = {"low": [], "high": []}
        for pid, name in (pid_low, "low"), (pid_high, "high"):
            for i in range(steps):
                pid.step(measurement=0.0, setpoint=100.0, time=i / 10)
                tot_int[name].append(pid.integral + pid.antiw)

        for i in range(2, steps):
            assert (
                tot_int["high"][i] < tot_int["low"][i]
            ), "Higher k_aw should reduce integral wind-up more"


class TestDerivativeFiltering:

    def test_filters_smooths_derivative(self):
        pid_u = PID(
            k_p=0.0,
            k_i=0.0,
            k_d=0.1,
            k_df=0.0,  # Unfiltered derivative
            min=-100.0,
        )
        pid_f = PID(
            k_p=0.0,
            k_i=0.0,
            k_d=0.1,
            k_df=0.05,  # Filtered derivative
            min=-100.0,
        )

        outputs = {"filtered": [], "unfiltered": []}
        for pid, name in (pid_f, "filtered"), (pid_u, "unfiltered"):
            for i in range(6):
                m = 50.0 + (-1) ** i * 5 * i
                out = pid.step(measurement=m, setpoint=50.0, time=i / 10)
                outputs[name].append(out)

        for i in range(1, 5):
            dev_change_f = abs(outputs["filtered"][i] - outputs["filtered"][i - 1])
            dev_change_u = abs(outputs["unfiltered"][i] - outputs["unfiltered"][i - 1])
            assert dev_change_f < dev_change_u

    def test_k_df_scaling(self):
        pid_low = PID(k_p=0.0, k_i=0.0, k_d=0.1, k_df=0.01, min=-100.0)
        pid_high = PID(k_p=0.0, k_i=0.0, k_d=0.1, k_df=0.05, min=-100.0)

        outputs = {"low": [], "high": []}
        for pid, name in (pid_high, "high"), (pid_low, "low"):
            for i in range(6):
                m = 50.0 + (-1) ** i * 5 * i
                out = pid.step(measurement=m, setpoint=50.0, time=i / 10)
                outputs[name].append(out)

        for i in range(1, 5):
            dev_change_f = abs(outputs["high"][i] - outputs["high"][i - 1])
            dev_change_u = abs(outputs["low"][i] - outputs["low"][i - 1])
            assert (
                dev_change_f < dev_change_u
            ), "Higher k_df should give smoother derivative"


class TestOutputLimits:

    def test_output_not_unnecessarily_limited(self):
        max_rate = 5.0
        pid = PID(max=100.0, min=-100.0, max_rate=max_rate)

        # small error should not be rate-limited
        out_1 = pid.step(measurement=49.0, setpoint=50.0)
        assert out_1 < max_rate
        assert pid.output <= pid.output_sat
        assert out_1 == pid.output_sat

    def test_output_max(self):
        pid = PID(max=50.0)

        out = pid.step(measurement=0.0, setpoint=100.0)

        assert pid.output > 50
        assert pid.output_sat == 50.0
        assert out == pid.output_sat

    def test_output_min(self):
        pid = PID(min=-10.0)

        out = pid.step(measurement=100.0, setpoint=0.0)

        assert pid.output < -10.0
        assert pid.output_sat == -10.0
        assert out == pid.output_sat

    def test_output_max_rate_pos(self):
        max_rate = 5.0
        pid = PID(max_rate=max_rate)

        out = pid.step(measurement=0.0, setpoint=50.0)

        assert pid.output > max_rate
        assert pid.output_sat == max_rate
        assert out == pid.output_sat

    def test_output_max_rate_neg(self):
        max_rate = 5.0
        pid = PID(min=-100, max_rate=max_rate)

        out = pid.step(measurement=50.0, setpoint=0.0)

        assert pid.output < -max_rate
        assert pid.output_sat == -max_rate
        assert out == pid.output_sat
