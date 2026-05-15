# A bash script to test all the components of Comodo
# Run with `./all-tests.sh`

#!/bin/bash
set -e

# Run tests for each component
echo "Running tests for Comodo"

# List of components to test
components=("controller" "firmware" "setpoint_controller" "ui")

# Loop through each component and run its tests
for component in "${components[@]}"; do
    echo "Testing $component..."
    (cd "$component" && docker compose up --build --abort-on-container-exit)
done
