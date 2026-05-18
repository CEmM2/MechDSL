# Phase 6 Gate History

Plan: `dev/plans/post_recovery_plan.md`
Branch: `post-recovery-plan_phase-6` (off `post-recovery-plan_phase-5`)
Started: 2026-05-01

---

## P6-1 — Extract `_e2e_helpers.py`

**Issue:** #234

### Gate A — Spec Compliance (attempt 1, pass)
- New `packages/mechdsl-core/tests/_e2e_helpers.py` exposes `_import_generated_module` with the same signature (source, tmp_path, name="gen_e2e") as the four duplicated copies.
- Module docstring documents the family-split rule (cross-import allowed once 3+ callers exist; today 4 exist).

### Gate B — Domain Quality (attempt 1, pass)
- Single source of truth; readable, well-typed, no Taichi dependency.
- Returns `ModuleType` for type-checker friendliness.

### Gate C — Verification (attempt 1, pass)
- 2/2 task tests pass.

```json
{"task": "P6-1", "gate": "C", "attempt": 1, "result": "pass", "evidence": "2/2"}
```

---

## P6-2 — Swap helper consumers

**Issue:** #235

### Gate A — Spec Compliance (attempt 1, pass)
- `test_e2e_taichi.py` and `recovery_plan_latex_contract/test_p7_2.py` no longer define `_import_generated_module`; both import from `tests._e2e_helpers`.
- `test_p7_2.py` call site explicitly passes `name="gen_p7_2"` (helper default is `"gen_e2e"`).

### Gate B — Domain Quality (attempt 1, pass)
- Family-split rule satisfied (4 callers existed pre-swap; threshold is 3).

### Gate C — Verification (attempt 1, pass)
- 4/4 task tests pass; existing `test_e2e_taichi` and `test_p7_2` collect cleanly.

```json
{"task": "P6-2", "gate": "C", "attempt": 1, "result": "pass", "evidence": "4/4 + collection"}
```

---

## P6-3 — Robustify `test_p7_4.py:92`

**Issue:** #236

### Gate A — Spec Compliance (attempt 1, pass)
- Replaced `notes[0].read_text(...)` with `target_notes = [n for n in notes if "recovery_plan_latex_contract.md" in n.read_text(...)]; target = target_notes[0]`. Filter by plan-referenced filename.

### Gate B — Domain Quality (attempt 1, pass)
- Selection now order-independent: any reordering of `_candidate_note_paths()` continues to land on the same target.

### Gate C — Verification (attempt 1, pass)
- 2/2 task + 2/2 `test_p7_4` pass.

```json
{"task": "P6-3", "gate": "C", "attempt": 1, "result": "pass", "evidence": "2/2 task + 2/2 p7_4"}
```

---

## P6-4 — Replace `_INTENTIONAL_CLEANUP_MATCHES` whitelist with marker scan

**Issue:** #237

### Gate A — Spec Compliance (attempt 1, pass)
- `_INTENTIONAL_CLEANUP_MATCHES` set replaced by `_INTENTIONAL_CLEANUP_MARKER = "intentional-cleanup-site"` constant.
- `_iter_cleanup_matches` whitelists any TODO/FIXME hit within ±3 lines of a marker comment (window survives ruff multi-line statement reformatting).
- `test_emission_verification.py` now carries the marker on the docstring + assert lines for the SVK-no-TODO test.
- `test_phase6_exit.py` itself carries the marker next to the comment that mentions "TODO/FIXME" so it doesn't self-flag.

### Gate B — Domain Quality (attempt 1, pass)
- Marker text is greppable from anywhere in the repo.
- Drift-resistant: insert/delete blank lines around the cleanup site without touching the marker — scan still passes.
- `_CLEANUP_MARKER_WINDOW = 3` documented inline.

### Gate C — Verification (attempt 1, pass)
- 3/3 task + 5/5 `test_phase6_exit` pass; full fast suite 1846/1846 green.

Initial Gate-C run flagged `("test_phase6_exit.py", 126)` because the windowing comment itself mentioned "TODO/FIXME". Resolved by adding the marker comment immediately above the comment block. Recorded as `style_violation` resolved in same attempt.

```json
{"task": "P6-4", "gate": "C", "attempt": 1, "result": "pass", "failure_modes": ["style_violation (self-flag, resolved in same attempt)"], "evidence": "3/3 task + 5/5 phase6_exit + 1846/1846 fast suite"}
```

---
