#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Codex cloud environment — maintenance script
# Runs when a cached container is resumed on a newer commit.
# Re-syncs deps in case pyproject.toml or uv.lock changed.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

uv sync --all-packages --all-groups --all-extras

echo "✓ Codex maintenance complete"
