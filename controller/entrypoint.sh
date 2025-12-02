#!/bin/sh
set -e

# --- Secrets handling: *_FILE → plain env vars ---

if [ -n "${MQTT_PASS_FILE}" ] && [ -f "${MQTT_PASS_FILE}" ]; then
  MQTT_PASS="$(cat "${MQTT_PASS_FILE}")"
  export MQTT_PASS
fi

if [ -n "${INFLUX_TOKEN_FILE}" ] && [ -f "${INFLUX_TOKEN_FILE}" ]; then
  INFLUX_TOKEN="$(cat "${INFLUX_TOKEN_FILE}")"
  export INFLUX_TOKEN
fi

# --- Config Templating ---

CONFIG_TEMPLATE="/controller/config/config.json.template"
CONFIG_FILE="/controller/config/config.json"

if [ -f "$CONFIG_TEMPLATE" ]; then
  echo "Generating config.json from template using environment variables..."
  envsubst < "$CONFIG_TEMPLATE" > "$CONFIG_FILE"
else
  echo "Template $CONFIG_TEMPLATE not found!"
fi

# Hand off to original CMD (python -u controller.py)
exec "$@"