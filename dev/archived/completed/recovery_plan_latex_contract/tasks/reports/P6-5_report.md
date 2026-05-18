# Task P6-5: Document `algo2code`'s role in the recovered architecture to prevent renewed drift — Complete

**Issue:** SOSOVSKI/MechDSL#187
**Branch:** `SOSOVSKI/scaffold-phase-6`
**Implementer commit:** `797f945`
**Started:** 2026-04-29 19:30 UTC
**Completed:** 2026-04-29 20:08 UTC

## Implementation Summary

Three documentation surfaces updated. Path B chosen — operator authored the design-doc patches directly because `.claude/hooks/protect-spec.sh` blocks Claude writes under `dev/design_docs/`. Implementer (Claude) handled README, examples README, and tests.

**Files changed:**
- `README.md` — added `### mechdsl-core ↔ algo2code integration` subsection (under existing `## Architecture` heading) naming both packages, `LinearSolverInterface` seam, four concrete adapters (`ScipyCGSolver`, `CGSolver`, `PCGSolver`, `Algo2CodePCGSolver`), the consumer/producer relationship, opt-in pattern via `select_linear_solver("generated")` / `newton_solve(linear_solver=...)`, and the P6-4 radial-return deferral. Cross-links to `dev/design_docs/11-ALGO2CODE.md`.
- `dev/examples/README.md` (new, Option A) — inventory table for the 8 existing example scripts plus a dedicated "algo2code-generated PCG seam (opt-in)" section showing the 3-line opt-in pattern. Notes that examples keep the default fallback for CI stability (P6-2 invariant). Cross-link to design doc.
- `dev/design_docs/11-ALGO2CODE.md` (operator-authored) — two patches:
  - §1.1 (around line 33): rewrote the integration-points list to reflect post-Phase-6 reality (P6-1..P6-3 landed, P6-4 deferred).
  - §2.5 (around line 144): replaced v1 PCG sample with canonical post-P6-1 LaTeX (byte-identical to `algo2code.library.pcg.PCG_ALGORITHM_LATEX`); added parser-deferral note explaining why P6-1 ships a hand translation.
- `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_5.py` — both stubs replaced with real assertions covering README + design_docs + dev/examples/README. Updated stub docstring to point at `dev/examples/` (the canonical examples directory; `examples/` and `packages/mechdsl-core/examples/` do not exist in this repo).

**Zero production-code touches.** `git diff b336e5f..797f945 -- packages/mechdsl-core/src/ packages/algo2code/src/` empty.

## Resolves Carry-Forward

P6-1 Gate-B medium ("design-doc sync — `dev/design_docs/11-ALGO2CODE.md §2.5` PCG sample stale relative to canonical `PCG_ALGORITHM_LATEX`") is now closed. §2.5 is byte-identical to the canonical constant and §1.1 names the recovered seam.

## Gate History

**Gate A — Spec Compliance:** 1 attempt → PASS (strict, multi-axis evidence)
- Zero production-code drift.
- All three documentation surfaces present (README, design_docs, dev/examples/README).
- Tests fleshed out and passing.
- Targeted regression: **308 pass / 1 skipped**.
- Full fast-suite: **1688 pass / 0 fail / 81 skipped / 113 deselected** (+2 vs P6-4 baseline from new P6-5 tests).
- ruff + mypy clean.
- algo2code runtime invariant preserved.
- Newton default branch unchanged.

**Gate B — Domain Quality:** 1 attempt → APPROVED, score 10/10 (operator-direct review)
- README architecture section: voice consistent, all required terms present, opt-in pattern documented, cross-link to design doc.
- Examples README: inventory + opt-in section + design-doc cross-link.
- Design-doc patches: §1.1 + §2.5 land per Path B; canonical PCG LaTeX byte-identical to `PCG_ALGORITHM_LATEX`.
- Discoverability: three independent surfaces — reader hits the seam from any entry point.
- Lessons applied: README cross-links design doc instead of duplicating it (P6-4 lesson — single canonical source); examples remain on default fallback for CI stability (P6-2 invariant preserved).
- Zero issues at any severity.

