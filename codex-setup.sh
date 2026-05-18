#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Codex cloud environment — setup script
# Runs once when the container is created (internet access ON).
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ── 1. Pin Python 3.12 ──────────────────────────────────────
# codex-universal ships multiple Python versions; make sure 3.12 is default.
# If the image already defaults to 3.12, this is a no-op.
if ! python3 --version 2>/dev/null | grep -q "3\.12"; then
    echo "⚠  Python 3.12 not default — attempting to set it"
    if command -v update-alternatives &>/dev/null; then
        PY312=$(command -v python3.12 || true)
        [ -n "$PY312" ] && update-alternatives --set python3 "$PY312"
    fi
fi
python3 --version

# ── 2. Install uv ───────────────────────────────────────────
# uv is the sole package manager for this project (never bare pip/pytest/ruff).
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in the agent phase
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv $(uv --version)"

# ── 3. Install all workspace packages + dev + extras ────────
# --all-packages  → both mechdsl-core and algo2code
# --all-groups    → dev tools (pytest, ruff, mypy, pre-commit)
# --all-extras    → optional deps like torch (verify group)
uv sync --all-packages --all-groups --all-extras

# ── 4. Verify critical imports ──────────────────────────────
uv run python -c "import mechdsl; import algo2code; print('packages OK')"

# ── 5. Pre-commit hooks (optional in CI, but useful for the agent) ──
uv run pre-commit install --install-hooks || true

echo "✓ Codex setup complete"
