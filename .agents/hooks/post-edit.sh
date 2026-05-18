#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

bash "$SCRIPT_DIR/format-on-edit.sh" "$@"
bash "$SCRIPT_DIR/typecheck-on-edit.sh" "$@"

