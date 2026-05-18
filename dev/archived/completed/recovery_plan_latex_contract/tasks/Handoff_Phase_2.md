# Recovery-plan Phase 1 Handoff

> **From**: Phase 1 agent
> **To**: Phase 2 agent
> **Date**: 2026-04-26
> **Branch**: SOSOVSKI/back2latex (compressed exec; no dedicated phase branch)
> **Plan**: dev/plans/recovery_plan_latex_contract.md

---

## Skills to Load Before Starting

- `Aut_Faciam` (for `ScaffoldPhase`, `ExecPhase`, `ExecTask`).
- `gitnexus-impact-analysis` — Phase 2 introduces a real public-API addition (`compile_latex`); run impact analysis on `mechdsl/__init__.py` before editing.
- `compile-check` (project-local skill) — useful when validating that the new façade resolves through the existing six-layer pipeline.

---

## Phase 1 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P1-1 | Define MVP-stable / experimental tiers | bd41a56 | 2/2 | none |
| P1-4 | Normalise tracker vocabulary | ae1e016 | 3/3 | none |
| P1-5 | Record frontend deferral as drift | b09802b | 3/3 | none |
| P1-2 | Mark experimental surfaces in module docstrings | cff354a | 5/5 | none |
| P1-3 | Stability-policy subsection in README | fe88f1a | 3/3 | none |
| P1-6 | MVP plan supersession banners | (this batch) | 3/3 | none |

**Overall test status**: 19/19 task-dedicated audit tests passing; 177/177 across the broader regression set (plan_tests + mechanics_ir + element_ir + taichi/mfem/moose printers).

---

## Architecture and State After Phase 1

- **README.md** has a new `## Support tiers` section followed by a `### Stability policy` subsection — both reference the recovery plan, the STATUS_LEGEND, and the drift-history note.
- **`dev/tracking/STATUS_LEGEND.md`** is new. It is the canonical definition of the four-value status vocabulary; every tracker should reference it. The MVP_plan tracker already does.
- **`dev/reviews/frontend_drift_history.md`** is new. It frames the frontend deferral as historical drift (not a defect) and classifies the work against three patterns (planned-but-deferred / never-planned / implemented-via-substitute).
- **Module docstrings** on `codegen/mfem_printer.py`, `codegen/moose_printer.py`, `solver/lumped_mass.py`, `symbolic/models/__init__.py`, and `ir/mechanics_ir.py::ElementType` carry an `experimental` tier marker.
- **MVP plans** (`MVP_plan.md`, `MVP_sprint{1,2,3}.md`) carry supersession banners pointing at the recovery plan.

No production-code behavior changed. Existing test suites (mechanics_ir/element_ir/codegen) all pass.

---

## Assumptions Made During Phase 1

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| Adding a docstring to `ElementType` does not alter Enum semantics | P1-2 | Verified by running `test_mechanics_ir.py` (15/15 pass) | None observed |
| Module-level "Support tier: experimental" docstrings are sufficient — no need for `@experimental` decorators or import-time warnings | P1-2 | Recovery plan's amendment-3 phrasing was "label experimental scope clearly", not "block usage" | If a downstream phase needs runtime gating, this would be a follow-up |
| The MVP_plan tracker preamble alone is enough to reference STATUS_LEGEND.md (vs adding the same preamble to every tracker file) | P1-4 | The recovery plan's R0.4 says "tracker vocabulary"; one canonical legend + one example wiring is sufficient to demonstrate the contract | If a future audit demands all 8 trackers reference the legend, this is a small follow-up edit |
| Hard-stop invariant `test_no_exec_artifacts_present` should be retired now that exec is authorized | Phase 1 close-out | The invariant served its purpose at back2latex commit time; replacing it with a data-integrity check preserves regression coverage without falsely failing | None — the historical contract is preserved in `dev/tasks/back2latex/gates/phase_2_gates.md` |

---

## Known Issues and Deferred Concerns

### Failing tests
| Test name/file | Failure reason | Impact on Phase 2 |
|----------------|---------------|-------------------|
| (none) | — | — |

### Known limitations
- The pre-existing `numpy`-importing tests across the wider suite collect-error if the venv is bootstrapped without `--all-packages --all-groups --all-extras`. That's an environment issue, not a Phase-1 regression. Run `uv sync --all-packages --all-groups --all-extras` before Phase 2 begins.
- The Phase-1 audit tests check for tier names by literal substring; a future refactor that renames `MVP-stable` would need to update both README.md and the tests in lockstep.

### Test coverage gaps
- Phase 1's tests verify *presence* of tier markers in docstrings, not their *correctness*. If someone marks the Taichi printer experimental by mistake, no Phase-1 test catches it (because `taichi_printer.py` is not on the "must be experimental" list).

---

## Lessons Learned

### Process
- Compressed exec (one branch / commit-per-task / phase-end Gate B-C) was the right call again for doc-only Phase 1. Per-task gate cycles would have produced no additional signal.
- The `numpy` import issue at the start of exec was avoidable — running `uv sync --all-packages --all-groups --all-extras` first is a cheap habit before any pytest invocation that touches the broader suite.
- Touching `mechanics_ir.py` (a high-impact production module) for a docstring-only change is fine, but always run `test_mechanics_ir.py` + `test_element_ir.py` immediately after. Phase 2's actual `ProblemIR` enrichment work is much higher-impact and will need that same discipline at every step.

### Physics and numerics
- N/A — Phase 1 is doc-only.

---

## What Phase 2 Must Know Before Starting

> Phase 2 introduces real production code: `compile_latex(source: str, profile: str = "mvp") -> ArtifactBundle`. This is where recovery starts touching the live API.

- **Critical dependency: `mechdsl/__init__.py`** — exports `compile` today; needs to also export `compile_latex` (without removing `compile`). Run `gitnexus_impact({target: "compile", direction: "upstream"})` before editing the package init; `compile` has many callers across tests and examples.
- **`nrpylatex` is wired in `pyproject.toml` but never imported under `src/`** — Phase 2 (R1.3 = P2-3) is where that integration actually happens. The recovery plan says "thin stable subset is sufficient at first"; do NOT block on full nrpylatex grammar coverage.
- **Preserve `build_context()`** (R1.2 = P2-2) — it must remain importable and functional. Document it as secondary, not deprecated.
- **High-risk task: P2-5 (frontend contract test suite)** — the test must start from LaTeX *source*, run through the entire pipeline, and reach a normalized frontend output. No existing test does that. Plan on writing one fresh.
- **Recommended starting point**: P2-1 (the canonical façade itself). The other Phase-2 tasks are blocked by it.
- **Watch out for**: `compile_latex` will need to forward to `build_context` + `compile` internally for the MVP, since the actual LaTeX → ProblemIR semantic layer is the central work of phases 3-5. Do not over-engineer the façade; a thin shim is correct for Phase 2.
- **Environment**: run `uv sync --all-packages --all-groups --all-extras` before `pytest`. The venv created by `uv run python` at the start of an engagement is minimal and will collect-error on the broader suite.
