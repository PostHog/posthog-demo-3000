#!/usr/bin/env bash
set -euo pipefail

# Resolve project root relative to this script (works in Codespaces and local devcontainers)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Create .env from example if missing
if [ ! -f .env ]; then
  cp .env.example .env
else
  # If existing .env looks invalid (extra keys or duplicates), reset it to example
  PH_COUNT=$(grep -E "^PH_(HOST|PROJECT_KEY|PERSONAL_API_KEY|PROJECT_ID)=" .env | wc -l || true)
  OTHER_COUNT=$(grep -Ev "^PH_(HOST|PROJECT_KEY|PERSONAL_API_KEY|PROJECT_ID)=" .env | sed '/^$/d' | wc -l || true)
  if [ "$PH_COUNT" != "4" ] || [ "$OTHER_COUNT" != "0" ]; then
    cp .env.example .env
  fi
fi

# The Makefile and CI both drive Python through uv, so the container must provide it.
if ! command -v uv >/dev/null 2>&1; then
  python -m pip install -U uv
fi

# uv.lock is the source of truth. uv replaces the stale .venv that the repo still tracks.
uv sync

echo "postCreate complete. Update .env with your PostHog values, then run: make run"

