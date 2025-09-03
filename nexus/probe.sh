#!/bin/sh
set -e

HOST="${MQTT_HOST:-localhost}"
PORT="${MQTT_PORT:-1883}"
USER="${MQTT_USER:-}"
PASS="${MQTT_PASS:-}"

TOPIC="healthcheck/$RANDOM"

AUTH_ARGS=""
if [ -n "$USER" ] && [ -n "$PASS" ]; then
  AUTH_ARGS="-u $USER -P $PASS"
fi

# Subscribe in the background (waits for 1 message)
timeout 5 mosquitto_sub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -C 1 > /tmp/msg.$$ &
SUB_PID=$!

sleep 1  # give subscriber a moment to connect

# Publish a test message
mosquitto_pub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -m "ok" || exit 1

# Wait for subscriber to get it
wait $SUB_PID || exit 1

exit 0
