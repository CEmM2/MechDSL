# Plan — Make `recovery_plan_latex_contract.md` Aut_Faciam-ingestible

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This document was the bootstrap plan that re-shaped the recovery plan for Aut_Faciam ingestion; that work is complete and the recovery plan itself is now the active execution source. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

## Context

`dev/reviews/drift_20_04.md` documents a critical drift: the original LaTeX-first compiler contract was deferred during MVP execution and the bypass hardened into the actual architecture. `dev/plans/recovery_plan_latex_contract.md` is the proposed recovery — phases R0..R6, additive refactors, preserve working assets.

**The user wants to drive recovery execution through the `Aut_Faciam` skill** (Plan-2-Tasks → ScaffoldPhase → ExecPhase). The recovery plan is excellent prose but is **not yet shaped for Plan-2-Tasks ingestion**. Three structural mismatches must be fixed before `/Aut_Faciam tasks dev/plans/recovery_plan_latex_contract.md` will produce useful task JSONs:

1. **Phase IDs** — Aut_Faciam mandates **sequential integers from 1** (`Plan-2-Tasks.md:24`); the plan uses `R0..R6`. Plan-2-Tasks would auto-remap, but mappings drive every downstream artifact (`phase-2` GitHub label, `Phase_2_context_summary.md`, `phase_2_gates.md`, branch `<plan>_phase-2`). Without an explicit mapping in the plan, the R-label and the integer drift apart.
2. **Task IDs** — Aut_Faciam mandates **`P<phase>-<seq>`** (`Plan-2-Tasks.md:26`); the plan uses `R0.1, R1.1, ...`. Same risk: implicit remap, ambiguous tracker rows.
3. **Per-task structure** — Plan-2-Tasks owns `objective, scope, implementation_steps, deliverables, acceptance_criteria, blocked_by, blocks, risks, test_plan.tier, test_plan.cases` (`Plan-2-Tasks.md:46-54`). The current plan's per-task surface is "Action item / Files / Verification" — Plan-2-Tasks can derive most fields from prose, but explicit `blocked_by`/`blocks` edges and a `test_plan.tier` per task massively reduce decomposition error.

Two **content-level gaps** also surfaced from the code audit and should be folded in before tasks are generated, otherwise Plan-2-Tasks will commit to acceptance criteria that current code can't trivially satisfy:

- **`ProblemIR` has no `to_dict()/from_dict()` today** (only `BoundaryCondition` and `MaterialSpec` do — `mechanics_ir.py:124-168`). Phase R2 task R2.1 references "serialization round-trip tests" — that infra must be built as part of R2.1, not assumed.
- **`mechdsl/__init__.py` exports only `compile`** (from codegen). R1.1 needs to export `compile_latex` from the package root, not from `frontend/__init__.py` — small but easy to miss.

The expected outcome is a **single edit pass on `dev/plans/recovery_plan_latex_contract.md`** that makes it Plan-2-Tasks-ingestible without losing the careful prose, plus a couple of governance touches that the recovery plan already promised but didn't execute on its own surface.

---

## Phase 0 — Branch rename (do first, before any edits)

The system instruction requires renaming the working branch via `git branch -m` with `SOSOVSKI/` prefix and a concrete name <30 chars.

Proposed name: **`SOSOVSKI/latex-recovery-plan`** (24 chars, concrete, scoped to this work).

```
git branch -m SOSOVSKI/latex-recovery-plan
```

---

## Goal

Produce a single recovery plan file that, when fed to `/Aut_Faciam tasks`, yields:

- 7 phase context files (`Phase_1_context_summary.md` … `Phase_7_context_summary.md`)
- ~30 task JSONs in `dev/tasks/recovery_plan_latex_contract/json/`
- A tracker at `dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`
- A `github_issue_map.json` and 1 plan-overview + 7 phase-skeleton GitHub issues

…with **zero structural ambiguity** about which R-label maps to which integer phase, which prior task each task blocks, and what the test tier is.

---

## Amendments to `dev/plans/recovery_plan_latex_contract.md`

All edits are to that file. Line numbers below reference the **current** file.

### Amendment 1 — Phase number reconciliation table (insert near top)

**Where:** Insert a new section between line 79 (end of "Planning assumptions") and line 81 (start of `## Phase R0`).

**Why:** Pin `R0..R6` ↔ `Phase 1..7` explicitly so Plan-2-Tasks doesn't have to guess and so future readers see both labels.

**New section (verbatim to insert):**

```markdown
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
```

### Amendment 2 — Phase headings keep both labels

**Edits:**

