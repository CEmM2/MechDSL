# MechDSL Drift Report — 2026-04-20

Generated: 2026-04-26  
Scope: monorepo-wide (`mechdsl-core`, `algo2code`, and `dev/` planning/tracking surfaces)  
Intent baseline: `dev/design_docs/00-OVERVIEW.md` through `11-ALGO2CODE.md`, with primary emphasis on the **LaTeX-driven semantic compiler contract**

---

## Executive summary

The repository still contains the architectural skeleton promised by the design suite, but the implementation has drifted in a specific and consequential way:

- the **original contract** was: LaTeX is the authoritative source, NRPyLaTeX is the math/parser dependency, semantics flow through rich IRs, and Taichi is the sole backend until the MVP is complete;
- the **executed MVP path** became: programmatic construction is the practical entry point, the frontend is reduced to a bespoke directive parser, IRs are thinner than specified, and substantial Plan B scope was implemented before the Plan A frontend contract was fulfilled.

This drift is not uniform. Some parts of the codebase remain strongly aligned with the docs; others are materially ahead of scope but still useful; and a few areas invert the original sequencing assumptions in the design docs.

The most important conclusion is:

> The repo does **not** lack a frontend plan. It contains a concrete NRPyLaTeX workstream. The drift happened because later MVP planning explicitly deferred or bypassed that workstream and the bypass hardened into the actual architecture.

---

## Severity rubric

| Severity | Meaning |
|---|---|
| **Critical** | Violates a core architectural contract or inverts the intended external interface. |
| **High** | Significant mismatch between design intent and implementation shape; affects downstream module boundaries or roadmap sequencing. |
| **Medium** | Partial mismatch, underspecified bridge, or implementation shortcut that is useful but should be normalized. |
| **Low** | Editorial, governance, or naming drift that amplifies confusion but does not by itself break the architecture. |

---

## Intended contract: what the design docs say

The baseline contract implied by the design suite is:

1. **LaTeX-first input contract**  
   - `dev/design_docs/01-ARCHITECTURE.md` Layer 1 is an NRPyLaTeX-based frontend.  
   - `dev/design_docs/02-LATEX-DSL.md` specifies mechanics directives *plus* NRPyLaTeX interaction.  
   - `dev/design_docs/00-OVERVIEW.md` Decision D2 explicitly says **fork NRPyLaTeX, not wrap**.

2. **Semantic-center IR contract**  
   - `dev/design_docs/04-MECHANICS-IR.md` defines a rich `ProblemIR` as the semantic center.  
   - `dev/design_docs/05-ELEMENT-IR.md` defines a correspondingly rich finite-element execution IR.

3. **Strict Plan A sequencing**  
   - Plan A Phase A3: frontend / NRPyLaTeX fork.  
   - Plan A Phases A4–A10: symbolic, IR, lowering, codegen, solver integration, verification.  
   - `dev/design_docs/06-CODEGEN.md` states Taichi is the sole backend until v1.0.

4. **Monorepo split of responsibilities**  
   - `mechdsl-core` handles tensor/mechanics semantics and FEM code generation.  
   - `algo2code` handles algorithm-box LaTeX (`algpseudocode`) for solver scaffolding and return maps (`dev/design_docs/11-ALGO2CODE.md`).

---

## What later MVP execution decided instead

Later planning artifacts made a materially different decision for MVP delivery:

- `dev/plans/MVP_sprint2.md` explicitly says the full NRPyLaTeX fork is out of scope for MVP and that the pipeline entry point is effectively **programmatic construction**.
- `dev/plans/MVP_sprint3.md` marks Plan A A3 (Parser / NRPyLaTeX) as **deferred** and states the MVP is functional without it.
- `dev/diagrams/project_recap.html` and `dev/diagrams/project_recap_2026-04-04.html` both describe the frontend as blocked or skipped, with the pipeline starting from `ProblemIR` rather than LaTeX source.

This is the central fork in the road that explains most of the drift below.

---

## Original design intent vs later MVP deferral

### Detailed list of deferred or ignored plan / phase / tasks

The table below collects the concrete deferrals, bypasses, or early out-of-order implementations that matter to the original contract.

