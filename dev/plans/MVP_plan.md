# MVP Phased Implementation Plan (Derived from PLAN-A)

> ⚠️ **Superseded for the frontend contract** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 2 / R1).
> Frontend tasks `P2.1`–`P2.5` here should be read as **`implemented-via-substitute`** under the recovery plan's canonical `compile_latex(...)` façade work, not as `not_started`. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) for the canonical status vocabulary and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md) for why the deferral is being recorded as historical drift rather than a defect. The remainder of this plan (kinematics, IRs, codegen, solver, verification) stays the source of truth for MVP runtime work.

This plan decomposes `dev/design_docs/PLAN-A.md` into granular, verifiable tasks.  
Within each phase, tasks are designed to be parallelizable where practical: no two tasks in the same phase should require edits to the same file(s) or break module contracts.

## Phase 0 — Foundation & Interfaces

### P0.1 Workspace dependency lock alignment
- **Scope:** Root workspace metadata only.
- **Files:** `pyproject.toml`, `uv.lock`
- **Work:** Ensure required runtime/dev dependencies from PLAN-A are present and pinned coherently.
- **Verification:** `uv sync --frozen` succeeds in a clean environment.

### P0.2 Core package skeleton completeness
- **Scope:** `mechdsl-core` package structure only.
- **Files:** `packages/mechdsl-core/src/mechdsl/**/__init__.py`
- **Work:** Add missing package dirs/modules from architecture plan (`frontend`, `symbolic`, `ir`, `lowering`, `codegen`, `solver`, `verify`, `lib`).
- **Verification:** `python -c "import mechdsl"` and imports for each subpackage succeed.

### P0.3 CI workflow baseline
- **Scope:** CI config only.
- **Files:** `.github/workflows/ci.yml`
- **Work:** Add jobs for Ruff, mypy (scoped), pytest, and contraction-budget regression stage.
- **Verification:** CI YAML validates and jobs trigger on PR.

### P0.4 Linear solver interface contract
- **Scope:** solver interface only.
- **Files:** `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py`
- **Work:** Define `LinearSolverInterface` protocol/ABC and adapter wrapper for existing PCG/CG backend.
- **Verification:** Unit test solves known SPD toy system to target tolerance.

### P0.5 Tier-1 tensor ops utility
- **Scope:** low-level Taichi math helpers only.
- **Files:** `packages/mechdsl-core/src/mechdsl/lib/tensor_ops.py`
- **Work:** Implement matrix multiply, transpose multiply, PK transforms, det/inv helpers.
- **Verification:** Deterministic unit tests for identity/shear/random invertible matrices.

---

## Phase 1 — Trusted Handwritten References

### P1.1 Handwritten TL Hex8 elastic reference kernel
- **Scope:** elastic reference solver only.
- **Files:** `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py`
- **Work:** Implement full TL Hex8 elastic path with NR loop and imported linear solver.
- **Verification:** patch test + rigid body motion + cantilever checks pass.

### P1.2 Handwritten TL Hex8 J2 plastic reference kernel
- **Scope:** plastic reference solver only.
- **Files:** `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py`
- **Work:** Add radial return mapping, power-law hardening, history variables, consistent tangent.
- **Verification:** below-yield equality to elastic; yield-surface residual near machine precision.

### P1.3 Golden artifact serialization fixture
- **Scope:** golden file harness only.
- **Files:** `packages/mechdsl-core/tests/golden/*`, `packages/mechdsl-core/tests/test_artifacts.py`
- **Work:** Persist baseline displacement/load-displacement outputs from reference solvers.
- **Verification:** golden snapshot tests pass and detect intentional drift.

---

## Phase 2 — Frontend Parsing (`% mechanics`)

### P2.1 NRPyLaTeX dependency fork wiring
- **Scope:** dependency wiring only.
- **Files:** `packages/mechdsl-core/pyproject.toml`
- **Work:** point dependency to maintained mechanics branch/fork.
- **Verification:** parser package imports and upstream parser smoke tests pass.

