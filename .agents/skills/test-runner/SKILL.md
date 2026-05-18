---
name: test-runner
description: Select and run the smallest useful MechDSL test subset based on what changed, then summarize failures and likely causes. Use after code changes or when triaging regressions.
---

# Test Runner

This skill is read-only apart from running commands.

## Workflow

1. Detect changed files with `git diff --name-only HEAD` unless `$ARGUMENTS` supplies a base ref or mode.
2. Classify scope:
   - docs only: no tests
   - `packages/algo2code/`: run the algo2code test suite
   - `packages/mechdsl-core/src/`: map changed modules to their tests
   - changed test files: run those tests directly
   - `pyproject.toml` or `conftest.py`: run the fast suite
3. Build the minimal pytest command.
   Add slow coverage for codegen or solver changes.
   Add `test_e2e.py` for IR or lowering changes.
   Do not run GPU tests unless explicitly requested.
4. Run the selected tests with `uv run pytest`.
5. For failures, read the failing tests and corresponding source, then summarize likely causes.

## Output

Report:

- scope and why those tests were chosen
- exact command run
- pass, fail, and skip counts
- failure analysis
- golden-file drift if relevant

