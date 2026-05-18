#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <file> [<file> ...]" >&2
    exit 64
fi

for file in "$@"; do
    case "$file" in
        *dev/design_docs/*)
            echo "BLOCKED: dev/design_docs/ files are authoritative and should not be modified by Codex. Edit them manually if needed." >&2
            exit 2
            ;;
    esac
done

