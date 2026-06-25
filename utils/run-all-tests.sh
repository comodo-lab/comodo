# A bash script to test all the components of Comodo

#!/bin/bash
set -e

cd $(dirname "$0")
project_root=$(cd .. && pwd)
cd $project_root

# Run tests for each component
echo "Running tests for Comodo"

# List of components to test
components=("controller" "firmware" "setpoint_controller" "ui" "utils" "monitor")

# Loop through each component and run its tests
for component in "${components[@]}"; do
    echo "Testing $component..."
    (cd "$component" && docker compose up --build)
done
