# Recovery Plan — Re-establish the LaTeX Compiler Contract

**Date:** 2026-04-26  
**Status:** Proposed active recovery plan  
**Primary source:** `dev/reviews/drift_20_04.md`  
**Recovery-status pointer:** `dev/reviews/recovery_status_2026_04.md` (cross-link note tying this plan to the drift audit)  
**Intent baseline:** `dev/design_docs/00-OVERVIEW.md` through `11-ALGO2CODE.md`  
**Supersedes as execution guide:** ad-hoc recovery discussion only; does **not** modify the design docs  

---

## Goal

Realign the implementation with the original **LaTeX-driven semantic compiler contract** without discarding useful implementation work already present in the repository.

In concrete terms, this plan restores:

1. a **canonical LaTeX-first entrypoint**;
2. richer semantic ownership in `ProblemIR` and `ElementIR`;
3. a stable MVP path centered on **Taichi only**;
4. a disciplined separation between **stable** and **experimental** scope;
5. an incremental integration path for `algo2code`.

---

## Non-goals

This plan explicitly does **not** aim to:

- rewrite the repo from scratch;
- delete advanced symbolic/runtime/codegen work merely because it arrived early;
- merge `algo2code` into `mechdsl-core`;
- expand backend support beyond what already exists;
- revise `dev/design_docs/*` as part of the first recovery wave.

---

## Recovery principles

1. **Restore the contract before rewriting internals.**  
   The biggest drift is at the front door, not in the existence of extra features.

2. **Prefer additive refactors and adapters.**  
   Existing working code should be wrapped, promoted, or gated before being replaced.

3. **Preserve useful work, quarantine premature scope.**  
   Experimental features may stay in-tree, but they must stop defining the primary story.

4. **Make the stable path testable from LaTeX.**  
   The stable contract is not recovered until at least one real LaTeX-to-solution path exists.

5. **Keep governance honest.**  
   Planning/tracking artifacts must distinguish `deferred`, `implemented-via-substitute`, and `done`.

---

## Success criteria

This recovery plan is considered successful when all of the following are true:

- [ ] `mechdsl-core` exposes a canonical `compile_latex(...)` or equivalent façade.
- [ ] The stable path starts from LaTeX input, not only from `build_context()`.
- [ ] `ProblemIR` carries the minimum semantic fields needed to act as the semantic center again.
- [ ] `ElementIR` carries explicit execution-contract structure rather than relying primarily on implicit summaries.
- [ ] Taichi is the only **stable** backend in docs/tests for the canonical path.
- [ ] MFEM/MOOSE and non-MVP scope are clearly labeled experimental.
- [ ] At least one end-to-end verification path runs from LaTeX input through code generation and solve.
- [ ] `algo2code` is integrated at one low-risk point (PCG first).
- [ ] Recovery status is reflected honestly in `dev/plans/`, `dev/tasks/`, and `dev/tracking/`.
- [ ] All canonical task IDs in `dev/tasks/recovery_plan_latex_contract/json/` reach `done` status, with their corresponding GitHub issues closed.

---

## Planning assumptions

- The repo already contains valuable working code in `symbolic`, `solver`, `verify`, and `algo2code`.
- The frontend drift is architectural, not primarily a compile-break issue.
- The NRPyLaTeX dependency is already wired in `packages/mechdsl-core/pyproject.toml`, but the integration contract is incomplete.
- Recovery should proceed in **small, reviewable slices** that preserve current tests wherever possible.

---

## Phase ID mapping (R-label ↔ Aut_Faciam integer)

This plan is decomposed by `Aut_Faciam` (`Plan-2-Tasks`), which requires sequential integer phase IDs. The R-labels below are the prose names used in `dev/reviews/drift_20_04.md`; the integer column is the canonical Aut_Faciam phase ID and is what appears in branch names, GitHub labels, gate files, and task IDs.

