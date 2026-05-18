#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <file> [<file> ...]" >&2
    exit 64
fi

for file in "$@"; do
    case "$file" in
        *.py)
            uv run ruff check --fix --quiet "$file" >/dev/null 2>&1 || true
            uv run ruff format --quiet "$file" >/dev/null 2>&1 || true
            ;;
    esac
done

