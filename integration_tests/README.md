# Integration tests

End-to-end tests for the Comodo stack.
Unlike each component's own tests, these start the real services together, and check they work with each other over MQTT.

- [Integration tests](#integration-tests)
  - [What is started](#what-is-started)
  - [What is tested](#what-is-tested)
  - [Running the tests](#running-the-tests)
    - [Debugging](#debugging)
  - [Configuration](#configuration)
  - [Updating the tests](#updating-the-tests)

## What is started
The [compose file](compose.yaml) includes the stack's own compose files, so the services are the same as in a real deployment:
- The MQTT broker (`compose.mqtt.yaml`).
- The core stack: config validation, controller, UI and monitor (`compose.yaml`).
- The data stack: InfluxDB, Telegraf and Grafana (`compose.data.yaml`).
- The firmware stack: one firmware container per instrument, and one per setpoint controller (`compose.firmware.yaml`).
  The instruments in the mock configuration are all simulated.
- The debugging tools (`compose.debug.yaml`).
- The test runner (`integration-test`), which runs [`runner.py`](runner.py) with pytest.

The test runner mounts `controller/data/` (read only) to check the database dump.
Note that the stack uses the same volumes and `controller/data/` folder as a local deployment,
so the test data is added to the local InfluxDB, and each run adds an experiment to `controller/data/`.

The stack is configured with the mock configuration in [`utils/tests/mocks/comodo.yaml`](../utils/tests/mocks/comodo.yaml),
and the experiment in [`utils/tests/mocks/mock_experiment.py`](../utils/tests/mocks/mock_experiment.py).
The test runner uses the same mocks to know what to expect.

## What is tested
The test runner subscribes to all MQTT topics, and runs the following tests in order, stopping at the first failure:
1. **Services ready:** A heartbeat is received from the controller, every instrument, and every setpoint controller in the mock configuration, and from nothing else.
2. **Default setpoints:** Every variable with a `default_setpoint` reports a measurement within its `tolerance` of it.
3. **Measurements in InfluxDB:** Every sensor's measurements are stored in InfluxDB (through Telegraf).
4. **Setpoint controllers configured while idle:** PID values sent on `setpoint_controllers/<id>/configure` are reported back in the setpoint controllers' heartbeats.
5. **Experiment completes:** An experiment sent on `ui/start` runs to the end (`controller/event/end`) without any error,
   and the setpoint controllers report the PID values from the experiment, rather than the ones set while idle.
6. **Database dump:** The controller dumps the database for the experiment to `controller/data/<experiment id>/<bucket>.csv`,
   with the measurements of every sensor, and only the setpoints of this experiment.
7. **No errors:** No message was received on any `error/...` topic during the whole run.

## Running the tests
The tests need a `.env` file in the repository root, with at least `MQTT_HOST`, `MQTT_USER`, `MQTT_PASS`, `INFLUX_TOKEN`, `INFLUX_BUCKET` and `INFLUX_ORG`
(see [environment variables](../README.md#environment-variables)).

From the repository root, copy the mock configuration and regenerate the firmware compose file:
```shell
cp utils/tests/mocks/comodo.yaml ./
docker compose -f firmware/compose.gen.yaml run --rm compose-gen
```
Note that this overwrites `comodo.yaml` and `compose.firmware.yaml`, so back them up first if you have local changes.

Then, from the `integration_tests/` directory, run the tests and stop the stack when done:
```shell
docker compose --env-file ../.env up --build --attach integration-test --force-recreate
docker compose --env-file ../.env kill
```

The tests are also run by [`utils/run-all-tests.sh`](../utils/run-all-tests.sh), and in CI on pushes that change any component, and on pull requests to `main` and `dev`
(see [`.github/workflows/integration_tests.yml`](../.github/workflows/integration_tests.yml)).

### Debugging
The output only shows the test runner's prints. To also see the logs of a service, attach to it, e.g. the monitor:
```shell
docker compose --env-file ../.env up --build --attach integration-test --attach monitor --force-recreate
```
or attach to everything except the broker:
```shell
docker compose --env-file ../.env up --build --no-attach rabbitmq --force-recreate
```
and exit with Ctrl-C when done.

To watch the MQTT messages while the tests run, use [mqttui](../README.md#debugging).

## Configuration
The timeouts (in seconds) can be changed with environment variables, set in the shell or in `.env`:
- `HEARTBEAT_TIMEOUT`: Time to wait for all heartbeats, and for the setpoint controllers to report their PID values. Defaults to 20.
- `SETPOINT_TIMEOUT`: Time to wait for all variables to reach their default setpoints. Defaults to 30.
- `EXPERIMENT_TIMEOUT`: Time to wait for the experiment to complete. Defaults to 40.
- `INFLUX_TIMEOUT`: Time to wait for the measurements to appear in InfluxDB, and for the database dump. Defaults to 30.

## Updating the tests
- If you change the mock configuration (`utils/tests/mocks/comodo.yaml`), keep the other mocks in `utils/tests/mocks/` consistent with it,
  as the test runner reads its expectations from them.
- The test runner only copies `utils/comodo_config.py` and `utils/tests/mocks/` (see the [Dockerfile](Dockerfile)).
- The InfluxDB credentials are not overridden for the integration tests: if the `comodo-influx` volume already exists, the `INFLUX_*` values in `.env` must match the ones it was created with.
  If it needs any other shared code, add it to the Dockerfile.
