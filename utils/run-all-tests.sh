# A bash script to test all the components of Comodo

#!/bin/bash
set -uo pipefail

run_integration=true
for arg in "$@"; do
    case "$arg" in
    --no_integration|--noint)
        run_integration=false
        ;;
    *)
        echo "Unknown argument: $arg"
        exit 1
        ;;
    esac
done

cd $(dirname "$0")
project_root=$(cd .. && pwd)
cd $project_root

# Run tests for each component
echo "Running tests for Comodo"

# List of components to test
components=("controller" "firmware" "setpoint_controller" "ui" "utils" "monitor")
separator="================================================================================================"

# Loop through each component and run its tests
declare -A outputs
declare -A exit_codes

run_component() {
    local name="$1"
    shift

    echo
    echo "$separator"
    echo "Testing $name..."
    echo "$separator"

    set +e
    output=$(
        "$@" 2>&1 | tee /dev/stderr
    )
    status=$?
    set -e

    outputs["$name"]="$output"
    exit_codes["$name"]=$status
}

for component in "${components[@]}"; do
    run_component \
        "$component" \
        bash -c "cd '$component' && docker compose up --build"
done

if [[ "$run_integration" == true ]]; then
    run_component \
        integration \
        ./integration_tests/run-integration-tests.sh
else
    echo "Skipping integration tests."
fi

# Print summary of test results
echo
echo "$separator"
printf "%-24s | %-36s | %-10s\n" "Component" "Result" "Coverage"
echo "$separator"

# Overall outcome, for the final conclusion
all_passed=true
any_warnings=false

for name in "${components[@]}" $( [[ "$run_integration" == true ]] && echo integration ); do
    output="${outputs[$name]}"
    exit_code="${exit_codes[$name]}"

    # Get pytest output or error exit code
    summary=$(printf '%s\n' "$output" |
        grep -E "={3,} .* in [0-9.]+s ={3,}" |
        tail -1 || true)
    if [[ -n "$summary" ]]; then
        result=$(printf '%s\n' "$summary" |
            sed -E 's/^.*={3,} (.* in [0-9.]+s) ={3,}.*$/\1/')
    else
        result="ERROR (exit code $exit_code)"
    fi

    # Chech for failures or warnings (no pytest summary -> error)
    if [[ -z "$summary" || "$result" =~ failed|error ]]; then
        all_passed=false
    fi
    if [[ "$result" =~ warning ]]; then
        any_warnings=true
    fi

    # Get coverage percentage from pytest-cov output
    cov_sum=$(printf '%s\n' "$output" |
        grep -E "\| TOTAL.*[0-9]+%$" |
        tail -1 || true)
    if [[ -z "$cov_sum" ]]; then
        coverage="---"
    else
        coverage=$(printf '%s\n' "$cov_sum" | awk '{print $NF}')
    fi

    # Print the result for this component
    printf "%-24s | %-36s | %-10s\n" \
        "$name" \
        "$result" \
        "$coverage"
done
echo "$separator"

# Print a conclusion that is hard to miss, coloured when printing to a terminal
if [[ -t 1 ]]; then
    red=$'\e[1;31m' yellow=$'\e[1;33m' green=$'\e[1;32m' reset=$'\e[0m'
else
    red="" yellow="" green="" reset=""
fi
if [[ "$all_passed" == true ]]; then
    echo "${green}     ---------------------------------  ALL TESTS PASSED  ---------------------------------${reset}"
else
    echo "${red}     ---------------------------  TESTS FAILED / ERRORS FOUND  ----------------------------${reset}"
fi
if [[ "$any_warnings" == true ]]; then
    echo "${yellow}     ---------------------------------  WARNINGS RAISED  ----------------------------------${reset}"
fi
echo "$separator"

# Exit with an error if anything did not pass
[[ "$all_passed" == true ]]