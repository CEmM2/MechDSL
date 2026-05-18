#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <file> [<file> ...]" >&2
    exit 64
fi

for file in "$@"; do
    case "$file" in
        *.py)
            case "$file" in
                *mechdsl*|*algo2code*)
                    uv run mypy --follow-imports=skip "$file" >/dev/null 2>&1 || true
                    ;;
            esac
            ;;
    esac
done

