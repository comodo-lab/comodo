# Helpers to find the address of this machine, sourced by contexts.sh and run-integration-tests.sh

# Prints the IP address this machine uses to reach the given host (an IP address or a name),
# or nothing if the host can't be resolved or reached.
local_ip_for() {
  local target
  target=$(getent ahostsv4 "$1" 2>/dev/null | awk '{print $1; exit}')
  [ -z "$target" ] && target="$1"
  ip route get "$target" 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}'
}

# Prints a note explaining that the remote stacks were given this machine's IP address to reach the broker.
# Arguments: lines of "<stack>: <ip> (from <host>)".
local_ip_note() {
  echo ""
  echo -e "\033[33mNOTE:\033[0m MQTT_HOST is blank, so the broker runs on this machine, where the local stacks reach it by name."
  echo "  The remote stacks can't, so they are given the IP address this machine uses to reach them:"
  for line in "$@"; do
    echo "    $line"
  done
  echo "  If this machine's IP address changes, the remote stacks will lose the broker until they are redeployed."
  echo "  To avoid this, set MQTT_HOST to a fixed address or hostname of this machine."
}
