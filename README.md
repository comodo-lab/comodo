# Comodo 

Welcome to the Comodo monorepo! 

This repo contains everything you need to get started using Comodo for automating your scientific experiments.

- [Comodo](#comodo)
  - [What is Comodo?](#what-is-comodo)
  - [Central Configuration File](#central-configuration-file)
    - [Global Settings](#global-settings)
    - [Instruments and Variables](#instruments-and-variables)
      - [Sensors](#sensors)
      - [Actuators](#actuators)
      - [Setpoint Controllers](#setpoint-controllers)
    - [Visualizations](#visualizations)
  - [Automatic deployment](#automatic-deployment)
  - [Manual deployment](#manual-deployment)
    - [Environment variables](#environment-variables)
    - [Publishing the Grafana dashboard](#publishing-the-grafana-dashboard)


## What is Comodo?

Comodo is an open-source platform for controlling and monitoring scientific experiments.

The stack consists of:
- A series of sensors and actuators that interface with the physical world.
  These devices are responsible for collecting data and/or executing the actual experiment,
  and must have compatible [firmware](firmware/README.md) controlling them.
- A central configuration file, `comodo.yml`, which defines the experiment: **NOTE:** *This is wishful thinking... Currently nothing actually listens to this file!!!*
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

**NOTE:** *The intention is that the central configuration file will result in a fully automated deployment of the entire stack, including the firmware for the sensors and actuators.*
*However, this is not yet fully implemented, and currently the deployment requires some manual steps.*
*In particular, the firmware for the sensors and actuators is currently orchestrated with the `compose.firmware.yaml` file, and hardocded in the firmware main.py file.*

## Central Configuration File
**NOTE:** *Currently nothing listens to this file, everything is hardcoded in the controller code, the firmware code, and the compose.firmware.yaml file.*

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
- The [`instruments`](#instruments-and-variables) section is where you define each instrument in the experiment.
  Each *instrument* should represent a physical device and can be composed of multiple [`variables`](#instruments-and-variables).
- The [`visualizations`](#visualizations) section defines how the data from the experiment will be monitored in the UI.

### Global Settings
Experiment global settings are defined in the `global` section of the `comodo.yml` file.

Currently implemented settings include:
- `error_timeout`: The time in seconds to wait before considering an instrument unresponsive.

### Instruments and Variables
Instruments are meant to represent physical devices in your experiment.
Each instrument can be monitoring or controlling multiple variables, so each instrument is composed of multiple `variables`.

Each variable represents a specific measurement.
Since they always have to be measured, a [`sensor`](#sensors) must always be associated with a variable.
In some cases, a variable can also be controlled, in which case an [`actuator`](#actuators) can be associated with the variable.
Finally, a variable's actuator can be controlled based on the measurement of another variable's sensor, in which case a [`setpoint_controller`](#setpoint-controllers) can be defined for the variable.

#### Sensors
A `sensor` defines how a variable is measured.
All variables need to be measured, so a sensor must always be specified for a variable.

Each sensor can have the following properties:
- `type`: [required] The data type reported by the sensor (e.g., float, int, string).
- `min`:  [optional] The minimum value the sensor can report.
- `max`:  [optional] The maximum value the sensor can report.
- `unit`: [optional] The unit of measurement for the sensor's readings (e.g., `°C`, `Pa`, `m/s`).

#### Actuators
An `actuator` defines how a variable can be controlled.
Not all variables are being controlled, so an actuator is optional for a variable.
Each actuator can have the following properties:
- `type`: [required] The data type accepted by the actuator.
- `min`:  [optional] The minimum value the actuator can accept.
- `max`:  [optional] The maximum value the actuator can accept.
- `unit`: [optional] The unit of measurement for the actuator's input.

#### Setpoint Controllers
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

Requirements:
- These ports must be available:
  - `1883` - MQTT broker
  - `8501` - UI
  - `8086` - InfluxDB
  - `3000` - Grafana

Steps:

- Set up the [environment variables](#environment-variables).
- Run `docker compose --profile mqtt --profile live up -d`.
- Publish the [Grafana dashboard](#publishing-the-grafana-dashboard).
- Update the `FRONTEND_GRAFANA_URL` environment variable in your `.env` file.
- Run `docker compose --profile live up -d` to apply the changes.
- Visit `localhost:8501` to access the Comodo UI.

Setting up the firmware for the sensors and actuators:

Currently this is done through the `compose.firmware.yaml` file. <!-- How? -->

### Environment variables

To manually deploy Comodo you'll need to copy the `env.template` file to a file called `.env` and fill in the required environment variables.

- `MQTT_HOST` sets the hostname or IP address of your MQTT broker.
    If you're running the Comodo stack locally, set this to `rabbitmq`.
    If you're using a remote broker, set this to the appropriate IP address or FQDN.
- `MQTT_USER` is the username for your MQTT broker. You can set this to whatever you like.
- `MQTT_PASS` is the password for your MQTT broker. You can set this to whatever you like.
- `INFLUX_ADDR` is the address of your InfluxDB instance.
    If you're running the Comodo stack locally, set this to `https://influx:8086`.
- `INFLUX_TOKEN` is the authentication token for your InfluxDB instance. You can set this to whatever you like.
- `INFLUX_BUCKET` is the bucket name in InfluxDB where data will be stored. You can set this to whatever you like.
- `INFLUX_ORG` is the organization name in InfluxDB.
- If you're running the Comodo stack locally, set this to `comodo`.
- `FRONTEND_GRAFANA_URL` is the URL of your Grafana dashboard.
    This is currently not automated, and it requires you to manually [publish your dashboard](#publishing-the-grafana-dashboard) before setting it here.

### Publishing the Grafana dashboard

- Visit the Grafana UI at `localhost:3000`.
- Select "Dashboards" on the navigation panel on the left.
- Select the dashboard called "Comodo State Testing".
- Click the "Share" icon at the top of the page, which will copy a shortened url.
- Use that URL as the value for the `FRONTEND_GRAFANA_URL` environment variable.
