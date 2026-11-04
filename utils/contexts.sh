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

echo ""
cd $(dirname "$0")
project_root=$(cd .. && pwd)
docker compose -f "$project_root/firmware/compose.gen.yaml" run --rm compose-gen
unset DOCKER_HOST
source "$project_root/.env"
source "$project_root/utils/local_ip.sh"

existing_contexts=$(docker context ls --format '{{.Name}}' | grep 'comodo_' || true)
if [ ! -z "$existing_contexts" ] && [ "$clean" != true ]; then
  echo -e "\033[31mWARNING:\033[0m Existing comodo docker contexts detected:"
  echo "$existing_contexts" | while IFS= read -r line; do
    echo "  $line"
  done
  echo "Use --clean to remove them before creating new ones."
  echo "I will continue without overwriting existing contexts."
  echo ""
fi

if [ "$clean" = true ]; then
  echo "Removing existing docker contexts..."
  if [[ -z "$existing_contexts" ]]; then
    echo "  No pre-existing comodo contexts found."
  fi
  if [[ "$existing_contexts" == *"comodo_mqtt_host"* ]]; then
    docker context rm -f comodo_mqtt_host 2>&1 | sed 's/^/  /' || true
  fi
  if [[ "$existing_contexts" == *"comodo_data_host"* ]]; then
    docker context rm -f comodo_data_host 2>&1 | sed 's/^/  /' || true
  fi
  if [[ "$existing_contexts" == *"comodo_firmware_host"* ]]; then
    docker context rm -f comodo_firmware_host 2>&1 | sed 's/^/  /' || true
  fi
  echo ""
fi

mqtt_local=true
data_local=true
firmware_local=true

echo "Configuring docker contexts..."
if [ ! -z "${MQTT_HOST_USER}" ] && [ ! -z "${MQTT_HOST}" ]; then
  docker context create comodo_mqtt_host --docker "host=ssh://${MQTT_HOST_USER}@${MQTT_HOST}" 2>&1 | sed 's/^/  /' || true
  mqtt_local=false
fi

if [ ! -z "${DATA_HOST_USER}" ] && [ ! -z "${DATA_HOST}" ]; then
  docker context create comodo_data_host --docker "host=ssh://${DATA_HOST_USER}@${DATA_HOST}" 2>&1 | sed 's/^/  /' || true
  data_local=false
fi

if [ ! -z "${FIRMWARE_HOST_USER}" ] && [ ! -z "${FIRMWARE_HOST}" ]; then
  docker context create comodo_firmware_host --docker "host=ssh://${FIRMWARE_HOST_USER}@${FIRMWARE_HOST}" 2>&1 | sed 's/^/  /' || true
  firmware_local=false
fi

# With a blank MQTT_HOST the broker is local, so give the remote stacks this machine's IP address to reach it
data_mqtt=""
firmware_mqtt=""
if [ -z "${MQTT_HOST}" ] && { [ "$data_local" = false ] || [ "$firmware_local" = false ]; }; then
  seeded=()
  for stack in data firmware; do
    local_var="${stack}_local"
    host_var="${stack^^}_HOST"
    if [ "${!local_var}" = false ]; then
      ip=$(local_ip_for "${!host_var}")
      if [ -z "$ip" ]; then
        echo -e "\033[31mERROR:\033[0m Could not find the IP address this machine uses to reach ${!host_var}."
        echo "  Set MQTT_HOST to an address of this machine that the remote hosts can reach."
        exit 1
      fi
      declare "${stack}_mqtt=MQTT_HOST=$ip "
      seeded+=("$stack: $ip (from ${!host_var})")
    fi
  done
  local_ip_note "${seeded[@]}"
fi

echo ""
echo ""
# The broker has to be up first: the other stacks check they can reach it before starting
echo "Deploy the stacks, in this order, with:"
mqtt_context=""
data_context=""
firmware_context=""
if [ "$mqtt_local" = false ]; then mqtt_context="--context comodo_mqtt_host "; fi
if [ "$data_local" = false ]; then data_context="--context comodo_data_host "; fi
if [ "$firmware_local" = false ]; then firmware_context="--context comodo_firmware_host "; fi
echo "  docker ${mqtt_context}compose -f compose.mqtt.yaml up --build -d --wait"
echo "  ${data_mqtt}docker ${data_context}compose -f compose.data.yaml up --build -d"
echo "  ${firmware_mqtt}docker ${firmware_context}compose -f compose.firmware.yaml up --build -d"
echo "  docker compose up --build -d"

echo ""
