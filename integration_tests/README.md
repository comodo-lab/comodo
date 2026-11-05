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
The tests are run by [`integration_tests/run-integration-tests.sh`](run-integration-tests.sh), which:
1. Backs up `comodo.yaml` and `compose.firmware.yaml`, copies the mock configuration ([`utils/tests/mocks/comodo.yaml`](../utils/tests/mocks/comodo.yaml)) in their place, and regenerates `compose.firmware.yaml`.
   The instruments in the mock configuration are all simulated.
2. Deploys every stack with its own compose file, using the commands printed by [`utils/contexts.sh`](../utils/contexts.sh), so it is tested too:
   the MQTT broker (`compose.mqtt.yaml`), the data stack (`compose.data.yaml`), the firmware stack (`compose.firmware.yaml`), and the core stack (`compose.yaml`).
3. Runs the test runner ([`runner.py`](runner.py), with pytest), using [this compose file](compose.yaml).
4. Tears the stacks down, and restores `comodo.yaml` and `compose.firmware.yaml`, however the script exits.

The test runner uses the same mocks (and the experiment in [`utils/tests/mocks/mock_experiment.py`](../utils/tests/mocks/mock_experiment.py)) to know what to expect.
It reads `controller/data/` (read only) to check the database dump, so it has to run on the same machine as the core stack.

### Local and remote (commissioning) tests
By default, every stack runs on this machine, whatever the `*_HOST` variables in `.env` are (with `utils/contexts.sh --local`).
This is how the tests run in CI.

With `--remote`, the stacks are deployed exactly as configured in `.env`:
stacks with both `*_HOST` and `*_HOST_USER` set are deployed to that host with docker contexts (see [`utils/contexts.sh`](../utils/contexts.sh)),
and the rest on this machine. The core stack, and the test runner, always run on this machine.
The existing comodo docker contexts are replaced with ones matching `.env` (with `utils/contexts.sh --clean`), so they can be used to deploy afterwards.
This works as a commissioning test of an actual deployment (networking, hosts and credentials), with simulated instruments,
before deploying it with the real `comodo.yaml`.

Note that, in both cases, the stacks replace any comodo stack already running on the same hosts, and use the same volumes and `controller/data/` folder.
So the test data is added to InfluxDB, and each run adds an experiment to `controller/data/`.

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
The tests need a `.env` file in the repository root, with at least `MQTT_USER`, `MQTT_PASS`, `INFLUX_TOKEN`, `INFLUX_BUCKET` and `INFLUX_ORG`
(see [environment variables](../README.md#environment-variables)). For `--remote`, it also needs the hosts and users of the remote stacks.

From the repository root, run:
```shell
./integration_tests/run-integration-tests.sh            # All stacks on this machine
./integration_tests/run-integration-tests.sh --remote   # Stacks deployed as configured in .env
```
Run `./integration_tests/run-integration-tests.sh --help` for all options.

The tests are also run by [`utils/run-all-tests.sh`](../utils/run-all-tests.sh), and in CI on pushes that change any component, and on pull requests to `main` and `dev`
(see [`.github/workflows/integration_tests.yml`](../.github/workflows/integration_tests.yml)).

### Debugging
The output only shows the test runner's prints. To inspect the stacks after the tests, keep them running with `--keep`, and check the logs of a service, e.g.:
```shell
docker logs comodo-controller
```
`comodo.yaml` and `compose.firmware.yaml` are still restored, so use `--remove-orphans` the next time you deploy the firmware stack.

With the stacks running with the mock configuration, the test runner can also be run on its own:
```shell
docker compose --env-file .env -f integration_tests/compose.yaml run --rm --build integration-test
```

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
  If it needs any other shared code, add it to the Dockerfile.
- If the `comodo-influx` volume already exists, the `INFLUX_*` values in `.env` must match the ones it was created with.