| Design source | Original intent | Later deferral / bypass / ignore | Current status |
|---|---|---|---|
| `PLAN-A.md` A3 | NRPyLaTeX fork and `% mechanics` parser are part of MVP | `MVP_sprint3.md` marks A3 deferred; parser treated as optional UX improvement | **Deferred in planning, only partially recovered in code** |
| `MVP_plan.md` P2.1 | Wire maintained NRPyLaTeX mechanics fork | `tasks-tracker_MVP_plan.md` still shows `not_started` | **Dependency wired in `packages/mechdsl-core/pyproject.toml`, but tracker says not started** |
| `MVP_plan.md` P2.2 | Add mechanics tokenization in NRPyLaTeX fork | No in-repo execution artifact for fork changes; later sprint plans bypassed fork-centric path | **Not evidenced in repo-local fork workflow** |
| `MVP_plan.md` P2.3 | Implement mechanics directive handlers in NRPyLaTeX fork | Bypassed by local bespoke parser in `mechdsl.frontend.parser` | **Semantics implemented locally, not in the planned fork boundary** |
| `MVP_plan.md` P2.4 | Two-manifold index typing inside NRPyLaTeX fork | Bypassed by simpler local index bookkeeping plus deferred math parsing | **Partial / local approximation** |
| `MVP_plan.md` P2.5 | Frontend adapter normalizing fork output into stable schema | Replaced by local parser + `build_context()` path | **Partial, but not on planned fork-to-adapter architecture** |
| `02-LATEX-DSL.md` §3 | Parser-level NRPyLaTeX modifications for two-manifold tensors | Not completed as designed; current parser does not expose full NRPyLaTeX semantic output | **Deferred / only partially emulated** |
| `01-ARCHITECTURE.md` Layer 1 | LaTeX source is the front door | `MVP_sprint2.md` and `MVP_sprint3.md` shift MVP entry to Python/programmatic construction | **External contract inverted for MVP** |
| `04-MECHANICS-IR.md` | Rich `ProblemIR` schema (fields, domain, residual, mesh contract, etc.) | Practical implementation uses a much thinner `ProblemIR` to support downstream work sooner | **Ignored in full detail** |
| `05-ELEMENT-IR.md` | Rich `ElementIR` with geometry/material/local-force/local-tangent sub-IRs | Implementation uses slimmer element metadata plus separate contraction specs | **Ignored in full detail** |
| `06-CODEGEN.md` | Taichi sole backend until v1.0 | MFEM and MOOSE printers were implemented early | **Ignored sequencing contract** |
| `11-ALGO2CODE.md` §1.1 / `PLAN-A.md` A8 | Newton driver eventually swaps imported solver for algo2code-transpiled PCG | No `mechdsl-core` integration points currently import or invoke `algo2code` | **Ignored integration point** |
| `11-ALGO2CODE.md` §1.1 / `PLAN-A.md` A9 | J2 radial return becomes algo2code-transpiled algorithm box | J2 remains manually implemented in `mechdsl-core` symbolic / emitted paths | **Ignored integration point** |
| `01-ARCHITECTURE.md` artifact API | `artifact.bind_mesh(...).bind_bcs(...).bind_materials(...)` runtime shape | Current code uses direct bundle/source emission and mesh-file / BC-array driven runtime paths | **Not implemented as documented** |
| `tasks-tracker_MVP_plan.md` overall | MVP task tracker should reflect execution state | Entire tracker remains `not_started` while significant code exists | **Governance drift / stale planning surface** |

### Deferred tasks list by task ID

The most important deferred or bypassed task group is the Phase 2 frontend workstream:

- **P2.1** — NRPyLaTeX dependency fork wiring  
- **P2.2** — Mechanics directive tokenization  
- **P2.3** — Mechanics directive parsing handlers  
- **P2.4** — Two-manifold index typing  
- **P2.5** — Frontend adapter in `mechdsl-core`

The repo contains these tasks in:
- `dev/plans/MVP_plan.md`
- `dev/tasks/MVP_plan/json/P2.1.json` … `P2.5.json`

But the later sprint execution path deprioritized them and the tracker still records them as not started.

### Deferred design-doc phase list

| Plan phase | Deferred / bypassed element |
|---|---|
| **A3** | Full NRPyLaTeX-based frontend contract |
| **A8 (partial)** | algo2code-based solver replacement |
| **A9 (partial)** | algo2code-based radial-return replacement |
| **A10 (partial)** | end-to-end LaTeX-to-solution contract; current e2e mostly starts later in the pipeline |

---

## Module-by-module drift assessment

## `packages/mechdsl-core/src/mechdsl/frontend/`

**Severity: Critical**

### Drift

The design docs require a LaTeX-first frontend centered on NRPyLaTeX. The current implementation provides:

- `build_context()` in `frontend/__init__.py`
- a bespoke directive parser in `frontend/parser.py`
- local directive handlers in `frontend/directives.py`

