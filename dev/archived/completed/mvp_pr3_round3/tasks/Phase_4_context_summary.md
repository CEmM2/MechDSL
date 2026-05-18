# Phase 4 Context Summary: CI Flags Fix

## Must Know

### File modified
- `.github/workflows/ci.yml` — 3 `uv sync` lines

### Conventions
- **CLAUDE.md install command**: `uv sync --all-packages --all-groups --all-extras`. CI must match this exactly.
- All three CI jobs (lint, test, budget-regression) need the same flags.

### Key principles
- The `--all-groups` flag ensures dev/test dependency groups are installed.
- The `--all-extras` flag ensures optional extras (if any) are installed.
- Without these flags, CI may silently skip tests or fail with import errors for dev-only dependencies.

## Should Know

### Downstream impact
- This is an isolated change with no code dependencies. Can be done at any point.
- Verify CI YAML validity after editing: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
