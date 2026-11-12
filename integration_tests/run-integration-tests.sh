#!/bin/bash
set -uo pipefail

help_str="
This script runs the integration tests using the mock configuration.
First, it backs up the existing 'comodo.yaml' and 'compose/firmware.yaml' files.
Then, it uses the mock configuration ('utils/tests/mocks/comodo.yaml', where all instruments are simulated) and generates a 'compose/firmware.yaml' to match it.
It then deploys every comodo stack with the mock configuration, using the commands from 'utils/contexts.sh' (so it is tested too),
and runs the test runner against it.
Finally, it tears the stacks down and restores 'comodo.yaml' and 'compose/firmware.yaml'.

By default all stacks run on this machine, ignoring the *_HOST variables in the 'compose/.env' file (with 'utils/contexts.sh --local').
With the --remote flag, the stacks are deployed exactly as configured in '.env'.
That is, stacks with both *_HOST and *_HOST_USER set are deployed to that host using docker contexts (see 'utils/contexts.sh').
This is useful to test the actual deployment topology.
The comodo docker contexts are replaced with ones matching '.env' (with 'utils/contexts.sh --clean'),
so they can be used to deploy afterwards.
The core comodo stack and the test runner, always run on the machine executing this script.

*Note:* The test stacks replace any comodo stack already running on the same hosts.

Usage: ./integration_tests/run-integration-tests.sh [--remote|-r] [--keep|-k] [--logs|-l SERVICES] [--help|-h]
Options:
  -r, --remote          Deploy the stacks as configured in .env, rather than all on this machine.
  -k, --keep            Leave the stacks running after the tests, e.g. to inspect them.
                          Note: The original 'comodo.yaml' and 'compose/firmware.yaml' are still restored, so you might have to use the --remove-orphans flag on the next deployment.
  -l, --logs SERVICES   Stream the logs of the given services (comma separated, e.g. 'controller,monitor')
                          into the output while the tests run, prefixed with the service name.
  -h, --help            Show this help message and exit.
"

remote=false
keep=false
log_services=()
log_pids=()

while [[ $# -gt 0 ]]; do
  case $1 in
  --help|-h)
    echo "$help_str"
    exit 0
    ;;
  --remote|-r)
    remote=true
    shift
    ;;
  --keep|-k)
    keep=true
    shift
    ;;
  --logs|-l)
    IFS=',' read -ra log_services <<< "${2:-}"
    shift 2
    ;;
  *)
    echo "Unknown option: $1"
    echo "$help_str"
    exit 1
    ;;
  esac
done

cd "$(dirname "$0")/.."
project_root=$(pwd)

if [[ ! -f compose/.env ]]; then
  echo "No .env file found in $project_root/compose. See the README to create one."
  exit 1
fi
source compose/.env

stacks=(mqtt data firmware core)
# The compose command for each stack, as printed by contexts.sh, so the tests also test it
declare -A commands

if [[ "$remote" == false ]]; then
  # Blank hosts make the test runner reach the stacks by service name, on the shared comodo network
  export MQTT_HOST="" DATA_HOST="" FIRMWARE_HOST=""
fi

# Runs a compose subcommand for the given stack, with the command from contexts.sh
stack_compose() {
  local stack="$1"
  shift
  [[ -z "${commands[$stack]:-}" ]] && return 1
  eval "${commands[$stack]} $(printf '%q ' "$@")"
}
runner_compose() {
  docker compose --env-file compose/.env -f integration_tests/compose.yaml "$@"
}

# Back up the configuration
backup_dir=$(mktemp -d)
echo "Backing up current configuration to $backup_dir..."
for f in comodo.yaml compose/firmware.yaml; do
  [[ -f "$f" ]] && cp "$f" "$backup_dir/$(basename "$f")"
done

# Kills a process and all its descendants (docker runs compose as a child process of its own)
kill_tree() {
  local child
  for child in $(pgrep -P "$1"); do
    kill_tree "$child"
  done
  kill "$1" 2>/dev/null
}

