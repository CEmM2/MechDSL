#!/bin/bash
# PreToolUse hook: block writes to dev/design_docs/ files
# Exit 2 to block the action, stderr message shown to Claude

set -e

INPUT=$(cat)

FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
print(ti.get('file_path', ''))
" 2>/dev/null)

if [[ "$FILE" == *dev/design_docs/* ]]; then
    echo "BLOCKED: dev/design_docs/ files are authoritative and should not be modified by Claude. Edit them manually if needed." >&2
    exit 2
fi

exit 0