| Aut_Faciam phase | R-label | Phase name (short)                         |
|------------------|---------|--------------------------------------------|
| 1                | R0      | Freeze the contract surface                |
| 2                | R1      | Restore the canonical LaTeX frontend       |
| 3                | R2      | Enrich `ProblemIR`                         |
| 4                | R3      | Enrich `ElementIR` and lowering            |
| 5                | R4      | Re-anchor Taichi as the stable codegen     |
| 6                | R5      | Integrate `algo2code` at the PCG seam      |
| 7                | R6      | Verification, governance, closure          |

Task IDs use the canonical `P<phase>-<seq>` form (e.g. `P1-1`); the legacy `R0.1` form is preserved alongside in tables for traceability with the drift report.

---

## Phase 1 — Freeze the contract surface (R0)

**Goal:** Stop further architectural drift and establish a stable vs experimental boundary.

**Why first:** Without a declared contract surface, every subsequent refactor remains ambiguous.

### Code reality anchor (2026-04-26)

- `dev/tracking/tasks-tracker_MVP_plan.md` rows are all `not_started`; only two status values exist in practice across the live trackers.
- `dev/plans/` already holds 13 plan files and `dev/tracking/` holds 8 trackers, with no explicit "active vs archived" marker on any of them.
- The mismatch this phase corrects: there is no published stable/experimental boundary, and the four-value status vocabulary (`done`, `deferred`, `implemented-via-substitute`, `not_started`) is not yet legal in any tracker.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P1-1 | R0.1 | Define two support tiers for the repo: `MVP-stable` and `experimental`. | `README.md`, package docs, release notes, recovery plan references | — | docs | Documentation review confirms each public feature is assigned a tier. |
| P1-2 | R0.2 | Mark MFEM/MOOSE codegen, explicit dynamics, non-MVP materials, and non-canonical elements as experimental for the canonical compile path. | `packages/mechdsl-core/src/mechdsl/codegen/**`, runtime docs, examples | P1-1 | docs | No canonical docs/examples present experimental features as default behavior. |
| P1-3 | R0.3 | Add a lightweight “stability policy” note to developer-facing docs. | `README.md` or `dev/reviews/` follow-up note | P1-1 | docs | Policy is visible and references this plan. |
| P1-4 | R0.4 | Normalize tracker vocabulary to distinguish `done`, `deferred`, `implemented-via-substitute`, and `not_started`. | `dev/tracking/tasks-tracker_MVP_plan.md`, related trackers | — | docs | Tracker rows no longer imply untouched work where substitute implementations exist. |
| P1-5 | R0.5 | Record the frontend deferral explicitly as historical execution drift, not missing design intent. | `dev/reviews/`, tracker notes, optional ADR-style note | — | docs | Recovery artifacts clearly distinguish “planned but deferred” from “never planned”. |
| P1-6 | R0.6 (new) | Mark `dev/plans/MVP_plan.md` and `dev/plans/MVP_sprint{1,2,3}.md` as superseded by this recovery plan for the frontend contract; add a banner pointing here and an explicit `superseded` tag. | `dev/plans/MVP_plan.md`, `dev/plans/MVP_sprint1.md`, `dev/plans/MVP_sprint2.md`, `dev/plans/MVP_sprint3.md` | P1-4 | docs | Each superseded plan has a top banner; tracker rows for old P2.1..P2.5 carry `implemented-via-substitute` (not `not_started`). |

### Cross-phase dependencies

This phase blocks: — (Phase 1 outputs are docs/tracker; downstream phases depend on them only weakly).
This phase is blocked by: — (no upstream dependencies).

### Exit criteria

- Stable/experimental scope is documented.
- Tracker status language supports truthful recovery reporting.
- No new work begins without being classified into one of the two support tiers.

---

## Phase 2 — Restore the frontend as the canonical entry point (R1)

**Goal:** Re-establish LaTeX input as the primary public contract.

**Why now:** This is the highest-leverage correction. The architecture cannot be “LaTeX-driven” if the practical front door is Python object construction.

### Code reality anchor (2026-04-26)

