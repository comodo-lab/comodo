# Firmware

The firmware provides a standard interface between the comodo stack and individual instruments.

An instrument is understood as a device with a unique address, which may monitor and/or control one or more variables.

- [Firmware](#firmware)
  - [Configuration](#configuration)
    - [Generating the compose.firmware.yaml](#generating-the-composefirmwareyaml)
  - [Structure and life cycle](#structure-and-life-cycle)
    - [MQTT Topics](#mqtt-topics)
  - [Instrument modules](#instrument-modules)

## Configuration
The firmware expects to find its configuration through environment variables. These are usually set in the firmware's [compose file](#generating-the-composefirmwareyaml).

The expected environment variables are:
- `MQTT_USER`: The username for the MQTT broker.
- `MQTT_PASS`: The password for the MQTT broker.
- `MQTT_HOST`: The hostname of the MQTT broker.
- `INSTRUMENT_NAME`: The instrument id.
- `FIRMWARE`: The name of the [module](#instrument-modules) to be used (should match the name of the module in the `src/instruments` directory). If unset, or if "generic_instrument" is specified, the firmware will use the generic instrument class to simulate the instrument.
- `ADDRESS`: The address at which the instrument is contacted (e.g. a serial port, an IP address, etc.).
- `SIMULATE`: True if the instrument should be simulated, False otherwise.
- `ACTIVE_VARIABLES`: A list of the variables that the instrument should monitor and/or control.
- `DEFAULT_SETPOINTS`: A dictionary of the default setpoints for each variable in the form `{variable: setpoint}`.
- `SAFE_STOP_SETPOINTS`: A dictionary of the safe stop setpoints for each variable in the form `{variable: setpoint}`.
- `MEASUREMENT_INTERVALS`: A dictionary of the measurement intervals for each variable in the form `{variable: interval}`.
- `HEARTBEAT_INTERVAL`: The interval at which the firmware should send a heartbeat message to the MQTT broker.


### Generating the compose.firmware.yaml

In a standard deployment, these are extracted from the `comodo.yaml` file and templated into the `compose.firmware.yaml` file using the `firmware/templates/compose.firmware.yaml.j2` jinja template. This can be accomplished by running:
```
docker compose -f "./firmware/compose.gen.yaml" run --rm compose-gen
```
from the comodo repository root (where the `comodo.yaml` file is located).

The `compose.firmware.yaml` file is then provides the stack of instrument firmware containers, each with its own configuration.

## Structure and life cycle
The firmware instantiates an `InstrumentState` object, which serves as the state machine for the instrument.
It owns a `status` string, an mqtt `client`, and an `Instrument` object. It is also responsible for redirecting the mqtt `callbacks` to the appropriate methods, and for publishing the instrument's `heartbeat`.

The `Instrument` object is the interface to the instrument itself.
It defines the `available_variables`, it stores the current `setpoints`, and owns the methods to measure and set setpoints.
The configuration is loaded from the environment variables, and stored in the Instrument object as `config`.

The structure of the firmware is then as follows:

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 1, "rankSpacing": 1, "padding": 5,"subGraphTitleMargin": {"top": 4, "bottom": 16}, "diagramPadding": 1}}}%%
flowchart TB
    subgraph state ["`**state**`"]
        direction TB
        status(status) ~~~ client(client) ~~~ instrument
        subgraph instrument ["`**instrument**`"]
            direction LR
            config(config) ~~~ setpoints(setpoints) ~~~ available_variables(available_variables)
        end
    end
    classDef item fill:#ccccff55,stroke:#888
    class status,client,available_variables,config,setpoints item

    style state fill:#ccccff55,stroke:#888,rx:10,ry:10
    style instrument fill:#ccccff55,stroke:#888,rx:10,ry:10
```

The initialisation of the firmware is done by first loading the configuration, which is passed to the `InstrumentState` object, which in turn uses it to create the `Instrument` object. The `status` is set to `initialising`.
Then measurement ticks are launched asynchronously.
Once the first tick of each variable is received, the instrument goes to the default setpoints, and the status is set to `awaiting_experiment`.
Only then, a success message is printed, and the instrument's
heartbeat ticks are launched asynchronously.

While in the `awaiting_experiment` state, the instrument will continue to take measurements, and expect for an experiment to start.
When an experiment is started, the status is set to `running`, and the instrument will continue to take measurements and set setpoints.
When an experiment is stopped, the status is set back to `awaiting_experiment`.

At any point, if the instrument cannot take measurements or set setpoints, the status is set to `error`. The instrument will nonetheless continue to try to take measurements and set setpoints, and if it succeeds, the status will be set back to `awaiting_experiment` or `running`, depending on whether an experiment is running or not.

The measurement and heartbeat ticks will continue to run indefinitely, unless an unexpected error occurs.
In such case, docker compose will restart the firmware container, and the initialisation process will be repeated.

The initialisation process of the firmware can be summarised as follows:
```mermaid
%%{init: {"flowchart": {"nodeSpacing": 15, "rankSpacing": 25, "padding": 6}}}%%
stateDiagram-v2
    state "Start / Restart" as start
    state "Load config" as load
    state "Create InstrumentState" as create_state
    state "Create Instrument" as create_instrument
    state "status = 'initialising'" as status_init
    state "Launch measurement ticks" as measure
    state "Wait for first tick of each variable" as first_tick
    state "Go to default setpoints" as setpoints_init
    state "status = 'awaiting_experiment'" as status_await
    state "Print success message" as success
    state "Launch heartbeat ticks" as heartbeat
    state "Unexpected error" as crash
    state continue <<join>>

    [*] --> start
    crash --> start
    start --> load
    load --> create_state
    create_state --> create_instrument
    create_instrument --> status_init
    status_init --> measure
    measure --> continue
    measure --> first_tick
    first_tick --> setpoints_init
    setpoints_init --> status_await
    status_await --> success
    success --> heartbeat
    heartbeat --> continue

    classDef item fill:#ccccff55,stroke:#888
    classDef async fill:#ccffcc55,stroke:#888,stroke-dasharray:5 3
    classDef failure fill:#ffcccc55,stroke:#c55
    class load, create_state, create_instrument, first_tick, setpoints_init, success item
    class measure, heartbeat async
    class crash failure
```

The status of an instrument can only be one of the following:
- `initialising`: The instrument is being initialised, and is not yet ready to take measurements or set setpoints.
- `awaiting_experiment`: The instrument is taking measurements and ready to set setpoints, but is waiting for an experiment to be started.
- `running`: The instrument is taking measurements and setting setpoints as expected.
- `error`: The instrument is unable to take measurements and/or set setpoints.

So its status transitions are as follows:
```mermaid
%%{init: {"flowchart": {"nodeSpacing": 15, "rankSpacing": 25, "padding": 6}}}%%
stateDiagram-v2
    state "initialising" as initialising
    state continue <<join>>
    state "awaiting_experiment" as waiting
    state "running" as running
    state "error" as error

    [*] --> initialising
    initialising --> continue
    continue -->waiting
    waiting --> running: experiment started
    waiting --> error: cannot measure
    running --> waiting: experiment stopped
    running --> error: cannot measure or set setpoint
    error --> running: recovered, has experiment
    error --> waiting: recovered, no experiment
```

### MQTT Topics
The firmware subscribes to the following MQTT topics:
- `instruments/<instrument_name>/configure`: To receive live configuration while in `awaiting_experiment` status.
- `controller/command/start`: To fetch the experiment id and start an experiment (move to `running` status).
- `instruments/<instrument_name>/+/setpoint`: The desired setpoint for the variable identified by the wildcard.
- `controller/event/end` and `controller/command/stop`: To end/stop the current experiment (move to `awaiting_experiment` status).

## Instrument modules
The firmware modules are located in the `src/instruments` directory. Each module should be a subclass of the `BaseInstrument` class, and should define an Instrument class with the following methods:
- `initialise(self)`: Must perform all required initialisation for the instrument, including establishing a connection to the instrument and setting up any required parameters. This method must also be safe to call whether the instrument is being simulated or not.
- `simulate(self, variable)`: This method will only be called when the instrument is being simulated, and should return a simulated value for the given `variable`. It can immediately refer to the `self.default_sim(variable)`, but may be use to provide more realistic simulated behaviour of the instrument, which converges towards the variable's setpoint over time.
- `get_measurement(self, variable)`: This method will only be called when the instrument is not being simulated, and should return a measurement for the given `variable`. It must raise an exception if the measurement cannot be taken.
- `go_to_setpoint(self, variable, setpoint)`: This method will only be called when the instrument is not being simulated, and should direct the instrument to go to the given `setpoint` for the given `variable` if an actuator is available. It must raise an exception if there is an actuator available but the setpoint cannot be set.

It is expected that the modules follow this structure:

```
"""
<Name of the instrument for which this firmware is intended>
<link to the instrument's documentation>
"""

# System imports
from typing import ClassVar

# Instrument specific imports
<imports required for the instrument>

# Local imports
from src.instrument import BaseInstrument


# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------
class Instrument(BaseInstrument):
    available_variables: ClassVar[dict[str, dict]] = {
        <variable dicts>
    }

    def initialise(self):
        <implementation>

    def simulate(self, variable):
        <implementation>

    def get_measurement(self, variable):
        <implementation>

    def go_to_setpoint(self, variable, setpoint):
        <implementation>


# ======================================================================================

# ======================================================================================
# Configuration and helper functions
# --------------------------------------------------------------------------------------
<configuration and helper functions for the instrument>
```
