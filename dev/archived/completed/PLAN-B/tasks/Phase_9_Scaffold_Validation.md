# Phase 9 Scaffold Validation

**Plan:** `dev/design_docs/PLAN-B.md` §B8b (lines 243-261)
**Phase:** 9 — Contraction template tuning
**Branch:** `plan-b_phase-9` (off `plan-b_phase-8` tip `5465694`)
**Date:** 2026-04-17

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P9-1 | Design named contraction-family templates (per backend × element) | `test_artifacts` placeholder, `verification_commands` placeholder | auto-filled |
| P9-2 | Refactor einsum_optimizer to emit via template families | `test_artifacts` placeholder, `verification_commands` placeholder | auto-filled |
| P9-3 | Budget regression test for all element × backend combos | `test_artifacts` placeholder, `verification_commands` placeholder | auto-filled |

All three task JSONs had populated `objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, and `test_plan.{tier,cases}` from Plan-2-Tasks. Only `verification_commands` and `test_artifacts` needed auto-fill from the generated stubs.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 7 (P9-1 inflated from 1→3, P9-2 = 4, P9-3 = 2) |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 3 (P9-2 Taichi/MFEM/MOOSE emission equivalence partial via existing printer tests) |
| Cases with no existing tests (stubs generated) | 4 |
| New stub files created | 3 |
| Total new stubs generated | 9 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts` on all 3 tasks |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P9-2 | Taichi emission equivalent | `tests/test_taichi_printer.py` | (determinism + material-model tests) | partial — covers determinism, not pre/post-refactor equivalence |
| P9-2 | MFEM emission equivalent | `tests/test_mfem_printer.py` | (acceptance + determinism tests) | partial — no golden-file regression for family-emitter path |
| P9-2 | MOOSE emission equivalent | `tests/test_moose_printer.py` | (acceptance tests) | partial — no family-emitter regression |
| P9-2 | All contractions classified | `tests/test_einsum_optimizer.py` | (tier-assignment tests) | none for `family` field (new enum in P9-2) |

## Tasks Needing Human Review Before Execute

None. All three tasks are fully scaffolded.

## Ready for Execute

Fully scaffolded:
- **P9-1**: Design named contraction-family templates — spec-doc-only, 3 stub tests gate spec completeness
- **P9-2**: Refactor einsum_optimizer to emit via template families — 4 stub tests covering classification + per-backend equivalence
- **P9-3**: Budget regression test for all element × backend combos — 2 stub tests (budget + emission-time) plus empty golden baseline

Needs human review before execution: none.

## Stub Verification

```
uv run pytest packages/mechdsl-core/tests/test_p9_1_family_spec_completeness.py \
               packages/mechdsl-core/tests/test_p9_2_family_emitters.py \
               packages/mechdsl-core/tests/test_template_family_budget.py -v
→ 9 skipped in 0.03s (all stubs skip cleanly with "stub - implement after Task P9-X")
```

## Execution order

P9-1 → P9-2 → P9-3 (strict sequence per `blocked_by` chain; no parallelisable batches in Phase 9).

Model assignment (complexity/risk per Plan-2-Tasks analysis):
- P9-1: 4/3 → Opus (design doc with existing-contraction audit)
- P9-2: 5/4 → Opus (largest refactor in Plan B, touches all three backends)
- P9-3: 3/3 → Sonnet (parametrised regression harness)
