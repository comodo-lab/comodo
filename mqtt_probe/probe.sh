#!/bin/sh
set -e

MQTT_PROBE_ID="${MQTT_PROBE_ID:-probe}"

HOST="${MQTT_HOST:-localhost}"
PORT="${MQTT_PORT:-1883}"
USER="${MQTT_USER:-}"
PASS="${MQTT_PASS:-}"

AUTH_ARGS=""
if [ -n "$USER" ] && [ -n "$PASS" ]; then
  AUTH_ARGS="-u $USER -P $PASS"
fi

TOPIC="mqtt-probe/${MQTT_PROBE_ID}"
UID_VAL=$RANDOM
TMP=$(mktemp)

mosquitto_sub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -C 1 > "$TMP" &
SUB_PID=$!

sleep 1

mosquitto_pub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -m "{\"uid\":$UID_VAL}" >/dev/null 2>&1
PUB_STATUS=$?

set +e
wait $SUB_PID
SUB_STATUS=$?
set -e

if [ $SUB_STATUS -ne 0 ] || [ $PUB_STATUS -ne 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') Pub status: $PUB_STATUS, Sub status: $SUB_STATUS"
  rm -f "$TMP"
  exit 1
fi

if ! grep -q "\"uid\":$UID_VAL" "$TMP"; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') UID mismatch"
  rm -f "$TMP"
  exit 1
fi

rm -f "$TMP"
exit 0