- `mechdsl/__init__.py:7` exports only `compile` (re-exported from `codegen`); `frontend/__init__.py` exports `build_context`, `parse`, `parse_file` but no LaTeX façade.
- `frontend/parser.py:11-17` explicitly defers nrpylatex math grammar to "Plan B"; `tests/test_frontend.py` is a stub. `nrpylatex` is wired in `pyproject.toml` but never imported under `src/`.
- The mismatch this phase corrects: no canonical `compile_latex(...)` entrypoint exists, so the LaTeX-first contract has no public surface to call.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P2-1 | R1.1 | Introduce a canonical façade, e.g. `compile_latex(source: str, profile: str = "mvp")`. | `packages/mechdsl-core/src/mechdsl/__init__.py`, frontend public API | — | unit | API smoke test imports and calls the façade successfully. |
| P2-2 | R1.2 | Preserve `build_context()` as a convenience/testing API, but document it as secondary. | `packages/mechdsl-core/src/mechdsl/frontend/__init__.py`, docs | P2-1 | unit | Public docs show LaTeX-first examples before programmatic examples. |
| P2-3 | R1.3 | Define the frontend split explicitly: NRPyLaTeX fork/integration = parser of record; local code = adapter/normalizer/validator. | `packages/mechdsl-core/src/mechdsl/frontend/**` | P2-1 | unit | Source layout and docstrings reflect the separation of responsibilities. |
| P2-4 | R1.4 | Reconcile or replace the old Phase 2 tasks (`P2.1`–`P2.5`) with the actual recovery tasks. | `dev/plans/`, `dev/tasks/`, `dev/tracking/` | — | docs | No duplicate/conflicting frontend task sets remain active. |
| P2-5 | R1.5 | Add a minimal frontend contract test suite that begins from LaTeX source. | `packages/mechdsl-core/tests/test_frontend*.py`, e2e tests | P2-1, P2-3 | integration | At least one test starts from LaTeX, reaches normalized frontend output, and validates the stable contract. |
| P2-6 | R1.6 | Ensure frontend failures produce contract-level errors (unsupported syntax, missing directives, invalid tensor/index semantics). | frontend parser/adapter layers | P2-1, P2-5 | integration | Negative tests cover malformed/unsupported LaTeX cases with stable error messages. |

### Required constraints

- Do **not** remove `build_context()`.
- Do **not** make the first step a large frontend rewrite.
- Do **not** block recovery on full parser completeness; a thin but canonical stable subset is sufficient at first.

### Cross-phase dependencies

This phase blocks: P3-1, P3-2, P5-4, P7-2.
This phase is blocked by: — (no upstream dependencies; Phase 1 docs are advisory).

### Exit criteria

- LaTeX input is the documented primary entry point.
- A minimal stable compiler path begins at LaTeX source.
- Frontend task ownership is no longer split across contradictory planning artifacts.

---

## Phase 3 — Enrich `ProblemIR` into the semantic center again (R2)

**Goal:** Move semantics back into the mechanics IR without breaking current consumers.

**Why here:** Once the front door is canonical again, the next requirement is to make the semantic center real rather than implied.

### Code reality anchor (2026-04-26)

