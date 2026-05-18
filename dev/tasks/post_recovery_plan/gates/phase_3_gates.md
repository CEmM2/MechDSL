# Phase 3 Gate History

Plan: `dev/plans/post_recovery_plan.md`
Branch: `post-recovery-plan_phase-3` (off `post-recovery-plan_phase-2` → main)
Started: 2026-05-01

## Pre-execution scan of prior phase gates

Phase 1 (boundary-condition / codegen) and Phase 2 (marker registration) gate histories show no recurring failure patterns relevant to docstring authoring. P2-1's `test_gap` (subprocess pytest probe needed `-c` and `--rootdir` flags from `tmp_path`) is noted in case any P3 stub uses a similar isolated-pytest-invocation pattern; otherwise no upfront warnings.

---

## P3-1 — Add BC handoff paragraph to compile_latex docstring

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-3`
**Issue:** #219

### Gate A — Spec Compliance (attempt 1, pass)

- New "Boundary conditions" NumPy-style section inserted into `compile_latex` docstring between Parameters and Returns. Section explicitly references `BoundaryCondition`, lists Dirichlet/Neumann support, names P1-5's `f_ext_kernel`, and describes the caller-provisioning contract for `f_ext`.
- `inspect.getdoc(compile_latex)` exposes the new section; `BoundaryCondition` and `f_ext` keywords present; caller-provisioning synonym `caller`/`supplied`/`supplies` present.
- Pre-existing D413 ("Missing blank line after last section 'Raises'") fixed by adding the trailing blank line inside the docstring — defect was unrelated to P3-1 but adjacent to the edit, so cleared in the same commit to satisfy acceptance criterion 3.

```json
{"task": "P3-1", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "ruff check --select D ... All checks passed!"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Edit limited to `packages/mechdsl-core/src/mechdsl/__init__.py` (the declared deliverable) plus a 1-line P2-2 stub fix (allowlist update — see below).
- New section reuses NumPy-style heading conventions (`Boundary conditions` underlined with `-`) consistent with neighbouring `Parameters` / `Returns` / `Raises` sections.
- Cross-task fix: `test_p2_2.py::test_docs_marker_selects_only_p7_doc_tier_tests` previously asserted that `pytest -m docs` collected only nodeids from `recovery_plan_latex_contract/test_p7_*.py`. P3-1 stubs add legitimate doc-tier tests under `post_recovery_plan/test_p3_*.py`, which broke that assertion. Allowlist relaxed in the same commit to include `post_recovery_plan/test_p3_*.py` and `tests/test_compile_latex_docstring.py` (the P3-2 deliverable). Recorded as `integration_break` (resolved in same attempt) — Phase 2 invariant required widening to accommodate Phase 3's legitimate doc-tier additions.

```json
{"task": "P3-1", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_1.py -v
3 passed in 0.08s
$ uv run ruff check --select D packages/mechdsl-core/src/mechdsl/__init__.py
All checks passed!
$ uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p5_1.py -v
7 passed, 1 skipped in 0.06s   # adjacent docstring test for Taichi paragraph still green
$ uv run pytest -m "not slow and not gpu" --tb=line -q
1772 passed, 85 skipped, 96 deselected
```

```json
{"task": "P3-1", "gate": "C", "attempt": 1, "result": "pass", "failure_modes": ["integration_break (P2-2 allowlist widened in same commit)"], "evidence": "3/3 task tests pass; ruff D-rules clean; 1772/1772 fast suite"}
```

**Completed:** 2026-05-01

---

## P3-2 — New docstring-presence test test_compile_latex_docstring.py

**Started:** 2026-05-01
**Branch:** `post-recovery-plan_phase-3`
**Issue:** #220

### Gate A — Spec Compliance (attempt 1, pass)

- Deliverable file `packages/mechdsl-core/tests/test_compile_latex_docstring.py` created (3 tests, all `@pytest.mark.docs`):
  1. `test_compile_latex_docstring_mentions_boundary_condition` — substring `BoundaryCondition` on `compile_latex.__doc__`.
  2. `test_compile_latex_docstring_describes_f_ext_caller_provisioning` — `f_ext` plus a caller-provisioning synonym (`caller`/`supplied`/`supplies`/`provisioning`).
  3. `test_compile_latex_docstring_names_dirichlet_and_neumann` — both BC kinds named.
- Meta-spec stub `tests/plan_tests/post_recovery_plan/test_p3_2.py` (3 tests) confirms the deliverable file exists, asserts the right substrings, and reads `__doc__` (so a docstring removal would fail the test rather than a source-text check passing trivially).
- All assertions read `inspect.getdoc(compile_latex)` so removing the paragraph from the docstring would cause the deliverable to fail (regression-guard property satisfied).

```json
{"task": "P3-2", "gate": "A", "attempt": 1, "result": "pass", "failure_modes": [], "evidence": "3/3 deliverable tests pass; 3/3 meta-spec stubs pass; -m docs collects 17 nodeids including the 3 new ones"}
```

### Gate B — Domain Quality (attempt 1, pass)

- Substring assertions key on lowercase keywords plus a small synonym set — robust against incidental copy-edits, fails on substantive contract removal (per Phase 3 context decision).
- Test file lives at `packages/mechdsl-core/tests/test_compile_latex_docstring.py` (not under `plan_tests/`) — correct: this is a permanent regression guard, not a phase-scoped stub.
- All three deliverable tests carry `@pytest.mark.docs` so they route through the Phase 2 `tier:docs` selector.
- Reuses the `inspect.getdoc(compile_latex)` pattern from `test_p5_1.py`.

```json
{"task": "P3-2", "gate": "B", "attempt": 1, "result": "pass", "review_score": 0, "minor": 0, "medium": 0, "high": 0, "critical": 0}
```

### Gate C — Verification (attempt 1, pass)

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_2.py packages/mechdsl-core/tests/test_compile_latex_docstring.py -v
6 passed in 0.07s
$ uv run pytest -m docs --tb=short
17 passed, 1939 deselected in 0.52s
$ uv run pytest -m "not slow and not gpu" --tb=line -q
1778 passed, 82 skipped, 96 deselected
```

```json
{"task": "P3-2", "gate": "C", "attempt": 1, "result": "pass", "evidence": "6/6 task tests pass; 17/17 docs-marked tests pass; 1778/1778 fast suite"}
```

**Completed:** 2026-05-01

---

