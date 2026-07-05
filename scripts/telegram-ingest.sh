#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROFILE_DIR/cache/uv}"
if [[ -f "$PROFILE_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROFILE_DIR/.env"
  set +a
fi
exec uv run "$PROFILE_DIR/scripts/telegram_ingest.py" "$@"
