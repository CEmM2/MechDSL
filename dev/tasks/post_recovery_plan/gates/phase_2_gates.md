# Phase 2 Gate History

Plan: `dev/plans/post_recovery_plan.md`
Branch: `post-recovery-plan_phase-2`
Started: 2026-05-01

## Pre-execution scan of prior phase gates

Phase 1 (`phase_1_gates.md`) recorded zero recurring failure-mode patterns relevant to Phase 2's marker-registration / decorator-swap / CI-audit work (Phase 1 was boundary-condition / codegen). No upfront warnings to surface.

---

## P2-1 — Register `docs` pytest marker

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-2`
**Issue:** #215

### Gate A — Spec Compliance (attempt 1, pass)

- pyproject.toml `[tool.pytest.ini_options].markers` extended with `"docs: documentation-anchor / doc-tier tests"`.
- `.claude/rules/tests.md` ## Markers section now lists `@pytest.mark.docs` line.
- `uv run pytest --markers` confirms `@pytest.mark.docs` present alongside `slow`, `gpu`, `e2e`.
- All three plan-listed deliverables met (lines 128–131 of plan).

```json
{"task": "P2-1", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "uv run pytest --markers | grep docs returns @pytest.mark.docs entry"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Marker name lowercase, matches existing tier-name style (`slow`, `gpu`, `e2e`).
- Description string matches phase context (`documentation-anchor / doc-tier tests`).
- No edits outside the two declared deliverable files.
- No conflict with existing markers; alphabetic ordering not enforced by the file convention so the new entry appended to end of list (consistent with prior additions like `from_problem_ir`).

```json
{"task": "P2-1", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_1.py -v
3 passed in 0.22s
$ uv run pytest -m "not slow and not gpu" --tb=line -q
1765 passed, 86 skipped, 96 deselected
```

**Sub-issue resolved during attempt 1:** initial `test_no_unknown_mark_warning_for_docs` failed because the spawned pytest probe ran in `tmp_path` outside the repo and missed the project pyproject.toml. Fix: pass `-c <root>/pyproject.toml --rootdir <root>` to the subprocess invocation. Re-run passed. Recorded as `test_gap` (stub harness gap), not a spec/domain failure.

```json
{"task": "P2-1", "gate": "C", "attempt": 1, "result": "pass", "failure_modes": ["test_gap (resolved in same attempt)"], "evidence": "3/3 task tests pass; 1765/1765 fast suite tests pass"}
```

**Completed:** 2026-05-01

---

## P2-2 — Swap @pytest.mark.integration → @pytest.mark.docs in test_p7_3..6

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-2`
**Issue:** #216

### Gate A — Spec Compliance (attempt 1, pass)

- All six pre-existing `@pytest.mark.integration` decorators in `test_p7_3.py`, `test_p7_4.py`, `test_p7_5.py` swapped to `@pytest.mark.docs` (verified by line-count grep: 2+2+2 = 6 decorators, all now docs).
- `test_p7_6.py` had no markers; added `@pytest.mark.docs` to its two test methods (`test_follow_up_review_confirms_contract_status`, `test_deliverables_present_at_surfaces`) and inserted `import pytest`.
- Deliverable A (no integration on P7-3..6) and Deliverable B (`pytest -m docs` selects exactly the doc-tier tests) both met.

```json
{"task": "P2-2", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "8 nodeids selected by -m docs, all under recovery_plan_latex_contract/test_p7_*.py"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Edits limited to four declared deliverable files; no other test file touched.
- P7-6's `import pytest` addition is the minimal-surface fix to enable the new decorators in a previously marker-free file.
- No regression in fast suite (1767/1767 vs 1765/1765 pre-task — delta = +2 task stub tests).

```json
{"task": "P2-2", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_2.py -v
2 passed in 0.71s
$ uv run pytest -m docs --tb=short
8 passed, 1939 deselected in 0.52s
$ uv run pytest -m "not slow and not gpu" --tb=line -q
1767 passed, 84 skipped, 96 deselected
```

```json
{"task": "P2-2", "gate": "C", "attempt": 1, "result": "pass", "evidence": "2/2 task tests pass; 8/8 docs-marked tests pass; 1767/1767 fast suite"}
```

**Completed:** 2026-05-01

---

## P2-3 — CI workflow tier:docs selector audit + add docs-tests job

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-2`
**Issue:** #217

### Audit findings (pre-edit)

| Workflow | Job | Selector | Doc-tier coverage |
|----------|-----|----------|-------------------|
| ci.yml | test | `-m "not slow and not gpu and not e2e"` | implicit (docs ∉ {slow, gpu, e2e}) |
| ci.yml | e2e-benchmarks | `-m e2e` | n/a |
| ci.yml | slow-tests | `-m "slow and not e2e"` | n/a |
| ci.yml | budget-regression | `-k budget` (no marker) | n/a |
| ci-backends.yml | (multiple) | (various) | n/a — none reference `docs` or `test_p7_3..6` directly |
| nightly.yml | (one) | `-m "nightly or regression"` | n/a |

No workflow currently runs `pytest -m docs`. No workflow uses `-m integration` to specifically target `test_p7_3..6` (the integration-marker fallback was decorator-level only, in the test files — already cleared by P2-2).

### Decision

Add a dedicated `docs-tests` job to `ci.yml` running `uv run pytest packages/mechdsl-core/tests/ -m docs --tb=short -q`. Triggers on `workflow_dispatch`, `pull_request`, or whenever a PR carries the `tier:docs` label. The pre-existing fast-tier `test` job continues to cover docs-tier tests in normal runs (no double-billing avoidance needed because the docs job is opt-in for `workflow_dispatch` / `tier:docs`-labelled PRs and the fast-tier job runs unconditionally — but the docs subset is small (8 tests, < 1s)).

### Gate A — Spec Compliance (attempt 1, pass)

- New `docs-tests` job invokes `pytest -m docs` (acceptance criterion 1).
- No integration-marker fallback for `test_p7_3..6` survives in any workflow (acceptance criterion 2).
- Workflow YAML parses cleanly (`yaml.safe_load(open('.github/workflows/ci.yml'))` → no exception).

```json
{"task": "P2-3", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "ci.yml docs-tests job present; grep finds zero -m integration referring to test_p7_3..6"}
```

### Gate B — Domain Quality (attempt 1, pass)

- `if:` conditional gates the job to dispatch / PR / `tier:docs` label so it does not double-trigger on every push.
- Job uses `--tb=short -q` to match neighbour-job conventions in the file.
- Comment block above job documents intent: tier:docs label-routed selector + redundancy with fast-tier coverage.

```json
{"task": "P2-3", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_3.py -v
2 passed in 0.02s
$ uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
(no output, no exception)
$ uv run pytest -m "not slow and not gpu" --tb=line -q
1769 passed, 82 skipped, 96 deselected
```

PR-level CI run will validate the new job end-to-end after merge (acknowledged risk in the task JSON).

```json
{"task": "P2-3", "gate": "C", "attempt": 1, "result": "pass", "evidence": "2/2 task tests pass; ci.yml YAML-valid; 1769/1769 fast suite"}
```

**Completed:** 2026-05-01

---

