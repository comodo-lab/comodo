# A bash script to test all the components of Comodo

#!/bin/bash
set -euo pipefail

cd $(dirname "$0")
project_root=$(cd .. && pwd)
cd $project_root

# Run tests for each component
echo "Running tests for Comodo"

# List of components to test
components=("controller" "firmware" "setpoint_controller" "ui" "utils" "monitor")

all_output=""

# Loop through each component and run its tests
for component in "${components[@]}"; do
    echo "Testing $component..."
    component_output=$(cd "$component" && docker compose up --build 2>&1 | tee /dev/stderr)
    all_output+=$'\n'"$component_output"
done

# Run integration tests
echo "Running integration tests..."
integration_output=$(
    cd integration_tests && docker compose --env-file ../.env kill &&
    docker compose --env-file ../.env up --build --attach test-runner --force-recreate 2>&1 | tee /dev/stderr &&
    docker compose --env-file ../.env kill)
all_output+=$'\n'"$integration_output"

# Print summary of test results
summary_lines=$(printf '%s\n' "$all_output" | grep -E "test[^|]*[[:space:]]+\|[[:space:]]+={3,} .* in [0-9.]+s ={3,}" || true)
separator="================================================================="
if [[ -n "$summary_lines" ]]; then
    printf '%s\n' "$separator"
    printf '%s\n' "$separator"
    printf '%s\n' "$summary_lines" | awk -F'|' '
        {
            service = $1
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", service)
            result = $2
            sub(/^[[:space:]]*=+[[:space:]]*/, "", result)
            sub(/[[:space:]]*=+[[:space:]]*$/, "", result)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", result)
            printf "%-24s |  %s\n", service, result
        }
    '
    printf '%s\n' "$separator"
    printf '%s\n' "$separator"
fi