### P2.2 Mechanics directive tokenization
- **Scope:** scanner extension only.
- **Files:** NRPyLaTeX fork scanner module (document exact path in fork)
- **Work:** add `MECHANICS_KWD` and directive token support.
- **Verification:** lexer unit tests produce expected token stream for `% mechanics ...` lines.

### P2.3 Mechanics directive parsing handlers
- **Scope:** parser directive handlers only.
- **Files:** NRPyLaTeX fork parser module (config dispatch + handler fns)
- **Work:** implement dim/coord/material/formulation/cell/boundary handlers.
- **Verification:** parser context dict equals expected canonical structure for MVP snippet.

### P2.4 Two-manifold index typing
- **Scope:** index/manifold model only.
- **Files:** NRPyLaTeX fork `IndexedSymbol` model + parser validations
- **Work:** add manifold metadata and contraction legality checks.
- **Verification:** positive and negative tests for valid/invalid mixed manifold contractions.

### P2.5 Frontend adapter in mechdsl-core
- **Scope:** integration wrapper only.
- **Files:** `packages/mechdsl-core/src/mechdsl/frontend/parse.py`
- **Work:** expose `parse(latex_str)` that normalizes fork output into project context schema.
- **Verification:** integration test confirms stable dict schema and clear errors for malformed directives.

---

## Phase 3 — Symbolic Mechanics Engine

### P3.1 Kinematics computation module
- **Scope:** symbolic kinematics only.
- **Files:** `packages/mechdsl-core/src/mechdsl/symbolic/kinematics.py`
- **Work:** compute `F, C, J, E, F_inv, F_invT, g` where convected metric `g=C`.
- **Verification:** identity, simple shear, and randomized symbolic sanity tests.

### P3.2 SVK constitutive model
- **Scope:** elastic constitutive model only.
- **Files:** `packages/mechdsl-core/src/mechdsl/symbolic/models/svk.py`
- **Work:** implement PK2 stress and material tangent for isotropic SVK.
- **Verification:** known closed-form tensor values for selected strain states.

### P3.3 J2 power-law symbolic model
- **Scope:** plastic constitutive model only.
- **Files:** `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py`
- **Work:** implement yield function, hardening law, return mapping scaffolding, algorithmic tangent output form.
- **Verification:** unit tests for elastic/plastic branch selection and consistency constraints.

### P3.4 Voigt/Mandel conversion utilities
- **Scope:** notation conversion only.
- **Files:** `packages/mechdsl-core/src/mechdsl/symbolic/voigt.py`
- **Work:** tensor↔Voigt and 4th-order tangent mappings.
- **Verification:** round-trip and isotropic stiffness symmetry tests.

### P3.5 AD oracle verification module
- **Scope:** verification oracle only.
- **Files:** `packages/mechdsl-core/src/mechdsl/verify/ad_oracle.py`
- **Work:** compare symbolic stress/tangent to autodiff-derived reference over random states.
- **Verification:** relative error threshold assertions across sampled deformation states.

---

## Phase 4 — IR and Lowering

### P4.1 Mechanics IR schema + validation
- **Scope:** mechanics-level IR only.
- **Files:** `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py`
- **Work:** implement dataclasses, constraints, subset rejection, serialization.
- **Verification:** schema round-trip + invalid-input rejection tests.

### P4.2 Element IR schema for Hex8 TL
- **Scope:** element-level IR only.
- **Files:** `packages/mechdsl-core/src/mechdsl/ir/element_ir.py`
- **Work:** encode basis, gradients, quadrature, geometry mapping, convected metrics.
- **Verification:** deterministic checks for quadrature cardinality and basis identities.

### P4.3 FE localization pass
- **Scope:** lowering pass only.
- **Files:** `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py`
- **Work:** map `ProblemIR` → `ElementIR`, extract einsum strings, validate compatibility.
- **Verification:** localization test on MVP input with expected einsum signatures.

