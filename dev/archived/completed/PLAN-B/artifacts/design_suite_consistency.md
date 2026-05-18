# MechDSL MVP -- Compiler Pass Test Coverage

Generated: 2026-04-01

## Coverage Matrix

| Pass ID | Pass Name | Test File(s) | Status | Notes |
|---|---|---|---|---|
| P | Frontend Parse | test_frontend.py (stub) | BLOCKED | Phase 2 depends on NRPyLaTeX fork; test file is a placeholder |
| S | Symbolic Engine | test_kinematics.py, test_svk.py, test_j2.py, test_voigt.py | PASS | 70 tests |
| M | Mechanics IR | test_mechanics_ir.py | PASS | 19 tests -- construction, validation, serialisation round-trip |
| E | Element IR | test_element_ir.py, test_hex8_tables.py | PASS | 35 tests -- basis functions, quadrature, patch test, gradients |
| N | Einsum / Contraction | test_einsum_optimizer.py, test_einsum.py | PASS | 54 tests -- tier classification, budget enforcement, pipeline integration |
| T | Taichi Codegen | test_taichi_printer.py, test_emission_verification.py, test_plastic_emission.py | PASS | 175 tests -- constitutive emission, internal force, tangent matvec, Newton driver, J2 branches |
| B | Boundary | test_boundary_codegen.py | PASS | 22 tests -- Dirichlet masking, Neumann traction, merge logic |
| A | Assembly | test_ref_elastic.py, test_ref_plastic.py | PASS | 39 tests -- element force, tangent matvec, global assembly, Newton convergence |
| C | Convergence | test_solver.py, test_load_stepping.py | PASS | 21 tests -- CG/PCG protocol, load stepping, cutback logic |

### Cross-cutting tests

| Pass ID | Pass Name | Test File(s) | Status | Notes |
|---|---|---|---|---|
| V | Verification | test_ad_oracle.py | PASS | 16 tests -- FD stress/tangent oracle, SVK + J2 elastic branch |
| G | Golden | test_artifacts.py, test_artifact_bundle.py | PASS | 35 tests -- golden file comparison, drift detection, serialisation round-trip |

### Supporting / infrastructure tests

| Category | Test File(s) | Tests | Notes |
|---|---|---|---|
| Lowering (L4) | test_localise.py | 28 | FE localisation: ProblemIR -> ElementIR + einsum specs |
| Tensor Library | test_tensor_ops.py | 26 | Tier 1 tensor operations (det, inv, deformation gradient, PK transforms) |
| History Fields | test_history_fields.py | 24 | State variable commit/rollback for J2 plasticity |
| Mesh I/O | test_mesh_io.py | 28 | Structured Hex8 mesh generation, boundary tags, coordinate domain |
| End-to-end | test_e2e.py | 12 | Full pipeline: ProblemIR -> ArtifactBundle round-trip, content hash stability |
| Smoke | test_smoke.py | 10 | Package imports, version string |

### Stub files (no tests)

| File | Intended Scope | Status |
|---|---|---|
| test_frontend.py | Layer 1 -- LaTeX parsing | BLOCKED -- parser not implemented |
| test_symbolic.py | Layer 2 -- symbolic engine umbrella | Stub only -- tests live in test_kinematics/svk/j2/voigt |
| test_codegen.py | Layer 5 -- Taichi codegen umbrella | Stub only -- tests live in test_taichi_printer/emission_verification/plastic_emission |
| test_boundaries.py | BC mapping and enforcement | Stub only -- tests live in test_boundary_codegen |

## Gap Analysis

### Critical gaps

1. **Frontend parsing (Pass P)** -- Zero test coverage. The `test_frontend.py` file is a
   single-line docstring stub. This is blocked on the NRPyLaTeX fork (Phase 2). Until the
   parser is implemented, the pipeline requires manually constructed `ProblemIR` objects.

### Moderate gaps

2. **End-to-end from LaTeX** -- `test_e2e.py` (12 tests) covers artifact round-trip and hash
   stability, but does not test the full LaTeX -> Taichi path because the parser is missing.
   The e2e tests start from `ProblemIR`, not from LaTeX source.

3. **Boundary codegen integration** -- `test_boundary_codegen.py` tests the BC infrastructure
   in isolation. Integration testing of BC application within a full Newton solve is covered
   by `test_ref_elastic.py` (TestDirichletBC, TestCantileverBeam) but there is no dedicated
   test for Neumann BC in the reference solver context.

### Minor gaps

4. **Stub file consolidation** -- `test_symbolic.py`, `test_codegen.py`, and
   `test_boundaries.py` are empty placeholders whose actual tests live in more specific
   files. These stubs should either be populated with umbrella imports or removed to avoid
   confusion.

5. **Load stepping + Newton integration** -- `test_load_stepping.py` tests the adaptive
   stepping logic in isolation and `test_solver.py` tests the linear solver. The interaction
   between load stepping and Newton convergence is only covered indirectly through the
   reference solvers.

## Test Count Summary

| Pass / Category | Test Count |
|---|---|
| P -- Frontend Parse | 0 |
| S -- Symbolic Engine | 70 |
| M -- Mechanics IR | 19 |
| E -- Element IR | 35 |
| N -- Einsum / Contraction | 54 |
| T -- Taichi Codegen | 175 |
| B -- Boundary | 22 |
| A -- Assembly | 39 |
| C -- Convergence | 21 |
| V -- Verification | 16 |
| G -- Golden | 35 |
| L -- Lowering | 28 |
| Tensor Library | 26 |
| History Fields | 24 |
| Mesh I/O | 28 |
| End-to-end | 12 |
| Smoke | 10 |
| **Total** | **614** |

All counts are from `uv run pytest packages/mechdsl-core/tests/ --co -q` (2026-04-01).
