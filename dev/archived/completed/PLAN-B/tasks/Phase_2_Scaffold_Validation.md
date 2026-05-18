# Phase 2 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-1 | Covariant/contravariant bases + metric tensors | verification_commands, test_artifacts | auto-filled |
| P2-2 | Christoffel symbols from metric | verification_commands, test_artifacts | auto-filled |
| P2-3 | Covariant derivatives (vectors and tensors) | verification_commands, test_artifacts | auto-filled |
| P2-4 | NRPyLaTeX metric-assignment directives | verification_commands, test_artifacts | auto-filled |
| P2-5 | Curvilinear patch test + Cartesian equivalence | verification_commands, test_artifacts | auto-filled |

All core fields (objective, acceptance_criteria, implementation_steps, deliverables, risks, test_plan) were already populated. Only `verification_commands` and `test_artifacts` needed auto-filling (expected pre-scaffold).

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 19 |
| Cases covered by existing tests | 1 (partial) |
| Cases partially covered (stubs generated) | 1 |
| Cases with no existing tests (stubs generated) | 18 |
| New stub files created | 3 |
| Total new stubs generated | 19 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | verification_commands (5 tasks), test_artifacts (5 tasks), test_plan.cases expanded (P2-1 +1, P2-2 +1, P2-4 +1) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P2-1 | Cartesian reference unchanged | tests/test_convected.py | TestComputeReferenceMetric::test_cartesian_returns_identity | partial |
| P2-1 | Cartesian reference unchanged | tests/test_convected.py | TestComputeConvectedMetric::test_identity_F_returns_identity | partial |
| P2-1 | Cartesian reference unchanged | tests/test_convected.py | TestConvectedKinematicsConsistency::test_convected_metric_matches_kinematics_g | partial |

**Note:** `test_convected.py::TestComputeReferenceMetric::test_non_cartesian_raises_unsupported` currently asserts that curvilinear raises `UnsupportedError`. After P2-1 implementation, this test must be **inverted** (curvilinear should be accepted, not rejected). This mirrors the P1-6 pattern where formulation-rejection tests were inverted.

## Tasks Needing Human Review Before Execute

None — all task JSONs are fully populated.

## Ready for Execute

Fully scaffolded:
- P2-1: Covariant/contravariant bases + metric tensors (curvilinear reference)
- P2-2: Christoffel symbols from metric
- P2-3: Covariant derivatives (vectors and tensors)
- P2-4: NRPyLaTeX metric-assignment directives
- P2-5: Curvilinear patch test + Cartesian equivalence

## Stub Files

| File | Tasks | Stubs |
|------|-------|-------|
| `tests/test_convected_curvilinear.py` | P2-1, P2-2, P2-3 | 12 |
| `tests/test_metric_assign_directives.py` | P2-4 | 5 |
| `tests/test_convected_patch.py` | P2-5 | 2 |

## Regression Guards

The following existing tests serve as regression guards during Phase 2 execution:
- `test_convected.py` — Cartesian-reference convected operations must remain unchanged
- `test_kinematics.py::TestConvectedMetric` — g == C invariant on Cartesian
- `test_formulation_switching.py` — TL/UL formulation switching (no Phase 2 impact)