This is useful work, but it is not the same contract.

### Evidence

- `packages/mechdsl-core/src/mechdsl/frontend/parser.py` explicitly says MVP only needs directive parsing and that NRPyLaTeX integration remains future work.
- `packages/mechdsl-core/tests/test_frontend.py` is still just a docstring stub.
- `packages/mechdsl-core/pyproject.toml` wires the NRPyLaTeX dependency, but the frontend path does not materially consume the fork as the primary semantic parser.

### Why it matters

This is where the external architecture was inverted:
- intended: LaTeX → parser → normalized semantic context
- current: programmatic context construction is the practical primary API

### Remediation

1. Preserve `build_context()` as a convenience/testing API, but demote it to a secondary entry point.
2. Introduce a real `parse_latex()` / `compile_latex()` façade that becomes the canonical top-level path.
3. Re-anchor the frontend boundary so that fork-specific concerns live in the NRPyLaTeX integration layer and local code becomes an adapter/normalizer, not the parser of record.
4. Finish the Phase 2 task group (`P2.1`–`P2.5`) or explicitly replace it with a new accepted architecture document.

---

## `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py`

**Severity: High**

### Drift

The implemented `ProblemIR` is much thinner than the schema in `dev/design_docs/04-MECHANICS-IR.md`.

Implemented core includes:
- `dim`
- `formulation`
- `element_type`
- `material`
- `boundaries`
- coordinates
- optional configuration/dynamics mode

Missing relative to the spec’s semantic-center role:
- fields
- residual form
- domain / mesh contract
- richer BC entities and topology semantics
- much of the explicit semantic inventory the docs expect

### Evidence

- `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py`
- `dev/design_docs/04-MECHANICS-IR.md`

### Why it matters

The thin IR made downstream progress easy, but it moved semantics out of the central IR and into implicit conventions in lowering, codegen, and runtime glue.

### Remediation

1. Expand `ProblemIR` in a backward-compatible way rather than rewriting it.
2. Add optional rich fields first (`domain`, `mesh_contract`, `fields`, `residual_contract`) with adapters from the current thin form.
3. Keep `from_dict()` compatibility so existing tests and artifacts survive.
4. Move semantic assumptions out of codegen comments and into IR metadata.

---

## `packages/mechdsl-core/src/mechdsl/ir/element_ir.py` and `packages/mechdsl-core/src/mechdsl/lowering/`

**Severity: High**

### Drift

The design-doc `ElementIR` is a rich FE execution IR. The current implementation stores:
- element metadata
- basis
- quadrature
- formulation/configuration/integration rule

but shifts important execution semantics into:
- `EinsumSpec`
- `LocalisationResult`
- printer-side knowledge

### Evidence

- `packages/mechdsl-core/src/mechdsl/ir/element_ir.py`
- `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py`
- `dev/design_docs/05-ELEMENT-IR.md`

### Why it matters

The lowering/codegen interface is thinner and more implicit than the docs promise. This weakens the “IR discipline” story because some execution semantics live outside the main IR object.

### Remediation

1. Add structured sub-objects to `ElementIR` incrementally:
   - geometry summary
   - material-eval contract
   - local force/tangent descriptors
2. Keep existing helpers (`EinsumSpec`, `LocalisationResult`) as derived views rather than primary structures.
3. Ensure codegen consumes enriched IR objects rather than summaries where possible.

---

## `packages/mechdsl-core/src/mechdsl/codegen/`

**Severity: High**

### Drift

Two related drifts occurred here:

1. **IR consumption drift**  
   Docs describe a `TaichiPrinter` class consuming `ElementIR` and `ProblemIR`.  
   Current implementation uses `ArtifactBundle` + module-level `emit(...)` functions.

2. **backend scope drift**  
   The design docs say Taichi is the sole backend until v1.0.  
   The repo already includes:
   - `mfem_printer.py`
   - `moose_printer.py`
   - MFEM template assets

### Evidence

