# Setpoint Controller

The setpoint controller works with a PID (Proportional-Integral-Derivative) feedback loop,
with optional [anti-windup](#anti_windup) and [derivative filtering](#derivative_filtering).

- [Setpoint Controller](#setpoint-controller)
  - [Configuration](#configuration)
    - [MQTT Topics](#mqtt-topics)
  - [Operation](#operation)

## Configuration

The setpoint controller is configured with an `external_sensor`, PID parameters, a `target` actuator, and its defined limits.

Configuration is done via environment variables.

In its simplest form, the following environment variables are required:
- `MQTT_HOST`: hostname or IP address of your MQTT broker.
- `MQTT_USER`: username for the MQTT broker.
- `MQTT_PASS`: password for the MQTT broker.
- `SENSOR`: The variable name of the external sensor to be used for feedback.
- `ACTUATOR`: The variable name of the target actuator to be controlled.

If only the above variables are defined, the controller will operate without anti-windup and derivative filtering,
it will use default PID parameters ($k_p$=1.0, $k_i$=0.1, $k_d$=0.05),
and set the actuator limits at $u_{min}$=0 and $u_{max}$=100, with unlimited rate of change.

Additional optional environment variables include:
- `HEARTBEAT_INTERVAL`: Interval (in seconds) at which the controller publishes its health state. $\textcolor{#999999}{\small{\text{ Default: 1.0 s. }}}$
- `K_P`: Proportional gain. $\textcolor{#999999}{\small{\text{ Default: 1.0. }}}$
- `K_I`: Integral gain. $\textcolor{#999999}{\small{\text{ Default: 0.1. }}}$
- `K_D`: Derivative gain. $\textcolor{#999999}{\small{\text{ Default: 0.05. }}}$
- `K_AW`: Anti-windup gain. $\textcolor{#999999}{\small{\text{ Default: 0 (disabled). }}}$
- `K_DF`: Derivative filtering time constant. $\textcolor{#999999}{\small{\text{ Default: 0 (disabled). }}}$
- `OUT_MIN`: Minimum limit for the actuator. $\textcolor{#999999}{\small{\text{ Default: 0. }}}$
- `OUT_MAX`: Maximum limit for the actuator. $\textcolor{#999999}{\small{\text{ Default: 100. }}}$
- `MAX_RATE`: Maximum rate of change for the actuator. $\textcolor{#999999}{\small{\text{ Default: None (unlimited). }}}$

### MQTT Topics
The controller subscribes to the following MQTT topics:
- `sensors/SENSOR/setpoint`: The desired setpoint for the external sensor.
- `measurement/SENSOR`: The current measurements from the external sensor.
- `setpoint_controllers/SPC_ID/configure`: Enables/disables the controller, sets its `experiment_id`, or updates its `pid` parameters.
  PID parameters cannot be changed while an experiment is running.
And publishes to:
- `heartbeat/pid/SENSOR__ACTUATOR`: The health state of the PID controller.
- `pid/SENSOR__ACTUATOR/setpoint`: When the PID controller's setpoint is updated (or None, on startup).
- `sensor/ACTUATOR/setpoint`: The computed control signal for the target
- `error/pid/SENSOR__ACTUATOR`: If there are any errors in the PID controller.

## Operation
It uses the *setpoint* of the defined `external_sensor`, as well as its *measurements* to compute the *error* $e(t)$.
This error is then used, in combination with the [PID parameters](#pid_parameters), to compute the *output variable* $u(t)$.
The output variable is then *[saturated](#saturation)*, that is limited to the actuator's [defined limits](#saturation).

$$
u(t) = k_p  e(t) +
        k_i  \sum_{t} e(t)dt +
        \textcolor{#dd3333}{ k_{aw}  \sum_{t} (u_{s}(t')-u(t'))dt } +
        k_d  \left( \frac{e(t)-e(t')}{dt \textcolor{#00aadd}{ + k_{df}}} +
        \textcolor{#00aadd}{ k_{df}  \frac{u'(t')}{dt + k_{df}} } \right)
$$
Where:
- $t$, $t'$ and $dt$ are the current time, the time in the previous step, and the time difference between them ($dt=t-t'$), respectively.
- $e(t)$ is the error at time $t$, defined as the difference between the setpoint and the measurement.
- **$k_p$**, **$k_i$**, **$k_d$** are the PID parameters.
  <details id=pid_parameters><summary>What do each of these do?</summary>

    - $k_p$ (Proportional): Determines the reaction to the current error. A higher value means a stronger reaction to the current error.
    - $k_i$ (Integral): Determines the reaction based on the accumulation of past errors. It helps eliminate steady-state errors but can lead to overshoot if set too high.
    - $k_d$ (Derivative): Determines the reaction based on the rate of change of the error. It helps to dampen the system's response and reduce overshoot.
  </details>
- **$k_{aw}$** controls the anti-windup term (red). If set to 0, anti-windup is disabled.
  <details id=anti_windup><summary>What is anti-windup?</summary>

    Anti-windup is a technique used to prevent the integral term from accumulating excessively when the actuator is saturated (i.e., when it reaches its maximum or minimum limit).
    This helps to avoid overshoot and instability in the control system.
    Note that anti-windup only works if $u_{max}$ and $u_{min}$ are defined for the actuator.
    </details>
- **$k_{df}$** controls the derivative filtering term (blue). If set to 0, derivative filtering is disabled.
  <details id=derivative_filtering><summary>What is derivative filtering?</summary>

    Derivative filtering is used to smooth out the derivative term, which can be sensitive to noise in the measurement signal.
    It does so by computing a weighted average of the current derivative calculation and the *already filtered* value of the derivative terms,
    with weights given by $dt$ and $k_{df}$ respectively.
    This helps to reduce the impact of high-frequency noise on the derivative calculation, leading to a more stable control response.
    </details>
- $u_{s}(t)$ is the saturated output at time $t$.
  <details id=saturation><summary>What is saturation?</summary>

    Saturation is the process of limiting the output variable to stay within predefined bounds.
    This is important to ensure that the actuator operates within its safe and effective range.
    The saturated output is truncated at **$u_{max}$** and **$u_{min}$**.
    Then, its rate of change ($\frac{u(t)-u(t')}{dt}$) is limited by **${du}_{max}$**.
    </details>
- $u'(t')$ is the error difference in the previous step ($e(t')-e(t'')$).


The saturated output variable is then published as an mqtt message, to which the actuator is expected to be subscribed.
