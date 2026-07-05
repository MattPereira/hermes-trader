#!/usr/bin/env bash
set -uo pipefail

PROFILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0

run_collector() {
  local name="$1"
  local script="$2"
  local status

  echo "[$name] starting"
  if "$PROFILE_DIR/scripts/$script"; then
    echo "[$name] ok"
  else
    status=$?
    echo "[$name] failed (exit $status)" >&2
    failures=$((failures + 1))
  fi
}

run_collector "youtube" "youtube-ingest.sh"
run_collector "substack" "substack-ingest.sh"
run_collector "telegram" "telegram-ingest.sh"

if (( failures > 0 )); then
  echo "Inbox ingestion completed with $failures failed collector(s)" >&2
  exit 1
fi

echo "Inbox ingestion completed successfully"
