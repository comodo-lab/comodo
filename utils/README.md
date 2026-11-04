# Utils

Code shared by the Comodo components, shared test mocks, and helper scripts.

- [Utils](#utils)
  - [How components use utils](#how-components-use-utils)
  - [Modules](#modules)
  - [Test mocks](#test-mocks)
  - [Scripts](#scripts)
  - [Running tests](#running-tests)

## How components use utils
`utils` is not installed as a package. Instead, each component's `Dockerfile` copies the files it needs into its own `utils/` folder, e.g.:
```dockerfile
COPY utils/mqtt_clients.py      /controller/utils/mqtt_clients.py
```
and imports them as `from utils import mqtt_clients`.

This means that:
- Changes to `utils` only take effect in a component after rebuilding its image (`--build`).
- When a component starts using another module from `utils`, it has to be added to its `Dockerfile`.

| Module | Used by |
|---|---|
| `mqtt_clients.py` | controller, firmware, monitor, setpoint controller, UI |
| `mqtt_validator.py` | controller, firmware, monitor, setpoint controller |
| `comodo_config.py` | controller, UI, integration tests |
| `interpolation.py` | controller, UI |
| `influx_query.py` | UI |

## Modules
- [`mqtt_clients.py`](mqtt_clients.py): Wrappers around the [paho](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) MQTT client.
  - `MQTTClient`: A client that connects to the broker, subscribes to a list of `topics`, and calls a `callback(client, msg, obj)` for every message.
    `obj` is any object to be passed to the callback (e.g. the controller's state). The callback can be swapped at any time, which the controller and firmware use to implement their state machines.
  - `MQTTPublisher`: A thread-safe singleton for publishing messages. Each component creates it once at start up with `MQTTPublisher.get_instance(...)`, and then uses `MQTTPublisher.get_instance().publish(topic, message)` anywhere.
  - Unhandled exceptions in a callback are caught, printed, and published on `error/exception`.
    Note that the controller's watchdog restarts the controller when a message is published on `error/exception`.
- [`mqtt_validator.py`](mqtt_validator.py): Validates MQTT messages against the [message schema](../schemas/README.md#mqtt_schemayaml).
  `validate_message(topic, payload)` returns the decoded payload, or raises an `MQTTValidationException` if the topic is not in the schema, the payload is not valid JSON, or it does not match the schema.
  The schema is read from `/schemas/mqtt_schema.yaml`, which each component's `Dockerfile` copies into its image.
- [`comodo_config.py`](comodo_config.py): Loads `comodo.yaml` (from `/app/comodo.yaml` by default) into a `ComodoConfig` object, with:
  - `globals`, `instruments`, `sensors`, `actuators` and `spcs` (setpoint controllers), keyed by name, or by `instrument/variable` for sensors and actuators.
  - The checks that the [schema](../schemas/README.md#comodoyamlschema) cannot express, e.g. that every actuator's driving sensor has a `default_setpoint` and a `tolerance`.
  - Helpers to build the expected heartbeat of each instrument, and the default experiment.
- [`interpolation.py`](interpolation.py): `split_setpoints` turns the rows of an experiment into one setpoint per `resolution` seconds,
  following each variable's profile (`linear`, `exponential`, `logarithmic` or `step`).
  Used by the controller to send the setpoints, and by the UI to plot them.
- [`influx_query.py`](influx_query.py): Helpers to query InfluxDB.

## Test mocks
[`tests/mocks/`](tests/mocks/) holds the mocks and pytest fixtures shared by the tests of all components, and by the [integration tests](../integration_tests/README.md):
- `comodo.yaml`: The mock central configuration, also used to run the integration tests.
- `mock_comodo_yaml_dict.py` and `mock_comodo_config.py`: The same configuration as a dictionary, and as a loaded `ComodoConfig`.
- `mock_experiment.py`: A mock experiment, as sent on `ui/start`.
- `mock_mqtt_clients.py`, `mock_mqtt_validator.py` and `mock_topic_map.py`: Mocks of the MQTT clients and validator, so tests can run without a broker.

The mocks are copied into each component's image, like the modules.
When changing `tests/mocks/comodo.yaml`, keep the other mocks consistent with it.

## Scripts
- [`contexts.sh`](contexts.sh): Prepares a deployment: regenerates `compose.firmware.yaml`, creates the Docker contexts for remote hosts, and prints the commands to start each stack.
  See [automatic deployment](../README.md#automatic-deployment) in the main README. Run `./utils/contexts.sh --help` for its options.
- [`run-integration-tests.sh`](run-integration-tests.sh): Deploys every stack with the mock configuration,
  runs the integration tests, and tears the stacks down. See the [integration tests](../integration_tests/README.md).
- [`run-all-tests.sh`](run-all-tests.sh): Runs the tests of every component, and the integration tests, and prints a summary.
  Use `--noint` to skip the integration tests. See [helper script](../README.md#helper-script) in the main README.

## Running tests
The tests for the shared modules can be run from the `utils/` directory with:
```shell
docker compose up --build
```

To check the coverage report after the tests have run:
```shell
xdg-open $(docker volume inspect utils-tests_memory -f '{{ .Mountpoint }}')/htmlcov/class_index.html
```