- Line 81: `## Phase R0 — Freeze the contract surface` → `## Phase 1 — Freeze the contract surface (R0)`
- Line 105: `## Phase R1 — Restore the frontend as the canonical entry point` → `## Phase 2 — Restore the frontend as the canonical entry point (R1)`
- Line 136: `## Phase R2 — Enrich \`ProblemIR\` into the semantic center again` → `## Phase 3 — Enrich \`ProblemIR\` into the semantic center again (R2)`
- Line 166: `## Phase R3 — Enrich \`ElementIR\` and normalize lowering boundaries` → `## Phase 4 — Enrich \`ElementIR\` and normalize lowering boundaries (R3)`
- Line 196: `## Phase R4 — Re-anchor Taichi codegen as the stable path` → `## Phase 5 — Re-anchor Taichi codegen as the stable path (R4)`
- Line 226: `## Phase R5 — Integrate \`algo2code\` at the least risky seam` → `## Phase 6 — Integrate \`algo2code\` at the least risky seam (R5)`
- Line 256: `## Phase R6 — Verification, governance, and closure` → `## Phase 7 — Verification, governance, and closure (R6)`

### Amendment 3 — Action-item tables: add `Task ID`, `Blocked by`, `Tier` columns

**Why:** Plan-2-Tasks reads action-item tables as the primary task source. Adding three columns up front is what eliminates the most decomposition guesswork. Keep the existing `#` column as the legacy R-label.

**New table header (use everywhere an action-item table appears):**

```markdown
| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |
|---------|-----------|-------------|-------------------|------------|------|--------------|
```

Concretely, for each phase, every existing row gets:

- `Task ID` filled with `P<phase>-<seq>` (sequential within phase, starting at 1)
- `Legacy ID` filled with the existing `R0.1` etc.
- `Blocked by` filled with the canonical IDs of any prerequisite tasks (use `—` for none)
- `Tier` filled with one of `unit | integration | regression | docs | manual` (most R0 rows are `docs`; R1.5/R1.6, R2.1, R2.5, R3.1, R3.4, R5.1, R5.3, R6.1, R6.2 are `integration` or `regression`)

The mapping is straightforward — Phase R0 rows R0.1..R0.5 become P1-1..P1-5, and so on. **For cross-phase blockers, use the canonical ID** (e.g. P3-2 in Phase 3 lists `P2-1` as `Blocked by` because the canonical `compile_latex` façade must exist before IR enrichment is wired through it).

### Amendment 4 — Insert a "Code reality anchor" block per phase

**Why:** The `Action item` column tells Plan-2-Tasks *what* to do; the `Files / surfaces` column tells it *where*. But the recovery prose doesn't pin to current symbols — `ProblemIR` field list, `compile` already exported from `mechdsl/__init__.py`, `LinearSolverInterface` protocol shape, etc. Adding a short **Code reality anchor** subsection per phase prevents tasks from being authored against a stale mental model.

**Insertion point:** Right after each `**Why <…>:**` line and before the `### Action items` heading, insert:

```markdown
### Code reality anchor (2026-04-26)

- <bullet 1: current state of the primary surface this phase touches, with file:line>
- <bullet 2: what already partially satisfies the phase>
- <bullet 3: the specific mismatch this phase corrects>
```

Concrete content per phase:

- **Phase 1 (R0):** `dev/tracking/tasks-tracker_MVP_plan.md` rows are all `not_started`; only two status values exist in practice. `dev/plans/` has 13 plans, `dev/tracking/` has 8 trackers, with no explicit "active vs archived" marker.
- **Phase 2 (R1):** `mechdsl/__init__.py:7` exports only `compile` (from `codegen`). `frontend/__init__.py` exports `build_context`, `parse`, `parse_file`. `parser.py:11-17` explicitly defers nrpylatex math grammar to Plan B. `tests/test_frontend.py` is a stub. `nrpylatex` is in `pyproject.toml` but never imported under `src/`.
- **Phase 3 (R2):** `ir/mechanics_ir.py:113` `@dataclass(frozen=True)`; existing `ProblemIR` fields are listed at `mechanics_ir.py:210-219`. `BoundaryCondition.to_dict/from_dict` exist (`:124-145`); `MaterialSpec.to_dict/from_dict` exist (`:155-168`). **`ProblemIR` itself has no `to_dict/from_dict`** — task R2.1's "round-trip tests" requires building this method first.
- **Phase 4 (R3):** `ir/element_ir.py:35-89` carries basis/quadrature/integration metadata. `lowering/fe_localise.py:35-66` defines `EinsumSpec` and `LocalisationResult`. Both are frozen dataclasses.
- **Phase 5 (R4):** `codegen/__init__.py:10-20` exposes `compile(problem_ir) -> ArtifactBundle`. `taichi_printer.py:20-80` uses an `EmissionContext` class — no module-level `emit*` functions today, contrary to the drift report's wording. `mfem_printer.py` and `moose_printer.py` exist; nothing currently labels them experimental in code or docs.
- **Phase 6 (R5):** `solver/import_adapter.py:26-57` defines `LinearSolverInterface` (Protocol) plus `CGSolver`, `PCGSolver`. **No `algo2code` imports anywhere under `packages/mechdsl-core/src/`** — confirmed by grep.
- **Phase 7 (R6):** `tests/test_e2e.py:1-80` constructs `ProblemIR` directly via `_make_elastic_problem_ir()`; no test starts from a LaTeX string anywhere in the suite.