- `ir/mechanics_ir.py:113` is `@dataclass(frozen=True)`; the existing `ProblemIR` field list runs roughly `:210-219`.
- `BoundaryCondition.to_dict/from_dict` exist (`mechanics_ir.py:124-145`); `MaterialSpec.to_dict/from_dict` exist (`:155-168`); `ProblemIR.to_dict/from_dict` also already exist (`:336/353` at audit time) but cover only the original 10 fields. **Anchor correction (2026-04-27 P3-1 retrospective):** the earlier wording said "`ProblemIR` itself has no `to_dict/from_dict`" which was wrong at audit time; the methods existed.
- The mismatch this phase corrects: P3-1's "round-trip tests" require `ProblemIR.to_dict/from_dict` to round-trip *the new optional enrichment fields*, not just the original 10. The existing methods get **extended**, not added from scratch.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P3-1 | R2.1 | Add optional semantic fields to `ProblemIR`: `fields`, `domain`, `mesh_contract`, `residual_contract`. | `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | P2-1 | integration | Serialization + round-trip tests preserve old and new forms. |
| P3-2 | R2.2 | Add compatibility constructors/adapters from the current thin representation. | same + frontend adapters | P3-1 | unit | Existing tests still pass without immediate downstream rewrites. |
| P3-3 | R2.3 | Move boundary/domain assumptions out of scattered runtime/codegen logic and into IR metadata where possible. | `ir/`, `lowering/`, `solver/`, `codegen/` | P3-1, P3-2 | regression | Reduced duplication of semantic assumptions in downstream layers. |
| P3-4 | R2.4 | Define a stable `ProblemIR` minimal subset for the MVP-stable contract. | IR docs, tests | P3-1 | unit | Tests explicitly validate the stable subset and reject unsupported combinations cleanly. |
| P3-5 | R2.5 | Add targeted IR validation for semantics that were previously implicit. | `packages/mechdsl-core/tests/test_mechanics_ir.py` | P3-1, P3-2 | integration | Invalid configurations fail at IR construction rather than much later in codegen/runtime. |

### Required constraints

- Backward compatibility is mandatory for the initial enrichment pass.
- `ProblemIR` remains an immutable dataclass-based surface.
- Do not push transient optimizer or printer-specific details into `ProblemIR`.

### Cross-phase dependencies

This phase blocks: P4-1, P4-3, P5-4.
This phase is blocked by: P2-1.

### Exit criteria

- `ProblemIR` can carry the semantic minimum promised by the design docs.
- Existing consumers remain functional via adapters.
- More semantics are validated at IR-construction time.

---

## Phase 4 — Enrich `ElementIR` and normalize lowering boundaries (R3)

**Goal:** Make the IR discipline true in practice, not just in naming.

**Why now:** The current lowering/codegen contract works, but too much execution meaning is hidden in helper structures and printer knowledge.

### Code reality anchor (2026-04-26)

- `ir/element_ir.py:35-89` already carries basis/quadrature/integration metadata; the dataclass is frozen.
- `lowering/fe_localise.py:35-66` defines `EinsumSpec` and `LocalisationResult`, both frozen dataclasses, currently treated as primary semantic carriers downstream.
- The mismatch this phase corrects: `ElementIR` does not yet carry an explicit execution-contract block (geometry summary, material-eval contract, force/tangent descriptors), so `EinsumSpec` ends up doing semantic work it should not own.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P4-1 | R3.1 | Add structured execution-contract fields to `ElementIR` (geometry summary, material-eval contract, local force/tangent descriptors). | `packages/mechdsl-core/src/mechdsl/ir/element_ir.py` | P3-1 | integration | New IR tests verify presence, validation, and serialization behavior. |
| P4-2 | R3.2 | Keep `EinsumSpec` and `LocalisationResult`, but demote them to derived/optimization views rather than the primary semantic carrier. | `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py` | P4-1 | unit | Lowering tests show enriched IR survives independently of optimizer views. |
| P4-3 | R3.3 | Rework lowering so it emits richer `ElementIR` first, then derives contraction/optimizer artifacts from it. | `lowering/`, `codegen/artifact.py` | P3-1, P4-1, P4-2 | regression | Localisation tests validate both IR richness and optimizer compatibility. |
| P4-4 | R3.4 | Make unsupported stable-path combinations fail in lowering with clear phase-scoped guidance. | `lowering/`, error message tests | P4-1, P4-3 | integration | Unsupported combinations fail deterministically and mention the right recovery/plan phase. |
| P4-5 | R3.5 | Update artifact bundling to reflect enriched IR ownership cleanly. | `packages/mechdsl-core/src/mechdsl/codegen/artifact.py` | P4-1 | unit | Artifact serialization preserves enriched IR plus derived plans. |

### Required constraints

- Do not break existing optimizer work.
- Do not delete proven helper structures unless a richer replacement is already in place.
- Avoid backend-specific leakage into IR types.

