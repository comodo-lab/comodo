#!/bin/bash
set -e

help_str="
This script configures docker contexts to facilitate deployment of the comodo stacks to remote hosts via SSH.

To generate the contexts, it reads the *_HOST and *_HOST_USER variables from the .env file.
Add/remove host usernames from your .env to switch between local and remote deployments.
Make sure you have SSH access to the remote hosts without password prompts (e.g., using SSH keys / SSH multiplexing).

If MQTT_HOST is blank (the broker runs on this machine), the remote stacks are given this machine's IP address to reach it.

Usage: ./utils/contexts.sh [--clean|-c] [--local|-l] [--commands-file|-o FILE] [--help|-h]
Options:
  --clean, -c             Removes existing contexts before creating new ones.
  --local, -l             Deploy all the stacks on this machine, ignoring the *_HOST and *_HOST_USER variables.
  --commands-file, -o     Also write the compose command for each stack to FILE, as '<stack><TAB><command>' lines,
                          without the compose subcommand (e.g. 'up'). Used by run-integration-tests.sh.
  --help,  -h             Show this help message and exit.
"

clean=false
local_only=false
commands_file=""

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
  --local|-l)
    local_only=true
    shift
    ;;
  --commands-file|-o)
    commands_file="$2"
    shift 2
    ;;
  *)
    echo "Unknown option: $1"
    echo "$help_str"
    exit 1
    ;;
  esac
done

# Relative to where the script was called from, before changing directory
if [ ! -z "$commands_file" ]; then
  commands_file=$(realpath -m "$commands_file")
fi

echo ""
cd $(dirname "$0")
project_root=$(cd .. && pwd)
docker compose -f "$project_root/firmware/compose.gen.yaml" run --rm compose-gen
unset DOCKER_HOST
source "$project_root/.env"

# Prints the IP address this machine uses to reach the given host (an IP address or a name),
# or nothing if the host can't be resolved or reached.
local_ip_for() {
  local target
  target=$(getent ahostsv4 "$1" 2>/dev/null | awk '{print $1; exit}')
  [ -z "$target" ] && target="$1"
  ip route get "$target" 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}'
}

if [ "$local_only" = true ]; then
  # Without hosts, no contexts are created, and every stack is deployed on this machine
  MQTT_HOST_USER=""
  DATA_HOST_USER=""
  FIRMWARE_HOST_USER=""
fi

existing_contexts=$(docker context ls --format '{{.Name}}' | grep 'comodo_' || true)
if [ ! -z "$existing_contexts" ] && [ "$clean" != true ] && [ "$local_only" != true ]; then
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
  echo ""
  echo -e "\033[33mNOTE:\033[0m MQTT_HOST is blank, so the broker runs on this machine, where the local stacks reach it by name."
  echo "  The remote stacks can't, so they are given the IP address this machine uses to reach them:"
  for line in "${seeded[@]}"; do
    echo "    $line"
  done
  echo "  If this machine's IP address changes, the remote stacks will lose the broker until they are redeployed."
  echo "  To avoid this, set MQTT_HOST to a fixed address or hostname of this machine."
fi

# The compose command for each stack, without the subcommand
stacks=(mqtt data firmware core)
declare -A files=([mqtt]=compose.mqtt.yaml [data]=compose.data.yaml [firmware]=compose.firmware.yaml [core]=compose.yaml)
declare -A commands
for stack in "${stacks[@]}"; do
  local_var="${stack}_local"
  mqtt_var="${stack}_mqtt"
  env_prefix="${!mqtt_var:-}"
  context=""
  if [ "${!local_var:-true}" = false ]; then
    context="--context comodo_${stack}_host "
  fi
  if [ "$local_only" = true ]; then
    # Blank hosts override the ones in .env, so the stacks reach each other by service name
    env_prefix="MQTT_HOST= DATA_HOST= "
  fi
  commands[$stack]="${env_prefix}docker ${context}compose -f ${files[$stack]}"
done

echo ""
echo ""
# The broker has to be up first: the other stacks check they can reach it before starting
echo "Deploy the stacks, in this order, with:"
echo "  ${commands[mqtt]} up --build -d --wait"
echo "  ${commands[data]} up --build -d"
echo "  ${commands[firmware]} up --build -d"
echo "  ${commands[core]} up --build -d"

if [ ! -z "$commands_file" ]; then
  : > "$commands_file"
  for stack in "${stacks[@]}"; do
    printf '%s\t%s\n' "$stack" "${commands[$stack]}" >> "$commands_file"
  done
fi

echo ""