### P4.4 Artifact bundle model
- **Scope:** artifact packaging only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/artifact.py`
- **Work:** store IR, plans, emitted source; support serialization for golden comparisons.
- **Verification:** artifact write/read preserves semantic content hashes.

---

## Phase 5 — Contraction Planning & Budgets

### P5.1 Einsum optimizer module
- **Scope:** contraction planning only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/einsum_optimizer.py`
- **Work:** implement budget counting + tier classification + guardrails.
- **Verification:** unit suite with expected tier assignments and over-budget failure cases.

### P5.2 Element IR ↔ optimizer integration
- **Scope:** integration seam only.
- **Files:** `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py`, `.../codegen/artifact.py`
- **Work:** attach contraction plans to artifact bundle.
- **Verification:** integration test confirms plans populated for local force and tangent.

### P5.3 CI budget regression fixture
- **Scope:** tests and CI wiring only.
- **Files:** `packages/mechdsl-core/tests/test_einsum.py`, `.github/workflows/ci.yml`
- **Work:** fail CI when MVP contractions exceed budget.
- **Verification:** intentional over-budget fixture causes red test.

---

## Phase 6 — Taichi Code Generation (Elastic Path)

### P6.1 Hex8 static table provider
- **Scope:** reference constants only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/hex8_tables.py`
- **Work:** provide shape function and quadrature constants for codegen/templates.
- **Verification:** partition of unity and exactness tests.

### P6.2 Taichi printer core
- **Scope:** emission infrastructure only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`
- **Work:** build deterministic emitter from `ProblemIR + ElementIR + ContractionPlan`.
- **Verification:** snapshot tests on emitted source skeleton and key function signatures.

### P6.3 Elastic constitutive emission
- **Scope:** constitutive function generation only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/constitutive_elastic.py.j2` (or equivalent)
- **Work:** emit SVK stress/tangent with CSE and runtime guards.
- **Verification:** emitted function numerically matches symbolic oracle on sampled states.

### P6.4 Internal force kernel emission
- **Scope:** force kernel only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/internal_force.py.j2`
- **Work:** emit deformation gradient, constitutive call, and force scatter.
- **Verification:** single-element patch test passes against reference solver output.

### P6.5 Matrix-free tangent matvec emission
- **Scope:** tangent matvec only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/tangent_matvec.py.j2`
- **Work:** emit push-forward + geometric stiffness and BC enforcement.
- **Verification:** matvec result matches finite-difference/assembled comparison on one element.

---

## Phase 7 — Nonlinear Solve Runtime (Elastic End-to-End)

### P7.1 Newton-Raphson driver generation
- **Scope:** solver driver generation only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/newton_driver.py.j2`
- **Work:** generate iteration loop, residual checks, and linear solve callback usage.
- **Verification:** converges on elastic cantilever benchmark.

### P7.2 Boundary condition codegen
- **Scope:** BC handling only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/boundary_codegen.py`
- **Work:** generate Dirichlet masks/enforcement and Neumann traction assembly.
- **Verification:** BC unit tests for component-wise constraints and traction loads.

### P7.3 Structured Hex8 mesh I/O
- **Scope:** mesh generation/I/O only.
- **Files:** `packages/mechdsl-core/src/mechdsl/solver/mesh_io.py`
- **Work:** implement structured mesh reader/generator + output writer hook.
- **Verification:** mesh integrity tests (node count, connectivity, boundary tags).

### P7.4 Adaptive load stepping runtime
- **Scope:** time/load stepping only.
- **Files:** `packages/mechdsl-core/src/mechdsl/solver/load_stepping.py`
- **Work:** implement adaptive increment control based on convergence behavior.
- **Verification:** synthetic convergence scenario exercises step cutback and growth.

---

## Phase 8 — Plasticity Runtime Integration

### P8.1 Plastic constitutive emitter
- **Scope:** generated radial return only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/constitutive_plastic.py.j2`
- **Work:** emit predictor-corrector update with power-law hardening Newton solve.
- **Verification:** single-point update reproduces reference stress-path.