### Cross-phase dependencies

This phase blocks: P5-4, P7-2.
This phase is blocked by: P3-1.

### Exit criteria

- `ElementIR` carries explicit execution semantics.
- Lowering produces semantically rich IR before optimizer views.
- Artifact bundling reflects the intended IR hierarchy more faithfully.

---

## Phase 5 — Re-anchor Taichi codegen as the stable path (R4)

**Goal:** Preserve codegen assets while making the stable contract unambiguous.

**Why now:** The stable path should be recoverable without deleting experimental backend work.

### Code reality anchor (2026-04-26)

- `codegen/__init__.py:10-20` exposes `compile(problem_ir) -> ArtifactBundle`; `taichi_printer.py:61` defines an `EmissionContext` class plus module-level `emit_preamble`, `emit_constants`, `emit_field_declarations`, `emit_constitutive_update` helpers (around `:323+`). **Anchor correction (2026-04-27 P3-1 retrospective):** the earlier wording said "no module-level `emit*` functions in `taichi_printer.py`" which was wrong at audit time; the helpers existed.
- `codegen/mfem_printer.py` and `codegen/moose_printer.py` exist alongside the Taichi printer; nothing in code or docs labelled them experimental at audit time (now corrected by recovery P1-2).
- The mismatch this phase corrects: the experimental backends still sit on the same surface as the stable Taichi path. A small façade layer (R4.3) consolidates the `emit_*` helpers behind a design-doc-aligned API while preserving current emitters.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P5-1 | R4.1 | Define Taichi as the only stable backend for the canonical LaTeX compile path. | docs, package API docs, examples | — | docs | Stable examples use Taichi only. |
| P5-2 | R4.2 | Mark MFEM/MOOSE printers as experimental backend surfaces. | `packages/mechdsl-core/src/mechdsl/codegen/**`, docs | — | docs | Tests/docs label these backends as experimental. |
| P5-3 | R4.3 | Add a small façade layer if needed to present codegen in the design-doc style while preserving current emitters. | `taichi_printer.py`, package exports | — | unit | Snapshot/API tests confirm façade stability without loss of current behavior. |
| P5-4 | R4.4 | Ensure the Taichi path consumes enriched IR data where available rather than relying primarily on implicit summaries. | Taichi printer + lowering integration | P2-1, P3-1, P4-1 | unit | Codegen tests show canonical path works with enriched IR fields. |
| P5-5 | R4.5 | Split codegen verification into stable vs experimental suites. | `packages/mechdsl-core/tests/test_codegen*.py` | P5-1 | regression | Stable suite passes independently of experimental backend status. |

### Required constraints

- Keep existing backend code in-tree.
- Do not allow experimental backend status to block stable-path verification.
- Do not widen the stable backend set during recovery.

### Cross-phase dependencies

This phase blocks: P7-2, P7-5.
This phase is blocked by: P2-1, P3-1, P4-1 (only P5-4 needs all three; the rest are independent).

### Exit criteria

- Taichi is clearly the stable path again.
- Experimental backend code is preserved but no longer defines the public contract.
- Codegen tests reflect this distinction.

---

## Phase 6 — Integrate `algo2code` at the least risky seam (R5)

**Goal:** Recover the intended monorepo relationship incrementally.

**Why here:** `algo2code` is already useful; the right move is to connect it at the safest planned seam, not to force deep replacement immediately.

### Code reality anchor (2026-04-26)

