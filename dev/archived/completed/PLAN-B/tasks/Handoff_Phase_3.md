# Handoff: Phase 2 → Phase 3

## Phase 2 Summary

**Phase:** Full convected coordinate framework
**Branch:** `plan-b_phase-2`
**Status:** Complete — all 5 tasks done, exit criterion met
**Final suite:** 1055 passed, 1 skipped, 0 failed

### What was built

The symbolic layer (`mechdsl.symbolic.convected`) now supports full curvilinear reference configurations:

| Component | Function | Location |
|-----------|----------|----------|
| MetricField | Wraps Cartesian/curvilinear metric with symmetry validation | convected.py:20-70 |
| Convected metric | `g_IJ = G_ref^T @ C @ G_ref` | convected.py:120-140 |
| Metric inversion | Symbolic `G^{IJ}` | convected.py:145-165 |
| Covariant/contravariant bases | `g_I = F @ G_I`, `g^I = g^{IJ} g_J` | convected.py:170-210 |
| Christoffel symbols | `Gamma^K_{IJ}` with fast-path for Cartesian | convected.py:217-259 |
| Covariant derivatives | Contravariant vector, covariant vector, rank-2 tensor | convected.py:262-345 |
| Metric-assign directives | `% mechanics assign gDD --metric_current` | directives.py |

### Key decisions and fixes

1. **API convention:** All functions take `G_ref_vecs` (base vectors matrix, columns = G_I), NOT the metric tensor `G_IJ`. This was a Gate B fix in P2-1 — the original formula `F^T G F` was wrong when F is the Cartesian deformation gradient.

2. **Index convention:** `gamma[K, I, J] = Gamma^K_{IJ}`. Covariant derivative functions use this consistently.

3. **Patch test scope:** P2-5 tests at the constitutive level (SVK stress through convected pathway), not through FEM solve — the element assembly doesn't support curvilinear meshes yet. Full pipeline curvilinear verification is downstream (P10-1).

### What Phase 3 needs to know

Phase 3 (Viscoplasticity) adds rate-dependent plasticity:
- P3-1: Perzyna viscoplasticity model
- P3-2: Johnson-Cook flow stress + thermal
- P3-3: Consistent viscoplastic tangent
- P3-4: Rate/quasi-static/thermal verification

Phase 3 does NOT depend on Phase 2 — its blockers are all resolved. The convected infrastructure built here will be consumed later by P10-1 (MMS convergence study matrix).

### Test baseline

- 1055 passed, 1 skipped (e2e metric propagation stub)
- No pre-existing failures
- All Phase 1 + Phase 2 tests green
