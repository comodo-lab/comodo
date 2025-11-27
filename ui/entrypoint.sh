#!/bin/sh
set -e

# Promote MQTT_PASS_FILE to MQTT_PASS if present
if [ -n "${MQTT_PASS_FILE}" ] && [ -f "${MQTT_PASS_FILE}" ]; then
  MQTT_PASS="$(cat "${MQTT_PASS_FILE}")"
  export MQTT_PASS
fi

# Promote INFLUX_TOKEN_FILE to INFLUX_TOKEN if present
if [ -n "${INFLUX_TOKEN_FILE}" ] && [ -f "${INFLUX_TOKEN_FILE}" ]; then
  INFLUX_TOKEN="$(cat "${INFLUX_TOKEN_FILE}")"
  export INFLUX_TOKEN
fi

# Hand off to the original command (python -u /app/app.py)
exec "$@"