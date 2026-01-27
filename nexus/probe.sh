#!/bin/sh
set -e

HOST="${MQTT_HOST:-localhost}"
PORT="${MQTT_PORT:-1883}"
USER="${MQTT_USER:-}"
PASS="${MQTT_PASS:-}"

TIMEOUT=5
HEALTH_FILE=/tmp/mqtt-health
SLEEP_HEALTHY=${SLEEP_HEALTHY:-30}
SLEEP_UNHEALTHY=${SLEEP_UNHEALTHY:-4}

AUTH_ARGS=""
if [ -n "$USER" ] && [ -n "$PASS" ]; then
  AUTH_ARGS="-u $USER -P $PASS"
fi

probe_once() {
  TOPIC="mqtt-probe/$RANDOM"

  timeout $TIMEOUT mosquitto_sub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -C 1 2>/dev/null &
  SUB_PID=$!

  sleep 1

  timeout $TIMEOUT mosquitto_pub -h "$HOST" -p "$PORT" $AUTH_ARGS -t "$TOPIC" -m '{"status":"ok"}' 2>&1
  PUB_STATUS=$?

  set +e
  wait $SUB_PID
  SUB_STATUS=$?
  set -e

  if [ $SUB_STATUS -ne 0 ] || [ $PUB_STATUS -ne 0 ]; then
    if [ $SUB_STATUS -eq 143 ] || [ $PUB_STATUS -eq 143 ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') Timeout (no route to host?)"
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') Pub status: $PUB_STATUS, Sub status: $SUB_STATUS"
    return 1
  else
    return 0
  fi
}

while true; do
  if probe_once; then
    echo "0" > "$HEALTH_FILE"
    sleep "$SLEEP_HEALTHY"
  else
    echo "1" > "$HEALTH_FILE"
    sleep "$SLEEP_UNHEALTHY"
  fi
done
