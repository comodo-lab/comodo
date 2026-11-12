#!/bin/bash
set -uo pipefail

help_str="
Deploys the comodo stacks (--deploy), as configured in the 'compose/.env' file and 'comodo.yaml', or brings them down (--down).

It runs the commands printed by 'utils/contexts.sh --clean', which also replaces the comodo docker contexts
with ones matching '.env', and regenerates 'compose/firmware.yaml'. In order, stopping at the first failure, it:
  1. Validates 'comodo.yaml'.
  2. Asks before replacing any comodo stacks already running (unless --force).
  3. Optionally (-t), runs the integration tests on the same hosts, with the mock configuration (see 'integration_tests/').
  4. Deploys the MQTT broker, and then the data, firmware and core stacks.
With --down, it asks before bringing down any running stacks (unless --force), and brings them down in reverse order.

Usage: ./comodo.sh (--deploy|--down) [--force|-f] [--test|-t] [--local|-l]
       ./comodo.sh --help|-h
Actions:
  --deploy          Deploy the stacks.
  --down            Bring the stacks down, in reverse order.
  --help,  -h       Show this help message and exit.
Options:
  --force, -f       Replace (or, with --down, bring down) running stacks without asking,
                      and recreate every container (e.g. after editing 'comodo.yaml').
  --test,  -t       Run the integration tests with --remote before deploying, and only deploy if they pass.
                      Note: The tests replace any running stacks.
  --local, -l       Deploy all the stacks on this machine, ignoring the *_HOST variables (see 'utils/contexts.sh --local').
"

action=""
force=false
test=false
local_only=false

while [[ $# -gt 0 ]]; do
  case $1 in
  --help|-h)
    echo "$help_str"
    exit 0
    ;;
  --force|-f)
    force=true
    shift
    ;;
  --test|-t)
    test=true
    shift
    ;;
  --local|-l)
    local_only=true
    shift
    ;;
  --deploy|--down)
    if [[ -n "$action" && "$action" != "$1" ]]; then
      echo "Use either --deploy or --down, not both."
      exit 1
    fi
    action="$1"
    shift
    ;;
  *)
    echo "Unknown option: $1"
    echo "$help_str"
    exit 1
    ;;
  esac
done

if [[ -z "$action" ]]; then
  echo "$help_str"
  exit 1
fi

cd "$(dirname "$0")"
project_root=$(pwd)

if [[ ! -f compose/.env ]]; then
  echo "No .env file found in $project_root/compose. See the README to create one."
  exit 1
fi
if [[ "$test" == true && "$action" == --down ]]; then
  echo "--test only applies to --deploy."
  exit 1
fi
if [[ "$test" == true && "$local_only" == true ]]; then
  echo "--test runs the integration tests on the hosts in .env, so it can't be used with --local."
  exit 1
fi

stacks=(mqtt data firmware core)
# The compose command for each stack, as printed by contexts.sh
declare -A commands

# Runs a compose subcommand for the given stack, with the command from contexts.sh
stack_compose() {
  local stack="$1"
  shift
  eval "${commands[$stack]} $(printf '%q ' "$@")"
}

# Asks before replacing (or bringing down) the stacks that are running, unless --force
confirm_running_stacks() {
  local action="$1"
  local running=()
  for stack in "${stacks[@]}"; do
    if [[ -n "$(stack_compose "$stack" ps --quiet 2>/dev/null)" ]]; then
      running+=("$stack")
    fi
  done
  if [[ ${#running[@]} -eq 0 || "$force" == true ]]; then
    return 0
  fi
  echo
  echo "These comodo stacks are running: ${running[*]}"
  if [[ ! -t 0 ]]; then
    echo "Use --force to $action without asking."
    exit 1
  fi
  read -r -p "Do you want to $action? [y/N] " answer
  if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "Nothing was changed."
    exit 1
  fi
}

# Gets the compose commands for each stack from contexts.sh.
# Always replacing the contexts, so they match .env, rather than deploying to the hosts of old ones.
load_commands() {
  local commands_file
  commands_file=$(mktemp)
  local contexts_args=(--commands-file "$commands_file" --clean)
  [[ "$local_only" == true ]] && contexts_args+=(--local)
  if ! ./utils/contexts.sh "${contexts_args[@]}"; then
    rm -f "$commands_file"
    exit 1
  fi
  while IFS=$'\t' read -r stack command; do
    commands[$stack]="$command"
  done < "$commands_file"
  rm -f "$commands_file"
}

if [[ "$action" == --down ]]; then
  load_commands
  confirm_running_stacks "bring them down"
  echo "Bringing down the stacks..."
  for ((i = ${#stacks[@]} - 1; i >= 0; i--)); do
    echo
    echo "Bringing down the ${stacks[$i]} stack: ${commands[${stacks[$i]}]} down ..."
    stack_compose "${stacks[$i]}" down --remove-orphans
  done
  exit 0
fi

# Validate comodo.yaml first, so a bad configuration doesn't leave a half-deployed stack
echo "Validating comodo.yaml..."
if ! docker compose -f compose/core.yaml run --rm config; then
  echo "comodo.yaml is not valid. Nothing was deployed."
  exit 1
fi

load_commands
# Before the tests too, as they also replace the running stacks
confirm_running_stacks "replace them"

if [[ "$test" == true ]]; then
  echo
  echo "Running the integration tests on the deployment hosts..."
  if ! ./integration_tests/run-integration-tests.sh --remote; then
    echo "The integration tests failed. Nothing was deployed."
    exit 1
  fi
fi

echo "Deploying the stacks..."
for stack in "${stacks[@]}"; do
  echo
  echo "Deploying the $stack stack: ${commands[$stack]} up ..."
  # The other stacks need the broker, so wait until it is healthy
  wait=""
  [[ "$stack" == mqtt ]] && wait="--wait"
  # If not forced, only the containers whose compose configuration changed are recreated
  recreate=""
  [[ "$force" == true ]] && recreate="--force-recreate"
  if ! stack_compose "$stack" up --build --detach --remove-orphans $wait $recreate; then
    echo "Could not deploy the $stack stack. The stacks before it are still running."
    exit 1
  fi
done

echo
echo "Comodo is deployed. The UI is available at http://localhost:8501 on this machine."
