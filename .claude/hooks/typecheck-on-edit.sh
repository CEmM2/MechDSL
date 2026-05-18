#!/bin/bash
# PostToolUse hook: run mypy on edited Python files
# Receives JSON on stdin with tool_input containing the file path

set -e

INPUT=$(cat)

FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null)

if [[ "$FILE" == *.py ]]; then
    if [[ "$FILE" == *mechdsl* || "$FILE" == *algo2code* ]]; then
        uv run mypy --follow-imports=skip "$FILE" 2>/dev/null || true
    fi
fi
