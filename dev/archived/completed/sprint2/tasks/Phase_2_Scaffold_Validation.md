# Phase 2 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-T1 | Implement patch_test_reference() | `risks` — empty | auto-filled |
| P2-T2 | Implement rigid_body_reference() | `risks` — empty | auto-filled |
| P2-T3 | Implement cantilever_euler_bernoulli() | `risks` — empty | auto-filled |
| P2-T4 | Implement uniaxial_tension_hardening() | — (all fields populated) | — |
| P2-T5 | Write analytical solution tests | `risks` — empty | auto-filled |
| P2-T6 | Implement frontend.build_context() | `risks` — empty | auto-filled |
| P2-T7 | Implement build_context validation | `risks` — empty | auto-filled |
| P2-T8 | Write frontend tests | `risks` — empty | auto-filled |

## Auto-fill Details

| Task ID | Field | Auto-filled Value |
|---------|-------|-------------------|
| P2-T1 | risks | "Small/finite strain formulation choice affects displacement computation — must match design docs convention" |
| P2-T2 | risks | "Rotation matrix validation (det=1, orthogonality) tolerance selection for near-singular inputs" |
| P2-T3 | risks | "Trivial formula — minimal risk" |
| P2-T5 | risks | "Test file depends on all four analytical functions — partial implementations may cause import errors" |
| P2-T6 | risks | "Context dict schema must exactly match what LaTeX parser would produce — schema drift risk if parser changes" |
| P2-T7 | risks | "UnsupportedError import and plan-phase pointer text must match ir.md conventions exactly" |
| P2-T8 | risks | "Tests cover parser test IDs P1/P2/P5/P6 — must verify mapping against 08-VERIFICATION.md" |

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 8 |
| Test cases assessed | 21 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 4 (patch_test, rigid_body, cantilever, uniaxial via ref tests) |
| Cases with no existing tests (stubs generated) | 17 |
| New stub files created | 2 |
| Total new stubs generated | 21 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | risks (7 tasks) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P2-T1 | patch_test known strain | `tests/test_ref_elastic.py` | patch test infrastructure | partial — tests FEM solver, not analytical reference |
| P2-T2 | rigid_body identity | `tests/test_benchmarks.py` | `test_single_element_rigid_body` | partial — behavioral test only |
| P2-T3 | cantilever known params | `tests/test_ref_elastic.py`, `tests/test_artifacts.py` | cantilever tests | partial — numerical, not analytical formula |
| P2-T4 | uniaxial above yield | `tests/test_ref_plastic.py` | `test_uniaxial_stress_strain_follows_hardening` | partial — FEM solver test, not analytical reference |

## Tasks Needing Human Review Before execute-phase

(none — all fields populated or auto-filled)

## Ready for execute-phase

Fully scaffolded:
- P2-T1: Implement patch_test_reference()
- P2-T2: Implement rigid_body_reference()
- P2-T3: Implement cantilever_euler_bernoulli()
- P2-T4: Implement uniaxial_tension_hardening()
- P2-T5: Write analytical solution tests
- P2-T6: Implement frontend.build_context()
- P2-T7: Implement build_context validation
- P2-T8: Write frontend tests
