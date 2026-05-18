#!/bin/bash
# PostToolUse hook: auto-format Python files after Edit/Write
# Receives JSON on stdin with tool_input containing the file path

set -e

# Read the JSON input
INPUT=$(cat)

# Extract the file path from the tool input
FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
# Edit tool uses 'file_path', Write tool uses 'file_path'
print(ti.get('file_path', ''))
" 2>/dev/null)

# Only act on Python files
if [[ "$FILE" == *.py ]]; then
    # Prefer uv run (project env), fall back to uvx (global tool)
    if command -v uv &>/dev/null; then
        uv run ruff check --fix --quiet "$FILE" 2>/dev/null || true
        uv run ruff format --quiet "$FILE" 2>/dev/null || true
    fi
fi