- `packages/mechdsl-core/src/mechdsl/codegen/__init__.py`
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`
- `packages/mechdsl-core/src/mechdsl/codegen/mfem_printer.py`
- `packages/mechdsl-core/src/mechdsl/codegen/moose_printer.py`
- `dev/design_docs/06-CODEGEN.md`

### Why it matters

The early extra backends are useful work, but they weaken the sequencing discipline of the original plan and increase maintenance load before the frontend contract is settled.

### Remediation

1. Keep the existing emitters.
2. Introduce a stable backend interface that explicitly distinguishes:
   - `stable`: Taichi
   - `experimental`: MFEM / MOOSE
3. Make the Taichi path the only path exercised by the canonical LaTeX-to-solution compile contract until frontend/IR alignment is restored.
4. Reintroduce a class-based printer façade if that improves doc alignment; keep module-level emitters behind it.

---

## `packages/mechdsl-core/src/mechdsl/solver/`

**Severity: Medium**

### Drift

The solver/runtime layer is useful and broadly compatible with the docs, but it has become more of a real runtime substrate than the thinner driver sketched in the design docs.

Notable drift points:
- explicit dynamics utilities exist early (`critical_timestep.py`, `lumped_mass.py`)
- load stepping and history management are real runtime surfaces
- runtime behavior is often driven by mesh arrays / BC masks rather than the richer boundary/domain model described in the docs

### Evidence

- `packages/mechdsl-core/src/mechdsl/solver/newton.py`
- `packages/mechdsl-core/src/mechdsl/solver/load_stepping.py`
- `packages/mechdsl-core/src/mechdsl/solver/critical_timestep.py`
- `packages/mechdsl-core/src/mechdsl/solver/lumped_mass.py`

### Why it matters

This is not harmful by itself. The risk is mainly that runtime conventions have solidified independently of the richer compiler/runtime contract in the design docs.

### Remediation

1. Keep the runtime layer largely intact.
2. Introduce thin adapter layers so generated artifacts/runtime binding look more like the documented API.
3. Avoid rewriting stable solver internals unless required by the frontend/IR reconciliation.

---

## `packages/mechdsl-core/src/mechdsl/symbolic/`

**Severity: Medium**

### Drift

The symbolic layer is generally strong, but it is ahead of the MVP scope:
- advanced hyperelasticity
- viscoplasticity
- damage
- objective-rate / UL-related support

### Evidence

- models under `packages/mechdsl-core/src/mechdsl/symbolic/models/`
- `objective_rates.py`
- `convected.py`

### Why it matters

This is good technical work. The issue is sequencing, not quality. The symbolic layer expanded while the frontend contract remained incomplete.

### Remediation

1. Preserve all implemented models.
2. Define a strict model-availability matrix:
   - MVP-stable
   - experimental / Plan B
3. Make the frontend/compiler contract explicitly reject or gate experimental models when compiling under the MVP profile.

---

## `packages/mechdsl-core/src/mechdsl/verify/` and `packages/mechdsl-core/tests/`

**Severity: Medium**

### Drift

The repo has built a large and valuable test/verification surface, but it also documents the frontend gap clearly:
- frontend e2e remains incomplete from actual LaTeX input
- many tests start from `ProblemIR`, not from LaTeX source
- empty or stub frontend test surfaces still exist (`test_frontend.py`)

### Evidence

- `packages/mechdsl-core/tests/test_frontend.py`
- `packages/mechdsl-core/tests/test_e2e.py`
- `dev/reviews/design_suite_consistency.md`

### Why it matters

The verification story is strong internally, but not yet aligned with the external contract promised by the docs.

### Remediation

1. Add a dedicated frontend contract suite once the parser boundary is restored.
2. Split e2e tests into:
   - `from_problem_ir`
   - `from_latex`
3. Keep all current tests; do not delete working verification just because it starts too late in the pipeline.

---

## `packages/algo2code/`

**Severity: Medium**

### Drift

`algo2code` is real, implemented, and broadly aligned with its own design doc. The drift is not internal quality but **missing integration** into the main compiler flow.

### Evidence

- `packages/algo2code/src/algo2code/algo_parser.py`
- `packages/algo2code/src/algo2code/expr_parser.py`
- `packages/algo2code/src/algo2code/type_inference.py`
- `packages/algo2code/src/algo2code/backends/taichi_codegen.py`
- `packages/algo2code/tests/test_end_to_end.py`
- `dev/design_docs/11-ALGO2CODE.md`

### Current alignment status

Positive:
- real LaTeX-driven algorithm pipeline exists
- architecture roughly matches its spec
- zero-runtime-dependency goal is preserved in `packages/algo2code/pyproject.toml`

Negative:
- `mechdsl-core` has no current integration imports/usages of `algo2code`
- the two explicit Plan A integration points (PCG and radial return) have not been wired in
- only Taichi backend is publicly active in practice

### Remediation

1. Preserve `algo2code` as-is; it is useful work.
2. Add an interface layer in `mechdsl-core` for optional algorithm-source replacement:
   - solver algorithm source = imported existing implementation OR algo2code-generated
3. Wire **PCG integration first**; defer radial-return substitution until frontend/IR contract is stabilized.
4. Keep `algo2code` independent; do not merge it into `mechdsl-core`.

---

## `dev/` planning, tracking, and review surfaces

**Severity: High**

### Drift

The planning surfaces are internally contradictory:
- the design docs and MVP Phase 2 tasks clearly plan an NRPyLaTeX-centered frontend
- later sprint plans explicitly defer that contract
- the task tracker still reports broad areas as `not_started` even though code exists

### Evidence

- `dev/plans/MVP_plan.md`
- `dev/plans/MVP_sprint2.md`
- `dev/plans/MVP_sprint3.md`
- `dev/tasks/MVP_plan/json/P2.1.json` … `P2.5.json`
- `dev/tracking/tasks-tracker_MVP_plan.md`

### Why it matters

This is governance drift. It makes it hard to tell whether the repo is:
- behind plan,
- intentionally off-plan,
- or already superseding the plan.

### Remediation

1. Declare one active architecture contract and one archive contract.
2. Mark deferred tasks explicitly as `deferred`, not `not_started`, when that is what happened.
3. Record whether a task was:
   - implemented as planned,
   - implemented via substitute path,
   - intentionally skipped.

---

## Reconciliation table

This table is the working bridge between what should be preserved and what must change.

| Area | Preserve | Realign | First concrete step |
|---|---|---|---|
| Frontend | `build_context()`, directive handlers, local validation | Restore LaTeX-first canonical path and fork/adapter boundary | Introduce top-level `compile_latex()` façade and define adapter contract |
| Mechanics IR | existing dataclass, validation, serialization | Add missing semantic fields rather than replacing the object | Add optional `domain`, `fields`, `mesh_contract`, `residual_contract` |
| Element IR | basis/quadrature/integration machinery | Promote hidden execution semantics into structured IR sub-objects | Add geometry/material/local-force/local-tangent descriptors |
| Taichi codegen | current emitters and tested logic | Reconnect emitters to enriched IR and mark Taichi as stable path | Add backend stability tiers and class façade |
| MFEM/MOOSE | keep as experimental assets | Remove them from the MVP contract surface | Mark as experimental in docs and tests |
| Solver/runtime | keep Newton, load stepping, history, mesh utilities | Rebind to richer artifact/runtime API | Introduce artifact/runtime adapter layer |
| Symbolic models | preserve implemented models | Add stable-vs-experimental gating | Define model availability matrix |
| algo2code | preserve package and tests | Wire planned integration points incrementally | Integrate PCG first behind `LinearSolverInterface` |
| Planning/tracking | preserve historical documents | Normalize status language and archive superseded execution plans | Update tracker states and decision log |

---

## Alignment section

The alignment goal is **not** to roll back useful work. The alignment goal is to restore the design-doc intent while preserving the hard-won implementation assets.

### Principles for alignment

1. **Do not delete functioning subsystems solely because they arrived early.**  
   Advanced symbolic models, extra elements, and backend experiments are assets.

2. **Restore the external contract before rewriting internals.**  
   The biggest architectural error is the lost LaTeX-first contract, not the presence of extra models.

3. **Use adapters before rewrites.**  
   Where current code is thinner than the spec, wrap and extend it instead of replacing it wholesale.

4. **Separate “stable MVP path” from “experimental scope.”**  
   This preserves useful work while re-establishing sequencing discipline.

5. **Keep `algo2code` independent but integrated.**  
   It is the algorithm-box LaTeX half of the monorepo contract and should be treated as such.

### Alignment target state

A realigned repo should have:

- a canonical public path that starts from LaTeX input;
- programmatic construction kept as a secondary/testing API;
- richer IRs that absorb semantic assumptions currently spread across codegen/runtime;
- Taichi as the only stable compile target for the canonical MVP path;
- MFEM/MOOSE and advanced models clearly marked experimental;
- at least one actual end-to-end path that exercises:
  - LaTeX mechanics frontend,
  - semantics into IR,
  - lowering,
  - Taichi codegen,
  - runtime solve.

---

## Recovery plan — what to refactor first

This recovery plan is intentionally incremental. The objective is to realign the implementation with the design docs **without torching the useful work**.

## Phase R0 — Freeze the contract surface

**Goal:** stop further drift while preserving current code.

### Actions

1. Declare two contract profiles in docs and tests:
   - **MVP-stable**
   - **experimental**
2. Mark the following as experimental:
   - MFEM/MOOSE printers
   - explicit dynamics
   - non-MVP material models
   - non-Hex8 elements in the canonical compile path
3. Update `dev/tracking/tasks-tracker_MVP_plan.md` status language:
   - `done`
   - `deferred`
   - `implemented-via-substitute`
   - `not_started`

### Why first

This step prevents more ambiguity while leaving all useful code in place.

---

## Phase R1 — Restore the frontend as the canonical entry point

**Goal:** realign the external interface before touching deeper internals.

### Actions

1. Introduce a new canonical façade in `mechdsl-core`:
   - `compile_latex(source: str, profile: str = "mvp")`
2. Reframe current local parser/build-context code as an adapter layer:
   - local directive parser stays usable
   - NRPyLaTeX integration becomes the math/frontend boundary of record
3. Finish or formally replace the `P2.1`–`P2.5` task group.
4. Add a frontend contract test suite that starts from LaTeX source.

### Preserve

- `build_context()`
- current directive parser
- tests that start from programmatic state

### Why second

The original drift began here. Fixing the front door gives the rest of the architecture something real to line up behind.

---

## Phase R2 — Enrich `ProblemIR` without breaking compatibility

**Goal:** move semantics back into the semantic center.

### Actions

1. Add optional rich fields to `ProblemIR`:
   - `fields`
   - `domain`
   - `mesh_contract`
   - `residual_contract`
2. Add adapter constructors from the current thin form.
3. Keep `to_dict()` / `from_dict()` backward compatible.
4. Update lowering to consume the richer structure when present.

### Preserve

- current `ProblemIR` validation behavior
- serialization round-trips
- existing tests

### Why third

This repairs the architecture while minimizing churn.

---

## Phase R3 — Enrich `ElementIR` and re-anchor lowering/codegen boundaries

**Goal:** make the IR discipline true again.

### Actions

1. Add structured sub-objects or equivalent fields for:
   - geometry contract
   - material evaluation contract
   - local force contract
   - local tangent contract
2. Keep `EinsumSpec` as a derived optimization view rather than the primary semantic carrier.
3. Make the Taichi printer consume richer IR data rather than summaries where feasible.

### Preserve

- existing basis/quadrature code
- optimizer integration
- artifact bundling

### Why fourth

Once frontend and `ProblemIR` are stabilized, this is the next leverage point for restoring the documented architecture.

---

## Phase R4 — Integrate `algo2code` at the least risky integration point

**Goal:** recover the monorepo’s two-package LaTeX story incrementally.

### Actions

1. Add an optional `algo2code`-generated PCG path behind `LinearSolverInterface`.
2. Keep the current imported solver adapter as fallback.
3. Add only one integration test for this path initially.
4. Defer radial-return substitution until after frontend/IR alignment is restored.

### Preserve

- existing solver runtime
- current J2 implementation
- all working `algo2code` internals

### Why now

This recovers planned monorepo integration without destabilizing constitutive codegen too early.

---

## Phase R5 — Normalize documentation and governance

**Goal:** make the repo understandable again.

### Actions

1. Update or add an architecture decision record explaining the MVP deferral and recovery path.
2. Archive superseded sprint planning notes as historical execution records.
3. Update review and tracking docs to reflect:
   - what was intentionally deferred,
   - what was implemented via substitute path,
   - what remains genuinely undone.

### Why last

Because governance should reflect the stabilized recovery strategy, not lead it blindly.

---

## Recommended execution order

If only a small amount of work can be done now, the highest-leverage order is:

1. **R0 — freeze stable vs experimental contract surface**  
2. **R1 — restore canonical LaTeX frontend façade**  
3. **R2 — enrich `ProblemIR` compatibly**  
4. **R4 — integrate algo2code PCG path**  
5. **R3 — enrich `ElementIR` / lowering boundary**  
6. **R5 — normalize docs / trackers**

If only one code refactor is possible in the near term, it should be:

> **restore the frontend contract first**

because that is the smallest change with the biggest architectural payoff.

---

## Final recommendation

Do **not** attempt a ground-up rewrite. The repo already contains substantial, valuable implementation work.

Instead:

- preserve the working symbolic, solver, verification, and algo2code assets;
- quarantine experimental scope;
- restore the LaTeX-first contract at the top of the stack;
- enrich the IRs through adapters and additive refactors;
- wire `algo2code` into the driver incrementally.

That path realigns the implementation with the design docs while keeping the work that already paid rent.
