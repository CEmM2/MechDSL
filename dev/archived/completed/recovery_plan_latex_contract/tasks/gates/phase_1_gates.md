# Recovery-plan Phase 1 Gate History

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Phase:** 1 — Freeze the contract surface (R0)
**Branch:** `SOSOVSKI/back2latex` (compressed exec; one branch shared with the back2latex closure)
**Started:** 2026-04-26 (recursive scaffold during back2latex P2-4)
**Executed:** 2026-04-26
**Tasks:** P1-1, P1-2, P1-3, P1-4, P1-5, P1-6 (6 tasks; all `docs` tier)

## Compressed-exec note

Per the same convention used for back2latex Phase 1, all six tasks were executed
on a single branch with one commit per task and a single combined Gate B/C at
phase end. The rationale is unchanged: every Phase 1 task here is doc-only, the
diffs touch non-overlapping surfaces (README, tracker legend, drift-history note,
codegen docstrings, MVP plan banners), and the per-task verification (live
pytest at `audit` tier) gives the same evidentiary value as a full per-task
gate cycle for ~4× lower cost.

## Per-task summary

```json
{
  "phase": 1,
  "branch": "SOSOVSKI/back2latex",
  "tasks": [
    {"id": "P1-1", "commit": "bd41a56", "issue": 148, "tests": "2/2", "status": "done"},
    {"id": "P1-4", "commit": "ae1e016", "issue": 151, "tests": "3/3", "status": "done"},
    {"id": "P1-5", "commit": "b09802b", "issue": 152, "tests": "3/3", "status": "done"},
    {"id": "P1-2", "commit": "cff354a", "issue": 149, "tests": "5/5", "status": "done"},
    {"id": "P1-3", "commit": "fe88f1a", "issue": 150, "tests": "3/3", "status": "done"},
    {"id": "P1-6", "commit": "(this batch)", "issue": 153, "tests": "3/3", "status": "done"}
  ]
}
```

## Where the work landed

| Task | Surface |
|------|---------|
| P1-1 | `README.md` — new `## Support tiers` section |
| P1-2 | Module docstrings: `codegen/mfem_printer.py`, `codegen/moose_printer.py`, `solver/lumped_mass.py`, `symbolic/models/__init__.py`, `ir/mechanics_ir.py` (ElementType) |
| P1-3 | `README.md` — new `### Stability policy` subsection |
| P1-4 | `dev/tracking/STATUS_LEGEND.md` (new); `dev/tracking/tasks-tracker_MVP_plan.md` preamble |
| P1-5 | `dev/reviews/frontend_drift_history.md` (new) |
| P1-6 | `dev/plans/MVP_plan.md` + `dev/plans/MVP_sprint{1,2,3}.md` supersession banners |

## Gate B — Domain quality (phase-level)

Reviewer: claude-opus-4.7 (self-review against recovery-plan Phase 1 exit criteria
and back2latex's per-task acceptance criteria).

| Check | Result | Evidence |
|---|---|---|
| Stable/experimental boundary documented | ✅ | README Support tiers section + Stability policy subsection (P1-1, P1-3) |
| Experimental code clearly labeled | ✅ | Module docstrings on MFEM/MOOSE/lumped_mass/non-MVP models/non-canonical elements (P1-2) |
| Tracker vocabulary supports truthful recovery reporting | ✅ | STATUS_LEGEND.md with 4 canonical values; MVP tracker preamble updated (P1-4) |
| Frontend deferral recorded as drift | ✅ | dev/reviews/frontend_drift_history.md distinguishes planned-but-deferred / never-planned / implemented-via-substitute (P1-5) |
| Old plans annotated as superseded | ✅ | Supersession banners on MVP_plan.md + 3 sprint plans, citing recovery plan + STATUS_LEGEND.md + frontend_drift_history.md (P1-6) |
| No new work begins without tier classification | ✅ (forward-looking) | README Stability policy subsection makes the requirement explicit |

```json
{
  "gate_b": {
    "review_status": "approved",
    "review_score": 100,
    "issues": {"minor": 0, "medium": 0, "high": 0, "critical": 0},
    "failure_categories": []
  }
}
```

## Gate C — Combined verification (phase end)

```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v -m audit
=> 19 passed in 0.02s
```

Iron Law evidence:
- Identified command: `uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v -m audit`
- Run: fresh, exit 0
- Read: 19/19 passed (100%)
- Verified: every acceptance criterion across all 6 tasks now has a live, passing assertion against the live target files

Wider regression check (177/177 across all touched suites):

```
uv run pytest packages/mechdsl-core/tests/plan_tests/ \
              packages/mechdsl-core/tests/test_mechanics_ir.py \
              packages/mechdsl-core/tests/test_element_ir.py \
              packages/mechdsl-core/tests/test_taichi_printer.py \
              packages/mechdsl-core/tests/test_mfem_printer.py \
              packages/mechdsl-core/tests/test_moose_printer.py \
              -m "not slow and not gpu"
=> 177 passed
```

```json
{
  "gate_c": {
    "command": "uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v -m audit",
    "passed": 19,
    "total": 19,
    "pass_rate": 100.0,
    "exit_code": 0,
    "wider_regression_pass_rate": 100.0,
    "wider_regression_count": "177/177"
  }
}
```

## Failure modes encountered (during execution)

- One test had to be relaxed: back2latex `test_p2_4::test_no_exec_artifacts_present`
  was the historical hard-stop invariant from the back2latex engagement. Now that
  exec is authorized on the recovery plan, that invariant is obsolete by
  design. Test was rewritten as `test_completion_data_consistent_with_status` —
  a data-integrity check that survives across exec phases. The original hard
  stop is preserved as historical context in the test's docstring and in
  `dev/tasks/back2latex/gates/phase_2_gates.md`.
- Category: `test_gap` (test scope was tied to a now-retired contract).

## Phase outcome

All 6 tasks `done`. The recovery plan's Phase 1 (R0) is complete. Phase 2 (R1)
— canonical `compile_latex(...)` façade — is the next phase. Phase 2 is not
yet scaffolded; the next legal action is `/Aut_Faciam scaffold 2 dev/plans/recovery_plan_latex_contract.md`.
