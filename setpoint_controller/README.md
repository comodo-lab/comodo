# Setpoint Controller

The setpoint controller works with a PID (Proportional-Integral-Derivative) feedback loop,
with optional [anti-windup](#anti_windup) and [derivative filtering](#derivative_filtering).

A setpoint controller drives an actuator (e.g. a mass flow controller) based on the readings of another instrument's sensor (e.g. a pressure gauge),
so that the sensor reaches its setpoint.

- [Setpoint Controller](#setpoint-controller)
  - [Configuration](#configuration)
    - [MQTT Topics](#mqtt-topics)
  - [Behaviour](#behaviour)
  - [Operation](#operation)
  - [Running tests](#running-tests)

## Configuration

The setpoint controller is configured with an external sensor, PID parameters, a target actuator, and its defined limits.

Configuration is done via environment variables.
In a standard deployment, each setpoint controller runs as its own service in `compose.firmware.yaml`,
which is generated from the `setpoint_controller` entries in `comodo.yaml` (see the [main README](../README.md#setpoint-controllers)).

In its simplest form, the following environment variables are required:
- `MQTT_HOST`: hostname or IP address of your MQTT broker.
- `MQTT_USER`: username for the MQTT broker.
- `MQTT_PASS`: password for the MQTT broker.
- `SENSOR`: The external sensor to be used for feedback, as `instrument_name/variable_name`.
- `ACTUATOR`: The target actuator to be controlled, as `instrument_name/variable_name`.
- `DEFAULT_SETPOINT`: The setpoint for the external sensor when no experiment is running.
  Set from the sensor's `default_setpoint` in `comodo.yaml`.

The id of the setpoint controller is derived from these, as `<sensor instrument>-<sensor variable>--<actuator instrument>-<actuator variable>`
(e.g. `pressure-pressure--mass_flow-mass_flow`).

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
- `OUT_MIN`: Minimum limit for the actuator. Set from the actuator variable's `min` in `comodo.yaml`. $\textcolor{#999999}{\small{\text{ Default: 0. }}}$
- `OUT_MAX`: Maximum limit for the actuator. Set from the actuator variable's `max` in `comodo.yaml`. $\textcolor{#999999}{\small{\text{ Default: 100. }}}$
- `MAX_RATE`: Maximum rate of change for the actuator, in units per second. $\textcolor{#999999}{\small{\text{ Default: None (unlimited). }}}$

### MQTT Topics
In the topics below, `SENSOR` and `ACTUATOR` are `instrument_name/variable_name`, and `SPC_ID` is the setpoint controller's id.

The controller subscribes to the following MQTT topics:
- `instruments/SENSOR/setpoint`: The desired setpoint for the external sensor (sent by the experiment controller).
- `instruments/SENSOR/measurement`: The current measurements from the external sensor.
- `setpoint_controllers/SPC_ID/configure`: Live configuration, with any of:
  - `enabled`: `true` or `false`, to enable or disable the controller.
  - `experiment_id`: The id of the current experiment.
  - `pid`: Any of the PID parameters `k_p`, `k_i`, `k_d`, `k_aw`, `k_df`, `min`, `max` and `max_rate`.
    PID parameters cannot be changed while an experiment is running.

  If any key is not configurable, the whole configuration is rejected and an error is published.
- `controller/command/start`: To store the id of the experiment that is starting.
- `controller/event/end` and `controller/command/stop`: To end the current experiment.
- `controller/command/reset`: Sent by the controller when it starts, or when asked by the UI. Ends any experiment (with a warning, as the controller lost it),
  even if disabled, and goes back to the default setpoint (if enabled).

And publishes to:
- `instruments/ACTUATOR/setpoint`: The computed control signal (the saturated output) for the target actuator.
- `setpoint_controllers/SPC_ID/heartbeat`: Every `HEARTBEAT_INTERVAL` seconds, and after every configuration message, with:
  - `state`: The `status`, whether it is `enabled`, the latest `sensor_measurement`, the latest `actuator_setpoint`, and the `experiment_id`.
  - `setpoints`: The current `sensor_setpoint`.
  - `config`: The `sensor`, `actuator`, and current `pid` parameters.
    The experiment controller compares these with the experiment's live configuration, and stops the experiment if they don't match.
- `error/setpoint_controller`: If a message is invalid, or a configuration is rejected.

## Behaviour
- On start up, the sensor's setpoint is set to `DEFAULT_SETPOINT`, and the status is `idle`.
- Every time a measurement of the external sensor is received, the PID computes a new output, which is published as the actuator's setpoint,
  and the status is set to `adjusting`. So the control loop runs at the sensor's measurement interval.
- When a new setpoint for the external sensor is received, it is used from the next measurement on.
- When an experiment ends or is stopped, the sensor's setpoint goes back to `DEFAULT_SETPOINT`, and the controller keeps running.
- When disabled (`"enabled": false`), the controller ignores setpoints, measurements and experiment messages, and does not publish any actuator setpoint.
  Its status is set to `idle`, and its sensor setpoint is cleared until it is enabled again and a new setpoint is received.
- If an invalid message is received, the status is set to `error`, until the next measurement is processed.

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

## Running tests

From the `setpoint_controller/` directory, run:
```shell
docker compose up --build
```

To check the coverage report after the tests have run:
```shell
xdg-open $(docker volume inspect setpoint_controller-tests_memory -f '{{ .Mountpoint }}')/htmlcov/class_index.html
```
