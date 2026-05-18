# Phase 6 Tasks Analysis

**Phase:** 6 — Continuum damage (Lemaitre CDM)
**Plan:** `dev/design_docs/PLAN-B.md` §B6 (lines 189-202)
**Branch:** `plan-b_phase-6` (branched from `plan-b_phase-5` tip, Phase 5 not yet merged to main)
**Scaffold commit:** `d970644`

## Task scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked By | Blocks |
|---------|-------|------------------|------------|----------|------------|--------|
| P6-1 | Lemaitre damage variable + evolution | 4 | 4 | **8** | P1-1 (done) | P6-2 |
| P6-2 | Plasticity coupling + element deletion | 4 | 4 | **8** | P6-1 | P6-3 |
| P6-3 | D=0 regression + notched bar | 3 | 3 | **6** | P6-2 | P10-8 |

## Model assignment (from ExecPhase Step 2 rules)

- **P6-1 combined=8 > 6** → Opus 4.6 implementer and reviewers
- **P6-2 combined=8 > 6** → Opus 4.6 implementer and reviewers
- **P6-3 combined=6** → Sonnet 4.6 or Opus 4.6 (complexity ≥ 3 threshold)

## Execution order

Strictly sequential. P6-1 → P6-2 → P6-3. No parallel batch possible (P6-2 and P6-3 both block on direct predecessors with shared symbol-table surface).

## Risk factors inherited from past gate history

1. **physics_error (Phase 2 precedent):** `compute_convected_metric` had wrong formulation for Cartesian F; tests used only isotropic state which masked it. **Phase 6 hazard:** Lemaitre's energy release rate `Y = σ_eq² R_v / (2 E (1-D)²)` depends on triaxiality R_v. Tests that drive D growth must use **non-isotropic stress states** (e.g., uniaxial tension with R_v ≠ 1/3) or the R_v factor won't be exercised.
2. **integration_break (Phase 5 precedent, ×3):** Shared-file changes broke tests that pinned old state. **Phase 6 hazard checklist:**
   - `test_material_lemaitre_damage_raises_unsupported_error` (frontend_build_context) — will flip from expected-raise to expected-accept
   - Any `test_history_fields.py` tests that enumerate strict state-field sets will break when P6-2 adds `(alpha, D)`
   - Golden snapshots (`test_codegen.py::TestGoldenSnapshot`) will drift when Lemaitre branch is added to taichi_printer
3. **Error message convention:** New UnsupportedError paths (if any — e.g., "rate-dependent damage not supported") must use "Plan B phase BX" wording enforced by test_documentation.

## Phase 6 exit criterion (Plan B line 202)

Notched bar matches qualitative expectations; D=0 matches J2. Both assertions live in `test_lemaitre_acceptance.py` (P6-3).