- `solver/import_adapter.py:26-57` defines `LinearSolverInterface` (Protocol) plus `CGSolver` and `PCGSolver` concrete adapters.
- `algo2code` is a sibling package with its own pipeline (`algo_parser → expr_parser → type_inference → backends/taichi_codegen`).
- The mismatch this phase corrects: there are zero `algo2code` imports anywhere under `packages/mechdsl-core/src/`, so the monorepo relationship is design-doc only — no actual integration seam exists yet.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P6-1 | R5.1 | Add an optional `algo2code`-generated PCG path behind `LinearSolverInterface`. | `solver/import_adapter.py`, solver integration layer, `algo2code` interface hook | P4-1 | integration | Integration test proves a generated PCG path can satisfy the solver interface. |
| P6-2 | R5.2 | Keep the current imported solver path as the default fallback until generated PCG is stable. | same | P6-1 | unit | Solver regression tests pass with both fallback and generated modes. |
| P6-3 | R5.3 | Add a single stable integration test for `algo2code` → PCG → Newton solve plumbing. | targeted integration tests | P6-1, P6-2 | integration | Test passes without requiring broader algo2code substitution. |
| P6-4 | R5.4 | Defer radial-return replacement until frontend + IR alignment is settled. | planning docs only | — | docs | Recovery docs explicitly label radial-return substitution as later-stage work. |
| P6-5 | R5.5 | Document `algo2code`’s role in the recovered architecture to prevent renewed drift. | `README.md`, architecture docs, examples | P6-1 | docs | Public architecture description includes both packages and their relationship. |

> **Deferral note (P6-4 — radial-return substitution):**
> Replacing the imported J2 radial-return path with an `algo2code`-generated
> equivalent is **later-stage work, deferred** until the recovery plan's
> frontend + IR alignment phases (Phase 2 / R2 and Phase 3 / R3) have
> settled. Rationale: the radial-return kernel sits behind the constitutive
> contract, which depends on the canonical `ProblemIR` field set (Phase 3,
> R3) and the LaTeX-driven frontend façade (Phase 2, R2). Substituting it
> before those layers stabilise risks re-introducing the very contract
> drift this recovery plan is correcting. The first `algo2code` integration
> wave (this phase) is therefore deliberately scoped to the linear-solver
> seam (P6-1..P6-3) only; radial-return replacement returns as a candidate
> task once R2 + R3 close, and is tracked as **post-MVP** work relative to
> Phase 6's exit criteria.

### Required constraints

- Do not merge package boundaries.
- Do not replace the current J2 implementation in the first integration wave.
- Keep `algo2code` runtime-independence intact.

### Cross-phase dependencies

This phase blocks: — (no later phase depends on `algo2code` integration on the stable path).
This phase is blocked by: P4-1 (P6-1 needs the enriched ElementIR before wiring the PCG seam).

### Exit criteria

- One real, low-risk integration point exists.
- The monorepo relationship is architectural reality, not only design-doc intent.
- The generated PCG path remains optional until proven stable.

---

## Phase 7 — Verification, governance, and closure (R6)

**Goal:** Make the recovered contract testable, documented, and traceable.

**Why last:** Governance should describe the stabilized recovery state, not speculate ahead of it.

### Code reality anchor (2026-04-26)

- `tests/test_e2e.py:1-80` constructs `ProblemIR` directly via a `_make_elastic_problem_ir()` helper.
- No test currently starts from a LaTeX string anywhere in the suite.
- The mismatch this phase corrects: end-to-end coverage cannot demonstrate the LaTeX-driven contract because every e2e test bypasses the frontend entirely; recovery is incomplete until at least one acceptance test runs from a LaTeX source.

### Action items

| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
| P7-1 | R6.1 | Split end-to-end tests into `from_latex` and `from_problem_ir` families. | `packages/mechdsl-core/tests/**` | P5-1 | integration | CI/test selection makes the boundary explicit. |
| P7-2 | R6.2 | Add at least one canonical LaTeX-to-solution acceptance test on the MVP-stable path. | e2e tests, examples | P2-1, P4-1, P5-1 | integration | Acceptance test passes starting from LaTeX input. |
| P7-3 | R6.3 | Update examples so the stable story begins from LaTeX input; keep programmatic examples as advanced/testing aids. | `examples/`, `README.md` | P2-1 | docs | First-run example in docs uses the canonical path. |
| P7-4 | R6.4 | Add a short architecture decision or recovery-status note cross-linking this plan and the drift report. | `dev/reviews/`, `dev/plans/`, optional ADR | — | docs | Readers can trace why recovery work exists and what it is correcting. |
| P7-5 | R6.5 | Archive or annotate superseded sprint/task documents so they are obviously historical. | `dev/plans/`, `dev/tasks/`, `dev/tracking/` | P5-1 | docs | No historical plan appears to be the active execution source by accident. |
| P7-6 | R6.6 | Close the loop with an updated drift/alignment review after Phases R1–R4 land. | `dev/reviews/` | P2-1, P3-1, P4-1, P5-1 | docs | Follow-up review confirms whether the contract was genuinely restored. |

