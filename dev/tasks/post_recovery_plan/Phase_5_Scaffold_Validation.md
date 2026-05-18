# Phase 5 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P5-1 | Author dev/algorithms/radial_return_j2.tex | `verification_commands=[""]`, `test_artifacts=[""]` (risks present) + `test_plan.cases` short | auto-filled |
| P5-2 | New algo2code radial-return codegen test | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled |
| P5-3 | Switch lib/plasticity.py default + feature flag | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled (extra risk noted re: missing `lib/plasticity.py`) |
| P5-4 | Imported vs algo2code parity test | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled |
| P5-5 | Design-doc note on substitution + fallback | `verification_commands=[""]`, `test_artifacts=[""]`, `risks=[]` | auto-filled |

`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `test_plan.tier` populated by Plan-2-Tasks for all five tasks. No human-review flags raised.

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (all) | radial-return / algo2code path / parity | — | — | none — Phase 5 is purely additive |

Audit findings (`grep -rln "radial_return\|MECHDSL_USE_IMPORTED_RR"` in `packages/`):
- Imported `radial_return` lives in `mechdsl.symbolic.models.j2_power_law`; consumed by `mechdsl.verify.benchmarks._j2_solver`.
- `packages/mechdsl-core/src/mechdsl/lib/plasticity.py` does **not** exist yet (only `__init__.py` + `tensor_ops.py` under `lib/`); P5-3 creates it.
- `dev/algorithms/` directory does **not** exist; P5-1 creates it.
- `algo2code` Taichi backend is at `packages/algo2code/src/algo2code/backends/`; library examples at `packages/algo2code/src/algo2code/library/pcg.py` (PCG only — radial-return not yet present).

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 18 (P5-1: 3, P5-2: 5, P5-3: 3, P5-4: 5, P5-5: 3 — meta-spec stubs include file-existence checks where the deliverable is itself a test file or doc/algorithm source) |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 18 |
| New stub files created | 5 |
| Total new stubs generated | 18 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts`, plus extra risks on P5-3 (missing `lib/plasticity.py`) and P5-5 (doc-target choice). |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| — | — | — | none |

## Notes on complexity

Phase 5 is the highest-complexity phase scaffolded so far in `post_recovery_plan.md`:

- P5-1 (algpseudocode authoring) — complexity 3, risk 3.
- P5-2 (codegen test exercising algo2code Taichi backend) — complexity 4, risk 4.
- P5-3 (lib/plasticity.py creation + feature flag dispatch) — complexity 3, risk 3.
- P5-4 (parity test against imported reference) — complexity 4, risk 4.
- P5-5 (design-doc note) — complexity 1, risk 1.

Per the `Aut_Faciam` model assignment rule, P5-2 and P5-4 (combined score 8) **must** dispatch Opus 4.6 subagents at exec time; P5-1 and P5-3 (score 6) qualify for Opus or Sonnet. Final scoring lives in `Phase_5_Tasks_analysis.md` (written at exec time).

## Notes

- Phase 5 stubs that exercise plasticity / algo2code carry `@pytest.mark.unit` or `@pytest.mark.integration` per task-JSON tier. Only P5-5's three stubs carry `@pytest.mark.docs` (design-doc presence checks).
- The plan permits in-scope minor extension of `algo2code` if a needed construct is missing (e.g. exponentiation for power-law hardening); P5-2 / P5-4 may need to surface this during exec.

## Ready for Execute

Fully scaffolded:
- P5-1: Author dev/algorithms/radial_return_j2.tex algpseudocode source
- P5-2: New algo2code radial-return codegen test
- P5-3: Switch lib/plasticity.py default + feature flag
- P5-4: Imported vs algo2code parity test
- P5-5: Design-doc note on substitution + fallback

Needs human review before execution:
- (none)

Execution order (dependency-driven):
1. P5-1 (no blockers).
2. P5-2 (blocked by P5-1).
3. P5-3 (blocked by P5-2).
4. P5-4 + P5-5 in parallel (both blocked by P5-3 only).
