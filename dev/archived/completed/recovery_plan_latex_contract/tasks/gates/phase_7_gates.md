# Phase 7 — Gate History

Plan: `dev/plans/recovery_plan_latex_contract.md`
Phase: 7 — Verification, governance, and closure (R6)
Branch: `SOSOVSKI/recovery-phase7`
Started: 2026-04-29

## Failure modes encountered (during execution)

(none yet)

---

## Tasks

## P7-4: Add a short architecture decision or recovery-status note cross-linking this plan and the drift report.

**Issue:** #194
**Started:** 2026-04-29
**Completed:** in progress
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `77e1498` (scaffold commit)
**Implementation SHA:** `0251afb`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `0251afb` independently: 4 files touched (new `dev/reviews/recovery_status_2026_04.md`, plan back-link line, fleshed-out `test_p7_4.py`, gate boilerplate). All bidirectional cross-link legs present (plan→note, note→plan, note→drift). New note narrates the why with R0–R6 phase status table; stays in spec surfaces. Fresh `uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_4.py -v` returned 2/2 pass. No scope creep into design docs, source, or unrelated plan_tests.

One minor finding (`test_gap`, severity minor): `_candidate_note_paths()` in `test_p7_4.py:37-60` matches both `frontend_drift_history.md` (P1-5 artifact) and `recovery_status_2026_04.md`. Test 1 inspects `notes[0]` only, so it would pass even if the new note were deleted, as long as `frontend_drift_history.md` survives. Test 2's plan-back-reference predicate provides the strict deletion guard (the recovery plan references only the new note), so the combined suite still fails correctly on accidental deletion. Not blocking; suggested fix is a 3-line change in test 1 to iterate `notes` for the one referenced by the plan.

**Resolution:** none required — minor only, combined-suite invariant holds. Logged for future reference.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T17:55", "minor_findings": ["test_gap: test_p7_4.py:92 inspects notes[0] only; combined invariant via test 2 still holds"]}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 9/10)

Reviewer (`pr-review-toolkit:code-reviewer`) verified design-doc alignment (zero `dev/design_docs/` changes), convention adherence (note mirrors `frontend_drift_history.md` voice and structure), all four cross-link legs (plan→note, note→plan, note→drift, note→companion), R0–R6 status accuracy against tracker + issue map, test durability (assertions catch deletion + content drift), no source code regressions, and Phase 5 lessons respected (no autoflake / hard-coded line whitelists).

**Issue counts:** minor=1, medium=0, high=0, critical=0.

**Minor finding (style_violation, cosmetic):** `dev/reviews/recovery_status_2026_04.md:33` heading read "Recovery phase status (R1 → R6)" but the table starts at R0. Triaged fix-now per Phase 5 lesson.

**Resolution:** heading corrected to "(R0 → R6)" in commit `4ec24a8`. Tests re-run on patched HEAD: 2/2 pass.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:00", "review_score": 9, "issue_counts": {"minor": 1, "medium": 0, "high": 0, "critical": 0}, "resolution_commit": "4ec24a8"}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `4ec24a8`:

```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_4.py -v
============================== 2 passed in 0.02s ===============================
```