### Amendment 5 — Add explicit task dependency edges

The `Blocked by` column from Amendment 3 covers most of this, but call out the cross-phase edges explicitly so Plan-2-Tasks does not need to infer them. Add a small paragraph at the end of each phase, before "Exit criteria":

```markdown
### Cross-phase dependencies

This phase blocks: <list canonical IDs>.
This phase is blocked by: <list canonical IDs>.
```

Concrete edges (the only ones that matter for unblocking logic):

- Phase 2 (R1) blocks: P3-1, P3-2, P5-4 (codegen consuming enriched IR via canonical façade), P7-2 (LaTeX→solution acceptance test).
- Phase 3 (R2) blocks: P4-1, P4-3, P5-4.
- Phase 4 (R3) blocks: P5-4, P7-2.
- Phase 5 (R4) blocks: P7-2, P7-5.
- Phase 6 (R5) blocks: nothing in the stable path; can run concurrently with Phase 5 if Phase 4 has landed.
- Phase 1 (R0) blocks every other phase only weakly — its outputs are docs/tracker, not code.

### Amendment 6 — Risk → task association

The plan's "Risks and mitigations" section (lines 339-348) is excellent but un-anchored to tasks. Plan-2-Tasks specifically looks for risk attribution (`Plan-2-Tasks.md:52`). Edit the table to add a `Affects task(s)` column:

| Risk | Why it matters | Mitigation | Affects task(s) |

Concrete attribution:
- "Frontend work balloons into parser rewrite" → P2-1, P2-3, P2-5
- "IR enrichment breaks downstream code" → P3-1, P3-2, P3-3, P4-1, P4-3
- "Experimental scope keeps leaking back into the stable story" → P1-2, P5-2, P5-5
- "`algo2code` integration expands too aggressively" → P6-1, P6-3
- "Tracker/doc cleanup lags behind implementation" → P1-4, P7-4, P7-5

### Amendment 7 — Reconcile prior plans (the R0 commitment)

R0.5 says "Record the frontend deferral explicitly as historical execution drift." The plan should itself enact the supersession. Add to **Phase 1 (R0)** action items, as a new task **P1-6**:

- **P1-6 (new):** "Mark `dev/plans/MVP_plan.md` and `dev/plans/MVP_sprint{1,2,3}.md` as superseded by this recovery plan for the frontend contract; add a banner pointing here and an explicit `superseded` tag in their front matter (or the first H1)."
  - Files / surfaces: `dev/plans/MVP_plan.md`, `dev/plans/MVP_sprint1.md`, `dev/plans/MVP_sprint2.md`, `dev/plans/MVP_sprint3.md`
  - Tier: `docs`
  - Verification: each superseded plan has a top banner; tracker rows for old P2.1..P2.5 carry `implemented-via-substitute` (not `not_started`).
  - Blocked by: P1-4 (vocabulary expansion must land first so `implemented-via-substitute` is a legal status).

### Amendment 8 — Drop or fold the "Suggested PR slices" section

The current section (lines 299-335) interleaves phases (PR-2 = R1.1-R1.3, PR-3 = R1.5-R1.6) which Plan-2-Tasks would treat as competing decompositions. Replace it with a single sentence: "PR boundaries are tracked per task in `dev/tasks/recovery_plan_latex_contract/json/`; one task = one PR is the default." Or delete the section outright. Either is fine; the PR slicing is downstream of task decomposition.

### Amendment 9 — Update success criteria checklist to use canonical IDs

Lines 56-69's checklist is fine as written. Add one row at the bottom:

- [ ] All canonical task IDs in `dev/tasks/recovery_plan_latex_contract/json/` reach `done` status, with their corresponding GitHub issues closed.

---

## Critical files (read-only references for execution)

