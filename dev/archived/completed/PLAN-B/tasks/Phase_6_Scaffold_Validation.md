# Phase 6 Scaffold Validation

**Phase:** B6 Continuum damage (Lemaitre CDM)
**Plan:** `dev/design_docs/PLAN-B.md` lines 189–202
**Tasks:** P6-1 (damage variable + evolution), P6-2 (plasticity coupling + element deletion), P6-3 (D=0 regression + notched bar)

## Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P6-1 | Lemaitre damage variable + evolution equation | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled (Step 4 after stub gen) |
| P6-2 | Plasticity coupling + element deletion at D > D_crit | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled (Step 4 after stub gen) |
| P6-3 | D=0 regression + notched bar verification | `verification_commands=[""]`, `test_artifacts=[""]` | auto-filled (Step 4 after stub gen) |

All three JSONs have well-populated `objective`, `acceptance_criteria` (3+ entries each), `implementation_steps` (4 entries each), `deliverables`, `risks`, `test_plan.tier`, and `test_plan.cases`. No `needs-human-review` entries. Only `verification_commands` and `test_artifacts` are placeholder — these are auto-fill targets after Step 3 stub generation.

## Pre-resolved context (from Phase_6_context_summary.md)

- D ∈ [0, 1), D_crit = 0.95 (default), clamp `D < 1 − 1e-6`.
- State per QP: `(alpha, D)`. Effective stress `σ_eff = σ / (1 − D)`.
- Lemaitre couples to J2 power-law **only** (not Perzyna/Johnson-Cook).
- `is_deleted` is per-element `ti.i32` field (0/1); deletion is one-way.
- D=0 regression is the primary correctness guard — byte-identical to J2 power-law.
- Mesh-dependence at localisation sites is expected, not a bug.

## Existing test inventory (pre-scaffold)

Single lexical hit for "lemaitre": `test_material_lemaitre_damage_raises_unsupported_error` in `test_frontend_build_context.py` — still-unsupported sentinel guard that P6-1/P6-2 will flip.

No `test_lemaitre_*` files exist. All three stubs will be new.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 9 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 9 |
| New stub files created | 3 |
| Total new stubs generated | 9 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` (for all 3 tasks) |

## Existing Test Coverage Found

None. Only hit for "lemaitre" is `test_frontend_build_context.py::test_material_lemaitre_damage_raises_unsupported_error`, which is a still-unsupported-error guard that P6-1/P6-2 will flip to accepted — not coverage of the implementation.

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| (none) | | | | |

## Tasks Needing Human Review Before Execute

None.

## Ready for Execute

Fully scaffolded:
- **P6-1**: Lemaitre damage variable + evolution equation (4 unit stubs in `test_lemaitre_evolution.py`)
- **P6-2**: Plasticity coupling + element deletion at D > D_crit (3 integration stubs in `test_lemaitre_codegen.py`)
- **P6-3**: D=0 regression + notched bar verification (2 integration stubs in `test_lemaitre_acceptance.py`)

Dependency order for execution:
1. P6-1 — no open blockers (P1-1 is done)
2. P6-2 — blocked by P6-1
3. P6-3 — blocked by P6-2 (Phase 6 exit criterion)

Phase 6 exit criterion (from plan line 202): Notched bar matches qualitative expectations; D=0 matches J2.

