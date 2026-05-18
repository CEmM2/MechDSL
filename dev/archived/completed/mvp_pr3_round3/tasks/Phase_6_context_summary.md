# Phase 6 Context Summary: Golden File Regeneration and Verification

## Must Know

### Purpose
Phase 6 is the final gate. All codegen changes (Phase 1, Phase 2 H4, Phase 5 G3) invalidate the golden files. This phase regenerates them and runs the full verification suite.

### Verification sequence (must run in order)
1. `uv run python packages/mechdsl-core/tests/generate_golden.py` — regenerate golden files
2. Inspect golden file diffs — verify only expected changes from codegen fixes
3. `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" --tb=short -q` — full fast suite
4. `uv run ruff check packages/` — linter
5. `uv run mypy packages/mechdsl-core/src/mechdsl/` — type checker
6. (Optional) `uv run pytest packages/mechdsl-core/tests/ -m "slow" --tb=short -q` — slow tests if Taichi available

### Key principles
- **Golden file diffs must be explainable**: Every change in the regenerated golden files should trace to a specific Phase 1 or Phase 2 change. Unexpected diffs indicate a bug.
- **Expected golden file changes**: New `raise RuntimeError` instead of `return max_iter`, NaN guard, CG failure counter, `range(N_NODES)` instead of `ti.static(range(N_NODES))`, `ti.static(range(N_QP))` instead of `range(N_QP)`, function rename `emit_constitutive_update`, dl clamp, convergence check.

### Blockers
This phase is blocked by 12 upstream tasks — all of Phase 1, R3.2.3 (CG counter), R3.2.5 (ref elastic), and R3.5.4 (tolerances/Dirichlet fix).

## Should Know

### If tests fail
- Check which tests fail. If golden snapshot tests fail, the golden files need regeneration (step 1).
- If validation tests fail (e.g., new `__post_init__` rejects a previously valid construction), the validator is too strict.
- If tolerance tests fail (G1, G4), the underlying numerical accuracy may be worse than expected — investigate before loosening.
- If mypy fails, the Phase 3 type changes may need annotations.
