#!/bin/bash
set -e

help_str="
This script configures docker contexts to facilitate deployment of the comodo stacks to remote hosts via SSH.

To generate the contexts, it reads the *_HOST and *_HOST_USER variables from the .env file.
Add/remove host usernames from your .env to switch between local and remote deployments.
Make sure you have SSH access to the remote hosts without password prompts (e.g., using SSH keys / SSH multiplexing).

Usage: ./utils/contexts.sh [--clean|-c] [--help|-h]
Options:
  --clean, -c       Removes existing contexts before creating new ones.
  --help,  -h       Show this help message and exit.
"

clean=false

while [[ $# -gt 0 ]]; do
  case $1 in
  --help|-h)
    echo "$help_str"
    exit 0
    ;;
  --clean|-c)
    clean=true
    shift
    ;;
  *)
    echo "Unknown option: $1"
    echo "$help_str"
    exit 1
    ;;
  esac
done

cd $(dirname "$0")
source ../.env

existing_contexts=$(docker context ls --format '{{.Name}}' | grep 'comodo_' || true)
if [ ! -z "$existing_contexts" ] && [ "$clean" != true ]; then
  echo "WARNING: Existing comodo docker contexts detected:"
  echo "$existing_contexts"
  echo "Use --clean to remove them before creating new ones."
  echo "I will continue without overwriting existing contexts."
  echo ""
fi

if [ "$clean" = true ]; then
  echo "Removing existing docker contexts..."
  if [[ "$existing_contexts" == *"comodo_mqtt_host"* ]]; then
    docker context rm -f comodo_mqtt_host || true
  fi
  if [[ "$existing_contexts" == *"comodo_data_host"* ]]; then
    docker context rm -f comodo_data_host || true
  fi
  if [[ "$existing_contexts" == *"comodo_firmware_host"* ]]; then
    docker context rm -f comodo_firmware_host || true
  fi
  echo ""
fi

mqtt_local=true
data_local=true
firmware_local=true

echo "Configuring docker contexts..."
if [ ! -z "${MQTT_HOST_USER}" ] && [ ! -z "${MQTT_HOST}" ]; then
  docker context create comodo_mqtt_host --docker "host=ssh://${MQTT_HOST_USER}@${MQTT_HOST}"
  mqtt_local=false
fi

if [ ! -z "${DATA_HOST_USER}" ] && [ ! -z "${DATA_HOST}" ]; then
  docker context create comodo_data_host --docker "host=ssh://${DATA_HOST_USER}@${DATA_HOST}"
  data_local=false
fi

if [ ! -z "${FIRMWARE_HOST_USER}" ] && [ ! -z "${FIRMWARE_HOST}" ]; then
  docker context create comodo_firmware_host --docker "host=ssh://${FIRMWARE_HOST_USER}@${FIRMWARE_HOST}"
  firmware_local=false
fi

echo ""
echo "Deploy remote stacks with:"
if [ "$mqtt_local" = false ]; then
  echo "  docker --context comodo_mqtt_host compose -f compose.mqtt.yaml up --build -d"
fi
if [ "$data_local" = false ]; then
  echo "  docker --context comodo_data_host compose -f compose.data.yaml up --build -d"
fi
if [ "$firmware_local" = false ]; then
  echo "  docker --context comodo_firmware_host compose -f compose.firmware.yaml up --build -d"
fi
echo "Deploy local stacks with:"
if [ "$mqtt_local" = true ]; then
  echo "  docker compose -f compose.mqtt.yaml up --build -d"
fi
if [ "$data_local" = true ]; then
  echo "  docker compose -f compose.data.yaml up --build -d"
fi
if [ "$firmware_local" = true ]; then
  echo "  docker compose -f compose.firmware.yaml up --build -d"
fi

echo "  docker compose up --build -d"

echo ""