### Cross-phase dependencies

This phase blocks: — (terminal phase).
This phase is blocked by: P2-1, P3-1, P4-1, P5-1 (the four pillars whose acceptance test, governance closure, and split test families this phase verifies).

### Exit criteria

- Stable verification clearly begins from LaTeX input.
- Planning and tracking artifacts reflect reality.
- Recovery progress can be audited without re-reading the whole repo history.

---

## Recommended execution order

The preferred implementation order is:

1. **Phase 1 (R0)** — freeze stable vs experimental contract surface  
2. **Phase 2 (R1)** — restore the frontend as the canonical entry point  
3. **Phase 3 (R2)** — enrich `ProblemIR` compatibly  
4. **Phase 4 (R3)** — enrich `ElementIR` and normalize lowering  
5. **Phase 5 (R4)** — re-anchor Taichi as the stable codegen path  
6. **Phase 6 (R5)** — integrate `algo2code` at the PCG seam  
7. **Phase 7 (R6)** — close the verification/governance loop

If only one near-term code refactor can be funded, it should be:

> **Phase 2 (R1) — restore the frontend contract first**

---

## Suggested PR slices

PR boundaries are tracked per task in `dev/tasks/recovery_plan_latex_contract/json/`; one task = one PR is the default.

---

## Risks and mitigations

| Risk | Why it matters | Mitigation | Affects task(s) |
|---|---|---|---|
| Frontend work balloons into a parser rewrite | Could stall recovery before visible wins | Recover a thin stable subset first; keep local adapter path while formalizing the fork boundary. | P2-1, P2-3, P2-5 |
| IR enrichment breaks downstream code | `ProblemIR`/`ElementIR` are widely consumed | Use additive fields and compatibility constructors; land with focused regression tests. | P3-1, P3-2, P3-3, P4-1, P4-3 |
| Experimental scope keeps leaking back into the stable story | Recreates the same drift under new names | Enforce explicit stable/experimental labeling in docs, examples, and tests. | P1-2, P5-2, P5-5 |
| `algo2code` integration expands too aggressively | Could destabilize solver/runtime work | Limit first integration to PCG behind `LinearSolverInterface`; defer radial return. | P6-1, P6-3 |
| Tracker/doc cleanup lags behind implementation | Future readers lose trust in the plan | Make governance updates part of each recovery phase rather than a final afterthought. | P1-4, P7-4, P7-5 |

---

## Acceptance checklist

- [ ] Stable/experimental boundary declared and visible.
- [ ] Canonical public story starts from LaTeX input.
- [ ] `build_context()` remains supported but secondary.
- [ ] `ProblemIR` enriched compatibly.
- [ ] `ElementIR` enriched compatibly.
- [ ] Taichi-only stable backend policy restored.
- [ ] Experimental backends clearly labeled.
- [ ] One `algo2code` integration point lands behind a stable interface.
- [ ] At least one LaTeX-to-solution test passes.
- [ ] Planning/tracking surfaces reflect actual execution state.

---

## Final note

This is a **recovery** plan, not a reset plan.

The repo already contains substantial value: symbolic models, solver/runtime infrastructure, verification assets, and a working `algo2code` package. The right move is to restore the original contract at the top of the stack, enrich the IRs additively, and reconnect the existing work to that contract.

That is the shortest path back to the design-doc intent without setting fire to code that already earned its keep.