| File | Why |
|------|-----|
| `dev/plans/recovery_plan_latex_contract.md` | The single file edited by this plan |
| `dev/reviews/drift_20_04.md` | Source of truth for R-label semantics; do not modify |
| `dev/design_docs/00-OVERVIEW.md` … `11-ALGO2CODE.md` | Intent baseline; informs acceptance criteria |
| `.claude/skills/Aut_Faciam/commands/Plan-2-Tasks.md` | Defines required plan shape (especially lines 24, 26, 46-54) |
| `.claude/skills/Aut_Faciam/templates/template.json` | Task JSON schema |
| `packages/mechdsl-core/src/mechdsl/__init__.py` | Where `compile_latex` will live (Phase 2) |
| `packages/mechdsl-core/src/mechdsl/frontend/parser.py` | Bespoke parser to demote |
| `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` | `ProblemIR` enrichment target |
| `packages/mechdsl-core/src/mechdsl/ir/element_ir.py` | `ElementIR` enrichment target |
| `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py` | `EinsumSpec` / `LocalisationResult` demotion target |
| `packages/mechdsl-core/src/mechdsl/codegen/{taichi,mfem,moose}_printer.py` | Stable/experimental boundary |
| `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py` | `LinearSolverInterface` integration seam |

---

## Verification

End-to-end check after the amendments land. Each step is the user's command (no automation needed):

1. **Skim verification** — open `dev/plans/recovery_plan_latex_contract.md` and confirm:
   - Phase ID mapping table is present.
   - Each `## Phase N — ... (RX)` heading is sequential 1..7.
   - Every action-item table has `Task ID | Legacy ID | ... | Blocked by | Tier | Verification` columns.
   - Each phase has a "Code reality anchor (2026-04-26)" subsection.
   - Each phase has a "Cross-phase dependencies" block.
   - Risks table has an `Affects task(s)` column.
   - Phase 1 has 6 tasks (P1-1..P1-6); P1-6 supersedes prior plans.

2. **Decompose with Aut_Faciam:**
   ```
   /Aut_Faciam tasks dev/plans/recovery_plan_latex_contract.md
   ```
   Expected outputs:
   - `dev/tasks/recovery_plan_latex_contract/all-tasks.md` with ~30 rows, no circular dependencies.
   - `dev/tasks/recovery_plan_latex_contract/json/P1-1.json` … `P7-N.json`, each with non-empty `objective`, `scope`, `acceptance_criteria`, and `test_plan.tier`.
   - `dev/tasks/recovery_plan_latex_contract/Phase_1_context_summary.md` … `Phase_7_context_summary.md`.
   - `dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`.
   - GitHub: 1 plan-overview issue + 7 phase-skeleton issues with labels `plan:recovery-plan-latex-contract`, `phase-N`, `not-scaffolded`.
   - `dev/tasks/recovery_plan_latex_contract/github_issue_map.json` populated.

3. **Spot-check three task JSONs:**
   - `P1-4.json` — must include the four-value status vocabulary (`done`, `deferred`, `implemented-via-substitute`, `not_started`) in `implementation_steps` or `acceptance_criteria`.
   - `P2-1.json` — must list `mechdsl/__init__.py` and `frontend/__init__.py` in `deliverables`; `acceptance_criteria` must mention LaTeX-string entry test.
   - `P3-1.json` — must list `mechdsl/ir/mechanics_ir.py` in `deliverables`; `implementation_steps` must include adding `to_dict()`/`from_dict()` to `ProblemIR` itself (not just sub-objects).

4. **Scaffold Phase 1 to validate the loop closes:**
   ```
   /Aut_Faciam scaffold 1
   ```
   Expected: `dev/tasks/recovery_plan_latex_contract/gates/phase_1_gates.md` created; phase-1 GitHub issue body populated; task issues for P1-1..P1-6 created and labeled `task-issue, phase-1, not-scaffolded`.

5. **Stop after scaffold.** Do not run `/Aut_Faciam exec 1` in this work session — that's a follow-up engagement once the user reviews the scaffolded tasks.

---

## Out of scope

- Editing `dev/design_docs/*` (the recovery plan itself promises not to in its non-goals).
- Any code edits in `packages/mechdsl-core/` or `packages/algo2code/` — those are downstream of `/Aut_Faciam exec`.
- Creating PRs, force-pushing, or modifying `MVP_plan.md` content beyond the supersession banner specified in P1-6.
- Re-running `/ultrareview`.

---

## Risk for this plan itself

| Risk | Mitigation |
|------|------------|
| The amended plan still contains R0/R0.1 references in places I missed, confusing Plan-2-Tasks | Verification step 1 explicitly checks the headings and table columns; a final `grep -n "R[0-6]\\." dev/plans/recovery_plan_latex_contract.md` should only return rows in the `Legacy ID` column |
| GitHub issue creation will fail without `gh auth status` | Plan-2-Tasks is documented to skip GH integration cleanly if `gh` is unauthenticated and to emit local artifacts anyway (`Plan-2-Tasks.md:77`); user can re-run later to backfill |
| Plan-2-Tasks generates fewer or more tasks than expected (~30) | The action-item count is fixed by the plan's own tables; if Plan-2-Tasks decomposes further, the dependency edges in Amendment 5 should still be valid because they reference the *task-level* IDs declared here, not sub-decompositions |
