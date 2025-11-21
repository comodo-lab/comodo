#!/bin/sh
set -e

CONFIG_TEMPLATE="/controller/config/config.json.template"
CONFIG_FILE="/controller/config/config.json"

if [ -f "$CONFIG_TEMPLATE" ]; then
  echo "Generating config.json from template using environment variables..."
  envsubst < "$CONFIG_TEMPLATE" > "$CONFIG_FILE"
else
  echo "Template $CONFIG_TEMPLATE not found!"
fi

exec "$@"  # runs CMD
