# Schemas

This directory holds the two schemas that define what Comodo accepts:
- [`comodo.yaml.schema`](#comodoyamlschema): The structure of the [central configuration file](../README.md#central-configuration-file), `comodo.yaml`.
- [`mqtt_schema.yaml`](#mqtt_schemayaml): The MQTT topics, and the messages sent on each of them.

## `comodo.yaml.schema`
A [LinkML](https://linkml.io/) schema for `comodo.yaml`.
It defines the `global` settings, and the `instruments` with their variables, sensors, actuators and setpoint controllers,
including which properties are required and their types.

It is used by the `config` service in the main [`compose.yaml`](../compose.yaml),
which validates `comodo.yaml` every time the core stack starts. The controller and UI only start if the validation passes.

To validate `comodo.yaml` without starting the stack, run from the repository root:
```shell
docker compose run --rm config
```

Some rules cannot be expressed in the schema, so the controller and UI also check them when loading `comodo.yaml`
(in [`utils/comodo_config.py`](../utils/comodo_config.py)).
For example, that every actuator's driving sensor has a `default_setpoint` and a `tolerance`.
When adding or changing a property, update both, as well as the [main README](../README.md#central-configuration-file).

## `mqtt_schema.yaml`
An [AsyncAPI 3.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0) specification of all MQTT messages in Comodo.
Each channel defines a topic (its `address`, which may use the `+` and `#` wildcards), and a JSON schema for the message `payload`.

It is used through [`utils/mqtt_validator.py`](../utils/mqtt_validator.py), which:
- Finds the channel whose `address` matches a message's topic. Messages on topics not in the schema are rejected.
- Validates the message's payload against that channel's schema. Only the first message defined in each channel is used.

The components use it to validate the messages they receive (controller, firmware and setpoint controllers),
and the [monitor](../monitor/README.md) uses it to check every message in the stack, and report any invalid ones.
The controller also uses the `ui/start` schema to validate experiments.

The file is copied into each component's image (at `/schemas/mqtt_schema.yaml`),
so the images need to be rebuilt (`--build`) for changes to take effect.

When adding a new topic, or changing a message, update this file accordingly,
otherwise the components will reject the messages, and the monitor will report them as errors.
For an overview of the topics, see [MQTT topics](../README.md#mqtt-topics) in the main README.
