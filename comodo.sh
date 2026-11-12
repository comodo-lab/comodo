#!/bin/bash
set -uo pipefail

help_str="
Deploys the comodo stacks (--deploy), as configured in the 'compose/.env' file and 'comodo.yaml', or brings them down (--down).

It runs the commands printed by 'utils/contexts.sh --clean', which also replaces the comodo docker contexts
with ones matching '.env', and regenerates 'compose/firmware.yaml'. In order, stopping at the first failure, it:
  1. Validates 'comodo.yaml'.
  2. Asks before replacing any comodo stacks already running (unless --yes).
  3. Optionally (-t), runs the integration tests on the same hosts, with the mock configuration (see 'integration_tests/').
  4. Gets the images of every stack ready on its host, so nothing is deployed if any of them can't be.
  5. Deploys the MQTT broker, and then the data, firmware and core stacks.

By default, it tries to pull the published comodo images (comodolab/comodo-*). With -b, it builds them from the local code.
With --down, it asks before bringing down any running stacks (unless --yes), and brings them down in reverse order.

Usage:
  ./comodo.sh --deploy [--yes|-y] [--local|-l] [--force|-f] [--test|-t] [--build|-b]
  ./comodo.sh --down [--yes|-y] [--local|-l]
  ./comodo.sh --help|-h

Options for --deploy and --down:
  --yes,   -y       Replace (or bring down) running stacks without asking.
  --local, -l       Use this machine for all the stacks, ignoring the *_HOST variables (see 'utils/contexts.sh --local').
                      To bring down stacks deployed with --local, use --local too.
Options for --deploy only:
  --force, -f       Recreate every container, rather than only those whose compose configuration changed
                      (e.g. after editing 'comodo.yaml', which is mounted).
  --test,  -t       Run the integration tests with --remote before deploying, and only deploy if they pass.
                      Note: The tests replace any running stacks, and always build the images from this repository.
  --build, -b       Build the comodo images from the local code, rather than using the published ones.  Use --build only when developing.
                      Built images are tagged 'local' (COMODO_TAG=local), so they are never mistaken for (or pushed as) published ones.
"

action=""
yes=false
force=false
build=false
test=false
local_only=false

while [[ $# -gt 0 ]]; do
  case $1 in
  --help|-h)
    echo "$help_str"
    exit 0
    ;;
  --yes|-y)
    yes=true
    shift
    ;;
  --force|-f)
    force=true
    shift
    ;;
  --build|-b)
    build=true
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
if [[ "$action" == --down && ( "$build" == true || "$test" == true || "$force" == true ) ]]; then
  echo "--build, --force and --test only apply to --deploy."
  exit 1
fi
if [[ "$test" == true && "$local_only" == true ]]; then
  echo "--test runs the integration tests on the hosts in .env, so it can't be used with --local."
  exit 1
fi

# Coloured when printing to a terminal, so each stack's step stands out from the compose output
if [[ -t 1 ]]; then
  yellow=$'\e[33m' bold=$'\e[1m' unbold=$'\e[22m' reset=$'\e[0m'
else
  yellow="" bold="" unbold="" reset=""
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

# Prints, and then runs, a compose subcommand for the given stack
run_stack_compose() {
  local stack="$1"
  shift
  echo "  ${commands[$stack]} $*"
  stack_compose "$stack" "$@"
}

