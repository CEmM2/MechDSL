---
name: local-ci
description: Run the full CI pipeline locally — lint, format check, type check, and tests. Mirrors the GitHub Actions workflow.
disable-model-invocation: true
---

# Local CI

Run the same checks as `.github/workflows/ci.yml` locally before pushing.

## Process

Run all steps sequentially. Stop and report on first failure.

### 1. Lint
```bash
uv run ruff check packages/
```

### 2. Format check
```bash
uv run ruff format --check packages/
```

### 3. Type check (mechdsl-core)
```bash
uv run mypy packages/mechdsl-core/src/mechdsl/
```

### 4. Type check (algo2code)
```bash
uv run mypy packages/algo2code/src/algo2code/
```

### 5. Tests
```bash
uv run pytest -m "not slow and not gpu" --tb=short -q
```

## Output

Report each step as ✅ or ❌ with the failing output. Summary at the end:

```
Lint:       ✅
Format:     ✅
Mypy core:  ✅
Mypy algo:  ✅
Tests:      ✅ (42 passed)
```
