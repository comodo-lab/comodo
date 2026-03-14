#!/bin/sh
set -e

# Promote any FOO_FILE env var to FOO if the file exists
for key in $(env | grep '_FILE=' | cut -d'=' -f1); do
  base="${key%_FILE}"
  file_path="$(eval echo \"\$$key\")"
  if [ ! -f "$file_path" ]; then
    echo "[entrypoint] $key is set but file not found: $file_path (skipping)"
  elif [ ! -s "$file_path" ]; then
    echo "[entrypoint] $key points to an empty file: $file_path (skipping)"
  else
    value="$(cat "$file_path")"
    eval "export $base=\$value"
    promoted="$promoted $base"
    echo "[entrypoint] $base loaded from $file_path"
  fi
done

if [ -n "$promoted" ]; then
  echo "[entrypoint] Final env check:"
  for var in $promoted; do
    echo "[entrypoint]   $var=$(eval echo \"\$$var\")"
  done
fi

echo "[entrypoint] Handing off to: $*"
exec "$@"
