#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROFILE_DIR/cache/uv}"
exec uv run "$PROFILE_DIR/scripts/substack_ingest.py" "$@"