Evidence: 2/2 task-relevant tests pass (100%). Both acceptance cases (`P7-4-c1: cross-link note exists and references plan + drift`, `P7-4-c2: deliverables present at surfaces`) covered.

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:01", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "4ec24a8"}
```

**Completed:** 2026-04-29
**Final commits:** `0251afb` (implementation), `4ec24a8` (Gate B heading fix).

---

## P7-3: Update examples so the stable story begins from LaTeX input.

**Issue:** #193
**Started:** 2026-04-29
**Completed:** in progress
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `44db219` (post-P7-4 close)
**Implementation SHA:** `0f37b30`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `0f37b30` independently: 4 files touched (`README.md`, `dev/examples/README.md`, new `dev/examples/run_compile_latex.py` 41 lines, `test_p7_3.py` flesh-out). README ordering verified live: `compile_latex(` precedes both `build_context(` and `ProblemIR(`. New script runs end-to-end via `uv run python dev/examples/run_compile_latex.py`, embeds a `% mechanics` LaTeX block, calls `compile_latex(source, profile="mvp")`. P2-2 mandate satisfied — programmatic API preserved, only relabeled. Fresh `uv run pytest .../test_p7_3.py -v` returns 2/2 pass. No source / design-doc / plan / task / tracker / review changes.

**Issues:** minor=2, medium=0, high=0, critical=0.

Minor findings:
1. Implementer's reported byte offsets (build_context 2421, ProblemIR 3226) are stale; live values are 2593 and 3398. Ordering invariant still holds — informational.
2. `test_first_run_example_in_readme_uses_canonical_path` uses first-occurrence textual ordering; a future contributor could in principle satisfy it via a passing prose mention while keeping a programmatic example as the first runnable block. Inherent docs-tier weakness, acceptable for tier.

**Resolution:** none required.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:30", "minor_findings": ["stale offsets in implementer report", "test_p7_3.py:50 first-occurrence ordering check is loose"]}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 9/10)

Reviewer (`pr-review-toolkit:code-reviewer`) confirmed: canonical compile_latex run produces real Taichi-shape ArtifactBundle (n_dof=24, voigt_size=6, formulation=total_lagrangian); README Quickstart leads with LaTeX-first at `README.md:40` and demotes programmatic API at `README.md:72`; P2-2 mandate satisfied (build_context/ProblemIR snippets still appear, just demoted); `dev/examples/README.md` restructured into "Canonical first-run example (LaTeX-first)" section + "Programmatic API examples (advanced / testing aids)"; test uses `text.find()` with rule-ID assertion messages (no hard-coded line numbers); src/ diff empty.

**Issue counts:** minor=0, medium=0, high=0, critical=0.

**Resolution:** none required.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:35", "review_score": 9, "issue_counts": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `233e441`:
```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_3.py -v -p no:cacheprovider
test_p7_3.py::TestP7_3::test_first_run_example_in_readme_uses_canonical_path PASSED
test_p7_3.py::TestP7_3::test_deliverables_present_at_surfaces PASSED
2/2 passed.
```

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:36", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "0f37b30"}
```

**Completed:** 2026-04-29
**Final commit:** `0f37b30`.

---

## P7-5: Archive or annotate superseded sprint/task documents.

**Issue:** #195
**Started:** 2026-04-29
**Completed:** in progress
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `44db219` (post-P7-4 close)
**Implementation SHA:** `b79ce6d`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `b79ce6d` independently: 25 files touched (8 plans banner'd, 8 task `_SUPERSEDED.md` markers added, 8 trackers banner'd, `test_p7_5.py` flesh-out). Banner format mirrors P1-6's `> ⚠️ **Superseded ...` pattern across all touched files. No deletions (`git show --stat` shows no `D` lines). Active set untouched: `recovery_plan_latex_contract.md`, its task folder, its tracker. Allowlist (`STATUS_LEGEND.md`, `verification_matrix.md`) is justified — vocabulary references, not plan execution sources. Test is content-based and would fail on accidental banner removal. Fresh 2/2 pass.

**Issues:** minor=0, medium=0, high=0, critical=0. One stylistic note: `sprint{2,3}.md` use unqualified "Superseded" while `MVP_plan.md` uses "Superseded for the frontend contract"; both forms appear in P1-6's own output (`MVP_plan.md` scoped vs `MVP_sprint{2,3}.md` unqualified), so this matches precedent rather than violating it.

**Resolution:** none required.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:30"}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 10/10)

Reviewer (`pr-review-toolkit:code-reviewer`) confirmed: all 8 plan banners + 8 task `_SUPERSEDED.md` markers + 8 tracker banners follow P1-6 convention exactly; `dev/tasks/PLAN-B/_SUPERSEDED.md` correctly distinguishes "execution source superseded" from "work landed in tree" (Phase 6 handoff preservation); allowlist (`STATUS_LEGEND.md`, `verification_matrix.md`) is justified — `STATUS_LEGEND.md` is canonical status-enum vocabulary, `verification_matrix.md` is test-ID → file mapping (spec §2); `dev/plans/reviews/` subfolder correctly excluded by `is_file()` filter; future-active safety verified — new plans without banner or `ACTIVE_PLAN_STEMS` entry will trigger helpful failure; no deletions; no src/ touches; idempotent (2/2 pass).

**Issue counts:** minor=0, medium=0, high=0, critical=0.

**Resolution:** none required.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:35", "review_score": 10, "issue_counts": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `233e441`:
```
test_p7_5.py::TestP7_5::test_no_historical_plan_appears_active_by_accident PASSED
test_p7_5.py::TestP7_5::test_deliverables_present_at_surfaces PASSED
2/2 passed.
```

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:36", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "b79ce6d"}
```

**Completed:** 2026-04-29
**Final commit:** `b79ce6d`.

---

## P7-6: Closing drift/alignment review after Phases R1–R4 land.

**Issue:** #196
**Started:** 2026-04-29
**Completed:** in progress
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `44db219` (post-P7-4 close, pre-parallel-batch)
**Implementation SHA:** `233e441`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `233e441` independently: 2 files touched (new `dev/reviews/drift_post_recovery_2026_04.md` 343 lines, `test_p7_6.py` flesh-out). All four pillars (R1, R2, R3, R4) carry explicit `**Verdict:** **RESTORED**` lines. Sign-off section reconciles all 9 success-criteria bullets (7 met, 2 partial), exceeding the test's "5 of 9" floor. References both `drift_20_04.md` and `recovery_plan_latex_contract.md`. Spot-checks: `mechdsl/__init__.py` exports `compile_latex` (R1 evidence); `codegen/_experimental.py` defines `ExperimentalBackendWarning` and `__experimental__` markers exist on MFEM/MOOSE printers (R4 evidence). No source / design-doc / sibling-review changes.

**Issues:** minor=1, medium=0, high=0, critical=0.

Minor finding: review lists P7-3 and P7-5 as pending (lines ~240-242). Both landed in parallel commits `0f37b30` and `b79ce6d` BEFORE HEAD `233e441` — but the review was authored against base `44db219` and honestly states its base commit at line 6. Per task spec this is informational-only `misunderstanding`-class; the review's verdicts on R1–R4 are not affected. Length 343 lines, slightly above the 100–250 hint but justified by per-pillar evidence + 9-bullet sign-off (both test-required).

**Resolution:** none required — review correctly states its authoring base; closure verdicts are accurate.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:30", "minor_findings": ["review's pending-list reflects base commit 44db219, not HEAD 233e441 — review is honest about its authoring base"]}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 9/10)

Reviewer (`pr-review-toolkit:code-reviewer`) confirmed: all four pillar verdicts substantiated by source line citations (R1: `mechdsl/__init__.py:33` `compile_latex` + `ALLOWED_PROFILES` gate; R2: `ir/mechanics_ir.py:506-509` four enrichment fields; R3: `ir/element_ir.py:393-396` execution-contract sub-objects + cross-validation at `:437-470`; R4: `_experimental.py` + `__experimental__` markers on MFEM/MOOSE printers); sign-off enumerates all 9 plan criteria with explicit met/partial/pending status (review lines 232-265); cross-link integrity (review references `drift_20_04.md`, `recovery_plan_latex_contract.md`, `recovery_status_2026_04.md`); distinct from P7-4 (60-line pointer vs 343-line per-pillar verdict); no source / design-doc / `drift_20_04.md` edits; test_p7_6.py section bounding makes verdict regex non-circumventable (one global RESTORED + four empty pillar headings would fail); tone consistent with companion reviews.

**Issue counts:** minor=0, medium=0, high=0, critical=0.

**Resolution:** none required.

**Optional (not pursued):** Could trim 50-80 lines by merging per-pillar evidence sub-bullets into denser prose, but current length justified by evidence density.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:35", "review_score": 9, "issue_counts": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `233e441`:
```
test_p7_6.py::TestP7_6::test_follow_up_review_confirms_contract_status PASSED
test_p7_6.py::TestP7_6::test_deliverables_present_at_surfaces PASSED
2/2 passed.
```

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T18:36", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "233e441"}
```

**Completed:** 2026-04-29
**Final commit:** `233e441`.

---

## P7-1: Split end-to-end tests into `from_latex` and `from_problem_ir` families.

**Issue:** #191
**Started:** 2026-04-29
**Completed:** 2026-04-29
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `f244690` (post-P7-3/5/6 closure)
**Implementation SHA:** `c711eed`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `c711eed` independently: 7 files touched (`pyproject.toml` markers + 5 e2e modules + `test_p7_1.py` flesh-out). `pytest -m from_problem_ir` collects 35/1847; `pytest -m from_latex` collects 0 (intentional, P7-2 adds first); `pytest -m e2e` preserved at 53 (list-form pytestmark works). All 5 reclassified files genuinely construct ProblemIR programmatically. Subprocess collect-only invocation in test is genuine. No source / design-doc / plan / task / tracker / review changes.

**Issue counts:** minor=0, medium=0, high=0, critical=0.

**Resolution:** none required.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T19:30"}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 10/10)

Reviewer (`pr-review-toolkit:code-reviewer`) verified: e2e collection unchanged at 53 pre/post P7-1 (list-form pytestmark preserves selection); `pytest` now consumed by `pytestmark` in `test_compile_pipeline.py:26` (autoflake-safe per P5 lesson); marker semantics documented in `test_p7_1.py:23-33`; subprocess harness uses `sys.executable -m pytest` with `-p no:cacheprovider` and `cwd=_REPO_ROOT`; exit-code-5 handled by stdout parsing; pyproject.toml marker descriptions follow `"<name>: <description>"` convention shared with `stable_backend`/`experimental_backend`; Phase-6 exit sentinel `test_phase6_exit.py` 9/9 pass (line whitelists untouched); source tree untouched.

**Issue counts:** minor=0, medium=0, high=0, critical=0.

**Resolution:** none required.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T19:35", "review_score": 10, "issue_counts": {"minor": 0, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `c711eed`:
```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_1.py -v -p no:cacheprovider
test_p7_1.py::TestP7_1::test_ci_test_selection_exposes_from_latex_family PASSED
test_p7_1.py::TestP7_1::test_deliverables_present_at_surfaces PASSED
2/2 passed.
```

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-29T19:36", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "c711eed"}
```

**Final commit:** `c711eed`.

---

## P7-2: Add at least one canonical LaTeX-to-solution acceptance test on the MVP-stable path.

**Issue:** #192
**Started:** 2026-04-29
**Completed:** 2026-04-29
**Branch:** `SOSOVSKI/recovery-phase7`
**Base SHA:** `e516bef` (post-P7-1 closure)
**Implementation SHA:** `c7964ce`

### Gate A — Spec Compliance

#### Attempt 1 — PASS

Reviewer read commit `c7964ce` independently: single file modified (`test_p7_2.py`). Module-level `pytestmark = pytest.mark.from_latex` anchors the previously-empty marker family P7-1 registered (was 0; now 2 collected). Test traverses canonical LaTeX → `compile_latex(..., profile="mvp")` → emitted Taichi module → `mod.newton_solve(LAM, MU, bc_dofs=...)` → reference compare via `tests.ref.ref_hex8_elastic.solve_elastic` within `1e-10` (07-CONVENTIONS §6). Stacked markers `slow + e2e + integration` correct per `.claude/rules/tests.md`. No source / design-doc / plan / task / tracker / review changes.

**Issue counts:** minor=1, medium=0, high=0, critical=0.

**Minor finding (informational):** LaTeX traction string `"0 0 -1000"` does NOT flow into emitted `f_ext`; numeric `f_ext` is injected directly. Documented in test comments at `test_p7_2.py:142-144` ("placeholder for symbolic binding; numeric f_ext provided here as the contract expects"). Canonical compile+solve path validated end-to-end; boundary-directive-to-emitted-code flow not exercised — out of MVP P2-1 façade scope.

**Resolution:** none required. Gap honestly documented; future-phase candidate.

```json
{"gate": "A", "attempt": 1, "result": "pass", "timestamp": "2026-04-30T07:25", "minor_findings": ["LaTeX traction string '0 0 -1000' does not flow into emitted f_ext; documented at test_p7_2.py:142-144"]}
```

### Gate B — Domain Quality

#### Attempt 1 — APPROVE (score 9/10)

Reviewer (`pr-review-toolkit:code-reviewer`) verified: source diff empty (no `packages/mechdsl-core/src/` touches); `from_problem_ir` family unchanged at 35 (P7-1 preservation); `from_latex` collects 2 (anchored by this test); markers registered in `pyproject.toml:56-57`; tolerance `1e-10` correctly cited per `07-CONVENTIONS.md §6` + `tests.md`; Newton-sanity guards at `test_p7_2.py:162-165` (`n_iters >= 1 AND max|u_gen| > 1e-10`) prevent false-pass; LAM/MU formulas match `test_e2e_taichi.py:45-46` exactly; module-level `pytestmark = pytest.mark.from_latex` + per-test `@slow + @e2e + @integration` stacks correctly without duplication; self-witness uses file text reads, no hard-coded line numbers.

**Issue counts:** minor=2, medium=0, high=0, critical=0.

**Minor findings (informational):**
1. `test_p7_2.py:142-144` traction-string gap comment lacks forward pointer to closing phase.
2. `test_p7_2.py:71` `_import_generated_module` uses constant `name="gen_p7_2"`; would shadow if test ever parametrized. Currently safe (single test).

**Resolution:** none required. Both items flagged for future awareness only.

```json
{"gate": "B", "attempt": 1, "result": "pass", "timestamp": "2026-04-30T07:28", "review_score": 9, "issue_counts": {"minor": 2, "medium": 0, "high": 0, "critical": 0}}
```

### Gate C — Verification

#### Attempt 1 — PASS

Iron-law fresh run on HEAD `c7964ce`:
```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_2.py -v -p no:cacheprovider
test_p7_2.py::TestP7_2::test_acceptance_passes_starting_from_latex_input PASSED
test_p7_2.py::TestP7_2::test_deliverables_present_at_surfaces PASSED
2/2 passed in 26.62s.
```

Slow test execution time confirms full Taichi JIT + Newton solve + reference comparison path actually traversed.

```json
{"gate": "C", "attempt": 1, "result": "pass", "timestamp": "2026-04-30T07:30", "test_results": {"passed": 2, "total": 2, "percentage": 100}, "commit": "c7964ce", "duration_seconds": 26.62}
```

**Final commit:** `c7964ce`.

