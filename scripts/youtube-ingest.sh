#!/bin/bash
set -euo pipefail

PROFILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec uv run "$PROFILE_DIR/scripts/youtube_ingest.py" "$@"