# Define the cleanup function to restore the configuration and tear down the stacks
cleanup() {
  # Don't let Ctrl+C interrupt the cleanup, or the configuration would not be restored
  trap '' INT TERM
  # Stop streaming logs (and the docker processes behind them), so the teardown output isn't flooded
  for pid in "${log_pids[@]}"; do
    kill_tree "$pid"
  done
  echo
  if [[ "$keep" == true ]]; then
    echo "Leaving the stacks running (--keep)."
  else
    echo "Tearing down the stacks..."
    runner_compose down --remove-orphans >/dev/null 2>&1
    for ((i = ${#stacks[@]} - 1; i >= 0; i--)); do
      stack_compose "${stacks[$i]}" down --remove-orphans 2>&1 | sed 's/^/  /'
    done
  fi
  echo "Restoring configuration..."
  for f in comodo.yaml compose/firmware.yaml; do
    if [[ -f "$backup_dir/$(basename "$f")" ]]; then
      cp "$backup_dir/$(basename "$f")" "$f"
    else
      rm -f "$f"
    fi
  done
  rm -rf "$backup_dir"
}
# Set up traps to call cleanup on exit or termination
trap cleanup EXIT
trap 'exit 130' INT TERM

# Get the compose commands for each stack from contexts.sh, which also creates the contexts for --remote
# (replacing existing ones, so they match .env) and regenerates compose/firmware.yaml
echo "Getting the deployment commands from contexts.sh..."
contexts_args=(--commands-file "$backup_dir/commands")
if [[ "$remote" == true ]]; then
  contexts_args+=(--clean)
else
  contexts_args+=(--local)
fi
./utils/contexts.sh "${contexts_args[@]}" || exit 1
while IFS=$'\t' read -r stack command; do
  commands[$stack]="$command"
done < "$backup_dir/commands"

# Set up the mock comodo.yaml and compose/firmware.yaml
echo "Setting up test configuration..."
cp utils/tests/mocks/comodo.yaml comodo.yaml
docker compose -f firmware/compose.gen.yaml run --rm compose-gen || exit 1

# Find the stack of each service to stream logs from
declare -A log_stacks
for service in "${log_services[@]}"; do
  for stack in "${stacks[@]}"; do
    if stack_compose "$stack" config --services 2>/dev/null | grep -qx "$service"; then
      log_stacks[$service]=$stack
      break
    fi
  done
  if [[ -z "${log_stacks[$service]:-}" ]]; then
    echo "Unknown service for --logs: $service"
    exit 1
  fi
done

# Start the stacks
echo "Starting the test stacks..."
for stack in "${stacks[@]}"; do
  echo
  echo "Starting the $stack stack: ${commands[$stack]} up ..."
  # The other stacks need the broker, so wait until it is healthy
  wait=""
  [[ "$stack" == mqtt ]] && wait="--wait"
  if ! stack_compose "$stack" up --build --detach --force-recreate --remove-orphans $wait; then
    echo "Could not start the $stack stack."
    exit 1
  fi
done

for service in "${log_services[@]}"; do
  echo "Streaming the logs of $service..."
  stack_compose "${log_stacks[$service]}" logs --follow "$service" &
  log_pids+=($!)
done

echo
echo "Running the integration tests..."
# Without a TTY (-T): a TTY puts the terminal in raw mode, which breaks the lines of the streamed logs.
# pytest then can't tell it is writing to a terminal, so ask for colours if this script is.
runner_args=()
[[ -t 1 ]] && runner_args+=(-e PYTEST_ADDOPTS=--color=yes)
# Tell pytest to end the line with the test's name, as the logs will be printed after it (see conftest.py)
[[ ${#log_services[@]} -gt 0 ]] && runner_args+=(-e STREAMING_LOGS=1)
runner_compose run --rm --build -T "${runner_args[@]}" integration-test
exit $?