### P8.2 Algorithmic tangent emitter
- **Scope:** plastic consistent tangent only.
- **Files:** same plastic constitutive template/module as above
- **Work:** emit branch-correct 6x6 tangent for elastic/plastic regimes.
- **Verification:** tangent symmetry + finite-difference match tests.

### P8.3 History field lifecycle support
- **Scope:** state variable storage only.
- **Files:** `packages/mechdsl-core/src/mechdsl/solver/history_fields.py`
- **Work:** define/current-old buffers and converged-step commit routines.
- **Verification:** step-commit tests confirm rollback/commit correctness.

### P8.4 Element kernel switch to elasto-plastic path
- **Scope:** integration seam only.
- **Files:** `packages/mechdsl-core/src/mechdsl/codegen/templates/internal_force.py.j2`
- **Work:** swap elastic-only constitutive call with configurable elastic/plastic dispatch.
- **Verification:** below-yield case equals elastic baseline; above-yield deviates as expected.

---

## Phase 9 — MVP Integration, Regression, and Documentation

### P9.1 Full pipeline e2e test (LaTeX → solve)
- **Scope:** e2e test harness only.
- **Files:** `packages/mechdsl-core/tests/test_e2e.py`
- **Work:** cover parse, IR build, lowering, optimizer, codegen, run, and result checks.
- **Verification:** one command runs full pipeline and asserts expected tolerances.

### P9.2 Generated vs handwritten equivalence tests
- **Scope:** cross-implementation comparison only.
- **Files:** `packages/mechdsl-core/tests/test_codegen.py`
- **Work:** compare field outputs from generated and handwritten references.
- **Verification:** max norm difference threshold satisfied.

### P9.3 Physical benchmark suite hardening
- **Scope:** benchmark tests only.
- **Files:** `packages/mechdsl-core/tests/test_mechanics_ir.py`, `test_frontend.py`, new benchmark test module(s)
- **Work:** encode patch, rigid-body, cantilever, Cook’s membrane, necking bar acceptance checks.
- **Verification:** all benchmark thresholds from PLAN-A achieved.

### P9.4 Compiler-pass coverage closure
- **Scope:** verification matrix mapping only.
- **Files:** `packages/mechdsl-core/tests/*`, `dev/reviews/design_suite_consistency.md`
- **Work:** map and close P/S/M/E/N/T/B/A/C test IDs to concrete tests.
- **Verification:** traceability table shows full pass coverage.

### P9.5 MVP user documentation
- **Scope:** docs only.
- **Files:** `README.md`, `dev/examples/*.tex` (or equivalent examples dir)
- **Work:** add setup, quickstart, and benchmark reproduction instructions.
- **Verification:** docs walkthrough reproduces at least one benchmark locally.

---

## Dependency/parallelism notes

- **Sequential gates:**
  - Phase 0 blocks Phases 1–9.
  - Phase 1 (reference solvers) should finish before final acceptance in Phases 8–9.
  - Phase 2 blocks Phase 4.
  - Phase 3 blocks constitutive portions of Phases 6 and 8.
  - Phase 4 blocks Phase 5 and most of Phase 6.
- **Parallel-safe examples:**
  - `P3.1`/`P3.2`/`P3.4` can run in parallel (distinct files).
  - `P4.1` and `P4.2` can run in parallel if IR contracts are agreed first.
  - `P6.3`/`P6.4`/`P6.5` parallelize via separate template files.
  - `P7.2`/`P7.3`/`P7.4` parallelize cleanly.

## Definition of done for MVP

MVP is complete when all PLAN-A acceptance criteria are met:
1. End-to-end LaTeX-to-solution pipeline is operational.
2. Generated solver matches handwritten reference outputs within defined tolerances.
3. Physical benchmark suite (including necking bar) meets target error bounds.
4. CI enforces lint/type/test/budget checks and remains green.
