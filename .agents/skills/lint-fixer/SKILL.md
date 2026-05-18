---
name: lint-fixer
description: Run Ruff and mypy for MechDSL, auto-fix safe issues, make manual fixes when needed, and verify the tree is clean. Use before committing or when lint or typing checks fail.
---

# Lint Fixer

If `$ARGUMENTS` names files, scope the run to those files when practical. Otherwise work on all packages.

## Workflow

1. Run `uv run ruff check --fix packages/`.
2. Run `uv run ruff format packages/`.
3. Re-run `uv run ruff check packages/`.
4. Make manual fixes for remaining Ruff issues.
5. Run:
   - `uv run mypy packages/mechdsl-core/src/mechdsl/`
   - `uv run mypy packages/algo2code/src/algo2code/`
6. Fix straightforward typing issues directly and re-run the checks.
7. Finish with:
   - `uv run ruff check packages/`
   - `uv run ruff format --check packages/`
   - both mypy commands above

## Constraints

- Prefer real fixes over suppression.
- If suppression is unavoidable, use the narrowest possible code-specific ignore.
- Do not touch excluded or unrelated generated content unless it is part of the requested scope.

## Output

Report Ruff and mypy status separately, list remaining manual issues, and state whether CI should pass.

