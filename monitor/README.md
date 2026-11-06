# Monitor

The monitor checks that every MQTT message in the Comodo stack is valid.

It subscribes to all topics (`#`), and validates each message against the [message schema](../schemas/mqtt_schema.yaml)
(an AsyncAPI specification, through [`utils/mqtt_validator.py`](../utils/mqtt_validator.py)).
It does not change any message, or the behaviour of any other component: it only reports problems.

- [Monitor](#monitor)
  - [Errors](#errors)
  - [Configuration](#configuration)
  - [Running tests](#running-tests)

## Errors
Invalid messages are reported on the `error/message` topic (and printed to the monitor's logs), and shown in the UI's log.
There are three kinds of error, identified by their `code`:
- `unexpected_topic`: The topic is not defined in the message schema.
  ```json
  {"code": "unexpected_topic", "message": "Unexpected topic: <topic>"}
  ```
- `invalid_json`: The payload is not valid JSON (or not valid UTF-8).
  ```json
  {"code": "invalid_json", "message": "<JSON error>", "topic": "<topic>"}
  ```
- `validation_error`: The payload does not match the schema for its topic.
  `failed_check` is the JSON schema check that failed (e.g. `required`, `type`), and `offending_key` is the path to the offending key in the payload (or `<root>`).
  ```json
  {"code": "validation_error", "message": "<schema error>", "topic": "<topic>", "failed_check": "<check>", "offending_key": "<key>"}
  ```

Any other error while validating a message (e.g. a missing or broken message schema) is a problem with the monitor,
so it is published on `error/monitor` instead, without stopping the monitor:
```json
{"code": "exception", "message": "Could not validate message on <topic>: <error>"}
```
If the monitor itself crashes (in practice, while starting, e.g. if it can't reach the broker), it publishes the error on `error/monitor` too, with the same `code`,
or only prints it if it couldn't create its publisher. It then exits with the error, so docker restarts it.

When adding a new MQTT topic, or changing a message, update the [message schema](../schemas/mqtt_schema.yaml) accordingly,
otherwise the monitor will report the new messages as errors.

## Configuration
The monitor is part of the core stack (the main [`compose.yaml`](../compose.yaml)), and reads the following environment variables:
- `MQTT_HOST`: The hostname of the MQTT broker. Defaults to `localhost`, but the compose file sets it from `.env`,
  or to `rabbitmq` (the broker's service name) if it is empty.
- `MQTT_USER`: The username for the MQTT broker. Defaults to `guest`.
- `MQTT_PASS`: The password for the MQTT broker. Defaults to `guest`.

## Running tests
The tests are in [`tests/`](tests/):
- `unit/`: Each function of the monitor, with the validator, the MQTT clients, and the monitor's other functions mocked.
- `integration/`: The monitor started with `monitor()`, validating messages against the real [message schema](../schemas/mqtt_schema.yaml),
  over an in-memory message bus instead of a broker. This also checks that the monitor's own error messages are valid.

From the `monitor/` directory, run:
```shell
docker compose up --build
```

To check the coverage report after the tests have run:
```shell
xdg-open $(docker volume inspect monitor-tests_memory -f '{{ .Mountpoint }}')/htmlcov/class_index.html
```