# Asks before replacing (or bringing down) the stacks that are running, unless --yes
confirm_running_stacks() {
  local action="$1"
  local running=()
  for stack in "${stacks[@]}"; do
    if [[ -n "$(stack_compose "$stack" ps --quiet 2>/dev/null)" ]]; then
      running+=("$stack")
    fi
  done
  if [[ ${#running[@]} -eq 0 || "$yes" == true ]]; then
    return 0
  fi
  echo
  echo "These comodo stacks are running: ${running[*]}"
  if [[ ! -t 0 ]]; then
    echo "Use --yes to $action without asking."
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
    echo "${yellow}Bringing down the ${bold}${stacks[$i]}${unbold} stack:${reset}"
    run_stack_compose "${stacks[$i]}" down --remove-orphans
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

if [[ "$build" == true ]]; then
  export COMODO_TAG=local
  echo "${yellow}${bold}Building${unbold} comodo images from local code${reset} (tagging as: '$COMODO_TAG')..."
else
  # As in the compose files, unless set in the shell, or in compose/.env (which the compose commands read)
  tag=$(grep -s -E '^COMODO_TAG=' compose/.env | tail -1 | cut -d= -f2-)
  echo "${yellow}${bold}Pulling${unbold} comodo images from Dockerhub${reset} (looking for tag: '${COMODO_TAG:-${tag:-latest}}')..."
fi

# Get the images of every stack ready (on each stack's host), so nothing is deployed if any of them can't be.
# Checks all the stacks, so all problems are reported on a single run.
problems=()
missing_images=false
for stack in "${stacks[@]}"; do
  echo
  echo "${yellow}Preparing the images of the ${bold}${stack}${unbold} stack:${reset}"
  if [[ "$build" == true ]]; then
    run_stack_compose "$stack" build || problems+=("Could not build the images of the $stack stack.")
    continue
  fi

  # Classify services as part of comodo (with images comodolab/comodo-*) or 'other'.
  comodo_services=()
  comodo_images=()
  other_services=()
  while read -r service image; do
    if [[ "$image" == comodolab/* ]]; then
      comodo_services+=("$service")
      comodo_images+=("$image")
    else
      other_services+=("$service")
    fi
  done < <(stack_compose "$stack" config | awk '
    /^services:/ { in_services = 1; next }
    /^[^ ]/ { in_services = 0 }
    in_services && /^  [^ ]/ { service = $1; sub(/:$/, "", service); print service }
    in_services && /^    image: / { print service, $2 }' |
    # A line per service, with its image if it has one
    awk '{ image[$1] = $2 } END { for (s in image) print s, image[s] }' | sort)

  # Pull comodo images if it can, carrying on with the ones it already has if it can't (e.g. without internet access)
  if [[ ${#comodo_services[@]} -gt 0 ]]; then
    run_stack_compose "$stack" pull --ignore-pull-failures "${comodo_services[@]}"
  fi
  # Configure 'other' (non-comodo) images (rabbitmq, telegraf, grafana...)
  if [[ ${#other_services[@]} -gt 0 ]] && ! run_stack_compose "$stack" build "${other_services[@]}"; then
    problems+=("Could not build the images of the $stack stack.")
  fi
  # Make sure all the comodo images exist on the corresponding host
  missing=()
  for image in $(printf '%s\n' "${comodo_images[@]}" | sort -u); do
    eval "${commands[$stack]%% compose *} image inspect $(printf '%q' "$image")" > /dev/null 2>&1 || missing+=("$image")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    problems+=("These comodo images are not on the $stack stack's host, and could not be pulled: ${missing[*]}")
    missing_images=true
  fi
done
# Report any problems, and exit without deploying anything if there are any.
if [[ ${#problems[@]} -gt 0 ]]; then
  echo
  printf '%s\n' "${problems[@]}"
  if [[ "$missing_images" == true ]]; then
    echo "Check the hosts can pull the missing images (and that they are published with that tag), or use --build to build them from this repository."
  fi
  echo "Nothing was deployed."
  exit 1
fi

# Deploy the stacks, with the images prepared above
for stack in "${stacks[@]}"; do
  echo
  echo "${yellow}Deploying the ${bold}${stack}${unbold} stack:${reset}"
  args=(up --detach --remove-orphans --no-build)
  # The other stacks need the broker, so wait until it is healthy
  [[ "$stack" == mqtt ]] && args+=(--wait)
  # If not forced, only the containers whose compose configuration changed are recreated
  [[ "$force" == true ]] && args+=(--force-recreate)
  if ! run_stack_compose "$stack" "${args[@]}"; then
    echo "Could not deploy the $stack stack. The stacks before it are still running."
    exit 1
  fi
done

echo
echo "Comodo is deployed. The UI is available at http://localhost:8501 on this machine."