**Gate C — Verification:** 1 attempt → PASS
- `test_p6_5.py` 2/2 pass.
- Wider regression confirmed in Gate A.
- Aggregate: **2/2 (100%)**. Iron Law satisfied.

## Failure Patterns

None. Path B (operator-authored design-doc patches) cleanly worked around the `protect-spec.sh` block. Both Gates A and B passed first attempt with no issues at any severity.

## Test Evidence

```
$ uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_5.py -v
============================== 2 passed in 0.02s ===============================

$ uv run pytest -m "not slow and not gpu and not e2e" -q
1688 passed, 81 skipped, 113 deselected, 2 warnings in 52.62s

Targeted regression (Gate A evidence): 308 passed, 1 skipped
ruff check: All checks passed!
mypy: Success: no issues found in 1 source file
```

## Open Questions / Deferred Items

1. **algo2code parser extension** — multi-letter LHS support (the `pq` issue) and a real numpy backend would let `Algo2CodePCGSolver`'s body be replaced by a call to `algo2code.transpile(get_pcg_algorithm_latex(), backend='numpy')` rather than a hand translation. Filed as a Phase-6 follow-up; out of P6-5 scope (P6-5 documents the current state, not future work).

## Lessons Reused / Added

- **Reused:** strict Gate A multi-axis evidence pattern (zero src drift + targeted regression + full fast-suite + lint/type). Docs-tier multi-surface task; the multi-axis check confirmed each surface independently.
- **Added:** Path-B operator-authored design-doc workflow. When `protect-spec.sh` blocks Claude writes under `dev/design_docs/`, the path is: Claude drafts the patch text inline → operator applies it → Claude verifies via `git diff` and proceeds with non-protected surfaces. Pattern works cleanly without weakening the protection invariant.
- **Added:** cross-link discipline. README and examples README cross-link the design doc rather than duplicate its content — single canonical source, multiple discovery paths.

---

## Phase 6 — Complete

Phase 6 ("Integrate `algo2code` at the least risky seam (R5)") is now fully complete:

| Task | Status | Review | Commit |
|---|---|---|---|
| P6-1 | ✅ done | 9/10 (1 medium → resolved by P6-5) | `199dedc` |
| P6-2 | ✅ done | 9/10 (1 minor — comment fixed in batch) | `4b15191` |
| P6-3 | ✅ done | 10/10 | `f498880` |
| P6-4 | ✅ done | 10/10 | `5c310a0` |
| P6-5 | ✅ done | 10/10 | `797f945` |

**Phase 6 invariants preserved:**
- `LinearSolverInterface`, `CGSolver`, `PCGSolver`, `ScipyCGSolver` byte-identical / AST-identical to pre-Phase-6 baseline.
- `algo2code` remains runtime-free (zero `mechdsl` imports under `packages/algo2code/src/`).
- Newton-driver default solver remains `ScipyCGSolver`.
- Phase 6 sentinel `test_phase6_exit::test_no_resolved_todos_or_fixmes_remain` PASSES (4 → 3 → 2 → 1 → 0 marker fall-through arc complete).

**Phase 6 deliverables:**
- `Algo2CodePCGSolver` adapter at `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py` (P6-1).
- `algo2code.library.pcg.PCG_ALGORITHM_LATEX` canonical algpseudocode (P6-1).
- `get_default_solver()` + `build_solver(mode)` factories + `mechdsl/solver/integration.py::select_linear_solver(mode)` (P6-2).
- Single integration test covering `algo2code` → PCG → Newton plumbing (P6-3).
- Recovery-plan deferral callout for radial-return substitution (P6-4).
- Public architecture documentation across README, design_docs §1.1/§2.5, dev/examples/README (P6-5).

**Aggregate test counts at phase close:**
- Phase-6 dedicated tests: 7 (P6-1) + 2 (P6-2) + 2 (P6-3) + 2 (P6-4) + 2 (P6-5) = **15 task-tier tests, 100% pass**.
- Full fast-suite: **1688 pass / 0 fail / 81 skipped / 113 deselected**.

**Branch ready for PR:** `SOSOVSKI/scaffold-phase-6` → `main`.
