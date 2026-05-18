# Recovery-plan Phase 2 Gate History

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Phase:** 2 — Restore the frontend as the canonical entry point (R1)
**Branch:** `SOSOVSKI/back2latex` (compressed exec; one branch shared with the back2latex / recovery-Phase-1 work)
**Started:** 2026-04-27 (after recovery Phase 1 closed)
**Executed:** 2026-04-27
**Tasks:** P2-1, P2-2, P2-3, P2-4, P2-5, P2-6 (6 tasks; mix of unit/integration/docs)

## Per-task summary

```json
{
  "phase": 2,
  "branch": "SOSOVSKI/back2latex",
  "tasks": [
    {"id": "P2-1", "commit": "ca79e7b", "issue": 154, "tests": "4/4", "status": "done", "tier": "unit"},
    {"id": "P2-4", "commit": "8602cae", "issue": 155, "tests": "4/4", "status": "done", "tier": "docs"},
    {"id": "P2-2", "commit": "2526e45", "issue": 156, "tests": "4/4", "status": "done", "tier": "unit"},
    {"id": "P2-3", "commit": "7a3c395", "issue": 157, "tests": "6/6", "status": "done", "tier": "unit"},
    {"id": "P2-5", "commit": "7b9f3eb", "issue": 158, "tests": "6/6", "status": "done", "tier": "integration"},
    {"id": "P2-6", "commit": "(this batch)", "issue": 159, "tests": "10/10", "status": "done", "tier": "integration"}
  ]
}
```

## Where the work landed

| Task | Surface |
|------|---------|
| P2-1 | `mechdsl/__init__.py` — new `compile_latex(source, profile)` façade + thin `_problem_ir_from_context` adapter |
| P2-4 | `dev/tracking/tasks-tracker_MVP_plan.md` — five `P2.x` rows retagged `not_started` → `implemented-via-substitute` with substitute citations |
| P2-2 | `mechdsl/frontend/__init__.py` (Canonical / Secondary docstring split) + `build_context` function docstring + README Quickstart reordered to lead with LaTeX |
| P2-3 | `packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md` (new) + module docstrings in parser.py, directives.py, two_point.py reflecting the parser-of-record vs adapter/normalizer/validator split |
| P2-5 | First test suite that begins from LaTeX source and reaches an ArtifactBundle (SVK + J2; rejection coverage for unsupported dim + malformed directive) |
| P2-6 | Negative-test contract surface: 4 unsupported-construct cases + 4 malformed-LaTeX cases + 1 index-semantics case + 1 stable-message case, all routed through `compile_latex` |

## Gate B — Domain quality (phase-level)

Reviewer: claude-opus-4.7 (self-review against recovery-plan Phase 2 exit criteria).

| Check | Result | Evidence |
|---|---|---|
| LaTeX input is the documented primary entry point | ✅ | README Quickstart leads with `compile_latex`; `frontend/__init__.py` docstring splits Canonical / Secondary (P2-2) |
| Minimal stable compiler path begins at LaTeX source | ✅ | `compile_latex` parses + adapts + compiles; covered end-to-end by P2-5 elastic & plastic cases |
| Frontend task ownership no longer split across contradictory artifacts | ✅ | Five legacy MVP P2.x rows retagged `implemented-via-substitute` with substitute citations (P2-4) |
| Constraint: do not remove `build_context()` | ✅ | Function still importable + functional (verified by P2-2 smoke test) |
| Constraint: thin stable subset; do not block on full parser completeness | ✅ | Façade only handles `% mechanics` directives; nrpylatex math grammar deferred per ARCHITECTURE.md |
| Failures produce contract-level errors with stable messages | ✅ | P2-6 covers 10 negative paths through `compile_latex` |

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
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v
=> 53 passed in 0.18s
```

Iron Law evidence:
- Identified command: `uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v`
- Run: fresh, exit 0
- Read: 53/53 passed (Phase 1: 19, Phase 2: 34)
- Verified: every Phase 2 acceptance criterion has a live, passing assertion against the live codebase.

Wider regression check — pre-existing surfaces still healthy:

```
uv run pytest packages/mechdsl-core/tests/plan_tests/ \
              packages/mechdsl-core/tests/test_mechanics_ir.py \
              packages/mechdsl-core/tests/test_element_ir.py \
              packages/mechdsl-core/tests/test_taichi_printer.py \
              packages/mechdsl-core/tests/test_mfem_printer.py \
              packages/mechdsl-core/tests/test_moose_printer.py \
              packages/mechdsl-core/tests/test_frontend_parser.py \
              packages/mechdsl-core/tests/test_frontend_build_context.py \
              packages/mechdsl-core/tests/test_compile_pipeline.py \
              -m "not slow and not gpu"
=> 278 passed in 1.26s
```

```json
{
  "gate_c": {
    "command_phase_audit": "uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/ -v",
    "phase_audit_passed": 53,
    "phase_audit_total": 53,
    "command_wider_regression": "uv run pytest <plan_tests + IR + codegen + frontend + compile_pipeline> -m 'not slow and not gpu'",
    "wider_regression_passed": 278,
    "wider_regression_total": 278,
    "exit_code": 0,
    "phase_pass_rate": 100.0
  }
}
```

## Failure modes encountered

None during execution. (One earlier-attempt issue with the test_p2_4 row scanner — the 3-column verification mapping table at the bottom of the MVP tracker shadowed the main 10-column rows — was caught at first run and fixed in the same commit by adding a column-count discriminator. Category: `test_gap`.)

## Phase outcome

All 6 tasks `done`. The recovery plan's Phase 2 (R1) is complete: the
canonical `compile_latex` façade is live, the LaTeX-first contract is
testable, frontend responsibilities are split, and old MVP P2.x tracker
rows are reconciled. Phase 3 (R2) — enrich `ProblemIR` into the
semantic center — is the next phase.
