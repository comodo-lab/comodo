# Functions to deploy the comodo stacks, shared by comodo.sh and integration_tests/run-integration-tests.sh.
# Source it from the repository root, after setting:
#   stacks:   The stacks, in the order they are deployed, e.g. (mqtt data firmware core).
#   commands: The compose command for each stack, from utils/contexts.sh (once loaded).
#   build:    true to build the comodo images from this repository, false to use the published ones.
#               Note: DEVELOPER=true (in the shell, or in 'compose/.env') automatically uses --build.

# Developers always build the images from the local code, as with --build
developer=${DEVELOPER:-$(grep -s -E '^DEVELOPER=' compose/.env | tail -1 | cut -d= -f2- | awk '{print $1}' | tr -d "\"'")}
if [[ "$developer" == true ]]; then
  build=true
fi

# Coloured when printing to a terminal, so each stack's step stands out from the compose output
if [[ -t 1 ]]; then
  yellow=$'\e[33m' bold=$'\e[1m' unbold=$'\e[22m' reset=$'\e[0m'
else
  yellow="" bold="" unbold="" reset=""
fi

# Runs a compose subcommand for the given stack, with the command from contexts.sh (if loaded)
stack_compose() {
  local stack="$1"
  shift
  [[ -z "${commands[$stack]:-}" ]] && return 1
  eval "${commands[$stack]} $(printf '%q ' "$@")"
}

# Prints, and then runs, a compose subcommand for the given stack
run_stack_compose() {
  local stack="$1"
  shift
  echo "  ${commands[$stack]} $*"
  stack_compose "$stack" "$@"
}

# Gets the images of every stack ready (on each stack's host)
# With build=true, it builds them; otherwise, it pulls comodo images and builds the others.
# Checks all the stacks, so all problems are reported on a single run, and returns 1 if there are any.
prepare_images() {
  if [[ "$build" == true ]]; then
    export COMODO_TAG=local
    echo "${yellow}${bold}Building${unbold} comodo images from local code${reset} (tagging as: '$COMODO_TAG')$([[ "$developer" == true ]] && echo " (DEVELOPER=true)")..."
  else
    # As in the compose files, unless set in the shell, or in compose/.env (which the compose commands read)
    local tag
    tag=$(grep -s -E '^COMODO_TAG=' compose/.env | tail -1 | cut -d= -f2-)
    echo "${yellow}${bold}Pulling${unbold} comodo images from Dockerhub${reset} (looking for tag: '${COMODO_TAG:-${tag:-latest}}')..."
  fi

  local problems=() missing_images=false
  local stack service image comodo_services comodo_images other_services missing
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
  # Report any problems, and return 1 if there are any, so the caller can abort.
  if [[ ${#problems[@]} -gt 0 ]]; then
    echo
    printf '%s\n' "${problems[@]}"
    if [[ "$missing_images" == true ]]; then
      echo "Check the hosts can pull the missing images (and that they are published with that tag), or use --build to build them from this repository."
    fi
    return 1
  fi
}
