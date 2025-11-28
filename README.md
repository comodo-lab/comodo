# Comodo 

Welcome to the Comodo monorepo! 

This repo contains everything you need to get started using Comodo for automating your scientific experiments.

- [Comodo](#comodo)
  - [What is Comodo?](#what-is-comodo)
  - [Central Configuration File](#central-configuration-file)
    - [Global Settings](#global-settings)
    - [Instruments](#instruments)
      - [Variables](#variables)
        - [Sensors](#sensors)
        - [Actuators](#actuators)
        - [Setpoint Controllers](#setpoint-controllers)
    - [Visualizations](#visualizations)
  - [Automatic deployment](#automatic-deployment)
  - [Manual deployment](#manual-deployment)
    - [Requirements:](#requirements)
    - [Environment variables](#environment-variables)
    - [Setting up Comodo](#setting-up-comodo)
      - [Bringing comodo down](#bringing-comodo-down)
    - [Setting up the firmware for the sensors and actuators](#setting-up-the-firmware-for-the-sensors-and-actuators)
      - [Bringing the firmware down](#bringing-the-firmware-down)


## What is Comodo?

Comodo is an open-source platform for controlling and monitoring scientific experiments.

The stack consists of:
- A series of sensors and actuators that interface with the physical world.
  These devices are responsible for collecting data and/or executing the actual experiment,
  and must have compatible [firmware](firmware/README.md) controlling them.
- A [central configuration file](#central-configuration-file), `comodo.yml`, which defines the experiment: (See [note here](#central-configuration-file).)
  - The instruments of an experiment (physical devices).
  - The variables measured by the instruments.
  - The sensor for each variable, and optionally their actuators and potential relationships between variables.
  - Desired monitoring visualizations.
- The [user interface](controller/ui/README.md), which allows users to configure and control experiments through a graphical interface (web app).
  The UI also contains an embedded Grafana dashboard to monitor the experiments.
- The [controller](controller/README.md), which is responsible for orchestrating experiments.
  It is the backbone of Comodo, and communicates with all other components through MQTT messages.
- An MQTT broker (RabbitMQ) for handling communication between the different components.
- A database (InfluxDB) for storing time series data from experiments.
  Data is recived in form of MQTT messages, translated by Telegraf, and stored in InfluxDB.

The different components are glued together using the `comodo-nexus` compose file, which defines and configures all the services required to run Comodo.

Currently, only [manual deployment](#manual-deployment) is supported.

## Central Configuration File
**NOTE:** *Currently nothing listens to this file, everything is hardcoded in:*
*- The [ui's app](ui/app.py) app - See definition of `PARAMS`, `PARAM_DICT` and `INI_DATA_DICT`*
*- The [ui's plotting](ui/plot.py) code - Maybe this is sort of generic?*
*- The controller's code - See the [experiment schema](controller/schemas/schema_experiment.json)*
*- The [firmware's main](firmware/main.py) code - See `# Sensor imports (trigger sensor registration)` section.*
*- The [compose.firmware.yaml](compose.firmware.yaml) file.*
*The intention is that the central configuration file will result in a fully automated deployment of the entire stack, including the firmware for the sensors and actuators.*
*However, this is not yet implemented, and currently the deployment requires manually configuring the above files.*
*Also, once the above are configured, one needs to [deploy the firmware stack](#setting-up-the-firmware-for-the-sensors-and-actuators).*

The central configuration file, `comodo.yml`, is where you define your experiment.
This file is written in YAML format and contains all the necessary information to set up, run, and monitor your experiment.

The hierarchical structure of the `comodo.yml` file is as follows:

```yaml
global: # Global settings for the experiment
instruments: # Define physical devices in your experiment
  instrument_name:  # Name of the instrument, to be used as a reference
    variables:  # Define variables measured by the instrument
      variable_name:  # Name of the variable, to be used as a reference
        sensor: # Defines the way in which the variable is measured.
        actuator: # Defines the way in which the variable is controlled.
        setpoint_controller:  # Defines relationships between variables.
visualizations: # Definitions of monitoring visualizations
```

That is, at the top level, the file is divided into three main sections: `global`, `instruments`, and `visualizations`.
- The [`global`](#global-settings) section contains settings that apply to the entire experiment.
- The [`instruments`](#instruments) section is where you define each instrument in the experiment.
  Each *instrument* should represent a physical device and can be composed of multiple [`variables`](#variables).
- The [`visualizations`](#visualizations) section defines how the data from the experiment will be monitored in the UI.

### Global Settings
Experiment global settings are defined in the `global` section of the `comodo.yml` file.

Currently implemented settings include:
- `error_timeout`: The time in seconds to wait before considering an instrument unresponsive.
- `measurement_interval`: The default interval in seconds at which measurements are taken from all instruments.
  This can be overridden for individual instruments if needed.

### Instruments
Instruments are meant to represent physical devices in your experiment.
Each instrument can be monitoring or controlling multiple variables, so each instrument is composed of multiple [`variables`](#variables).
However, an instrument has a single `firmware` and `address`, which define how to communicate with the physical device.

Each instrument can have the following properties:
- `firmware`: [required] The type of firmware the instrument is running.
  This defines how to communicate with the instrument, and it should match one of the supported firmware types in the [firmware directory](firmware/).
- `address`: [required] The address of the instrument.
  This can be an IP address and port (e.g., `192.168.10:502`), a serial port (e.g., `/dev/ttyUSB0`), or any other identifier required to communicate with the instrument.
- `measurement_interval`: [optional] The interval in seconds at which measurements are taken from the instrument.
  If not specified, the global `measurement_interval` will be used.
- [`variables`](#variables): [required] The (named) variables monitored or controlled by the instrument.

#### Variables

Variables represents specific measurement points in an instrument.

Each variable can have the following properties:
- [`sensor`](#sensors): [required] Defines how the variable is measured.
  Since all variables need to be measured, a sensor must always be specified.
- [`actuator`](#actuators): [optional] Defines how the variable can be *directly* controlled.
  Not all variables are being directly controlled, so an actuator is optional.
- [`setpoint_controller`](#setpoint-controllers): [optional] Defines a relationship between the variable's actuator and another variable's sensor.
  This is used to define a control feedback, that is, the actuator will be controlled based on the readings from an external sensor.

##### Sensors
A `sensor` defines how a variable is measured.
All variables need to be measured, so a sensor must always be specified for a variable.

Each sensor can have the following properties:
- `type`: [required] The data type reported by the sensor (e.g., float, int, string).
- `min`:  [optional] The minimum value the sensor can report.
- `max`:  [optional] The maximum value the sensor can report.
- `unit`: [optional] The unit of measurement for the sensor's readings (e.g., `°C`, `Pa`, `m/s`).

##### Actuators
An `actuator` defines how a variable can be controlled.
Not all variables are being directly controlled, so an actuator is optional for a variable.
When the variable is *indirectly* controlled by another variable's actuator, a `setpoint_controller` should be set for that variable.

Each actuator can have the following properties:
- `type`: [required] The data type accepted by the actuator.
- `min`:  [optional] The minimum value the actuator can accept.
- `max`:  [optional] The maximum value the actuator can accept.
- `unit`: [optional] The unit of measurement for the actuator's input.

##### Setpoint Controllers
A `setpoint_controller` defines a relationship between its variable's actuator and another variable's sensor.
It is used to define a control feedback.
That is, the actuator will be controlled based on the readings from an external sensor.

The setpoint controller listens to the setpoint of the `external_sensor`, as well as its readings,
and uses a PID controller, coupled with the `output_function` to compute the appropriate setpoint for the actuator.

Many actuators will use their own sensor for feedback, and so setpoint controllers are optional.

A setpoint controller can have the following properties:
- `external_sensor`: [required] The reference to the sensor that will be used as feedback for the controller.
  The reference should be in the format `instrument_name.variable_name`.
- `P`: [required] The proportional gain of the controller.
- `I`: [required] The integral gain of the controller.
- `D`: [required] The derivative gain of the controller.
- `output_function`: [required] The function used to compute the actuator output based on the controller's calculations. <!-- not sure what this will be, really -->

### Visualizations
The `visualizations` section is where you define how the data from the experiment will be monitored.

Each visualization can have the following properties:
- `id`: [required] The unique identifier for the visualization.
- `title`: [optional] A human-readable title for the visualization.
- `type`: [required] The type of visualization (e.g., graph, gauge).
<!-- lots to specify here still -->

## Automatic deployment
Currently not available.

## Manual deployment

### Requirements:
- These ports must be available:
  - `1883` - MQTT broker
  - `8501` - UI
  - `8086` - InfluxDB
  - `3000` - Grafana

### Environment variables

To manually deploy Comodo you'll need to copy the `env.template` file to a file called `.env`:
```bash
cp env.template .env
```
and fill in the required environment variables:

- `MQTT_HOST` sets the hostname or IP address of your MQTT broker.
    If you're running the Comodo stack locally, set this to `rabbitmq`.
    If you're using a remote broker, set this to the appropriate IP address or FQDN.
- `MQTT_USER` is the username for your MQTT broker. You can set this to whatever you like.
- `MQTT_PASS` is the password for your MQTT broker. You can set this to whatever you like.
- `INFLUX_ADDR` is the address of your InfluxDB instance.
    If you're running the Comodo stack locally, set this to `http://influxdb:8086`.
- `INFLUX_TOKEN` is the authentication token for your InfluxDB instance. You can set this to whatever you like.
- `INFLUX_BUCKET` is the bucket name in InfluxDB where data will be stored. ~~You can set this to whatever you like.~~
  This currently has to be `comodo` for Grafana to work.
- `INFLUX_ORG` is the organization name in InfluxDB.
- If you're running the Comodo stack locally, set this to `comodo`.
- `FRONTEND_GRAFANA_URL` is the URL of your Grafana dashboard.
    This is currently not automated, and it requires you to manually [publish your dashboard](#publishing-the-grafana-dashboard) before setting it here.

### Setting up Comodo

- Set up the [environment variables](#environment-variables).
- Run `docker compose --profile mqtt --profile live up --build -d`.
- Publish the Grafana dashboard ([steps](#publishing-the-grafana-dashboard)).
- Update the `FRONTEND_GRAFANA_URL` environment variable in your `.env` file.
- Run `docker compose up -d` to apply the changes.
- Visit `localhost:8501` to access the Comodo UI.

<details id="publishing-the-grafana-dashboard">
<summary>How do I publishing the Grafana dashboard?</summary>

- Visit the Grafana UI at `localhost:3000`.
- Select "Dashboards" on the navigation panel on the left.
- Select the dashboard called "Comodo State Testing".
- Click the "Share" icon at the top of the page, which will copy a shortened url.
- Use that URL as the value for the `FRONTEND_GRAFANA_URL` environment variable.

</details>


#### Bringing comodo down
If you must bring the stack down and want to start from scratch, run `docker compose --profile mqtt --profile live down -v`.

### Setting up the firmware for the sensors and actuators

Currently this is done through the `compose.firmware.yaml` file (see [note here](#central-configuration-file).)

First, in the firmware directory, create env.json file from env.json.template:
```bash
cp firmware/env.json.template firmware/env.json
```

Copy the mqtt credentials you set up in the .env file into the firmware/env.json.
If any of the hardware needs internet access, set the credentials in the file. Otherwise, you may delete these rows, or leave them empty.
The settings sensor id, heartbeat interval and measurement interval will be overwritten (in firmware.config.py),
with the environment variable values in the compose.firmware.yaml file.

Then bring the stack up with:
```bash
docker compose -f compose.firmware.yaml up --build -d
```

#### Bringing the firmware down
If you must bring the stack down and want to start from scratch, run `docker compose -f compose.firmware.yaml down -v`.
