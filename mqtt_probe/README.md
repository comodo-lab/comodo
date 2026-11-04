# MQTT Probe

The mqtt probe is used as a lightweight check to make sure the credentials and connection to the MQTT broker are working properly.

The service is used in each of the compose files (other than the mqtt broker) to provide a health check for the MQTT broker connection.
The other services in the same compose file wait for it before starting, with:
```yaml
depends_on:
  mqtt-probe-<id>:
    condition: service_healthy
```

## How it works
The probe runs [`probe.sh`](probe.sh) as the container's Docker health check.
Each check makes a round trip through the broker, using the provided credentials:
- It subscribes to `mqtt-probe/<MQTT_PROBE_ID>`.
- It publishes a message with a random id, `{"uid": <random number>}`, on the same topic.
- It checks that the same message is received back.

If any step fails, the check fails and the reason is printed in the health check log.

The health check runs every second while the container starts, and every 5 seconds after that.
After 5 consecutive failures (about 25 seconds), the probe is marked as unhealthy, and the services that depend on it will not start.
This usually means the broker is not running, `MQTT_HOST` is wrong, or the credentials don't match the broker's.

To see the result of the latest checks, run:
```shell
docker inspect --format '{{json .State.Health}}' <probe container>
```

## Configuration
- `MQTT_HOST`: The hostname of the MQTT broker. Defaults to `localhost`.
- `MQTT_PORT`: The port of the MQTT broker. Defaults to `1883`.
- `MQTT_USER` and `MQTT_PASS`: The credentials for the MQTT broker.
- `MQTT_PROBE_ID`: The id of the probe, used in its topic. Defaults to `probe`.
  Each compose file uses its own id: `core`, `data`, `firmware`, and `integration` for the [integration tests](../integration_tests/README.md).
