# Phase 7 — Tasks Analysis (ExecPhase, 2026-04-29)

Plan: `dev/plans/recovery_plan_latex_contract.md`
Phase: 7 — Verification, governance, and closure (R6)
Branch: `SOSOVSKI/recovery-phase7` (from `e313c0a`).

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By (open) | Blocks | Model tier |
|---------|-------|-----------------|------------|----------------|--------------------|--------|------------|
| P7-1 | Split e2e tests into `from_latex` / `from_problem_ir` families | 3 | 2 | 5 | — (P5-1 done) | — | Sonnet/Opus |
| P7-2 | Canonical LaTeX-to-solution acceptance test on the MVP-stable path | 4 | 3 | 7 | — (P2-1, P4-1, P5-1 done) | — | **Opus only** |
| P7-3 | Examples LaTeX-first; programmatic examples demoted | 2 | 1 | 3 | — (P2-1 done) | — | Sonnet/Opus |
| P7-4 | ADR / recovery-status note cross-linking plan + drift report | 1 | 1 | 2 | — | — | Sonnet/Opus |
| P7-5 | Archive or annotate superseded sprint/task docs | 2 | 1 | 3 | — (P5-1 done) | — | Sonnet/Opus |
| P7-6 | Closing drift/alignment review post-R1–R4 | 2 | 1 | 3 | — (P2-1, P3-1, P4-1, P5-1 done) | — | Sonnet/Opus |

## Parallelism plan

- **Parallel batch (complexity ≤ 3 AND risk ≤ 3):** P7-1, P7-3, P7-4, P7-5, P7-6.
- **Sequential (complexity > 3):** P7-2 — runs after P7-1 lands so the new acceptance test can adopt the `from_latex` marker introduced by P7-1.

## Within-phase dependency edges

Strict graph dependency: none between P7 tasks. Soft dependency: P7-2 should adopt the marker registered by P7-1 (rather than introducing a parallel marker), so prefer P7-1 → P7-2 ordering.

## Cross-phase dependencies (status)

All upstream blockers are `done` per tracker:
- P2-1 (#154 done 2026-04-27)
- P3-1 (#160 done 2026-04-27)
- P4-1 (#166 done 2026-04-27)
- P5-1 (#175 done 2026-04-28)

## Recommended execution order

1. **P7-4** (ADR — score 2, no upstream blockers) — anchors the governance story before docs sweep.
2. **P7-3, P7-5, P7-6** (docs-tier, score ≤ 3) — dispatch in parallel after P7-4 lands.
3. **P7-1** (test-family split) — registers `from_latex` / `from_problem_ir` markers.
4. **P7-2** (LaTeX-to-solution acceptance) — sequential, Opus, last because it consumes the `from_latex` marker registered by P7-1.

## Failure-pattern survey (from prior gate files)

Phases 1–6 finished with no recurring failure modes captured in `gates/phase_*_gates.md` beyond a single P3-2 `test_gap` entry. No specific tripwires inherited into Phase 7.

## Phase 5 → 6 → 7 lessons (carried forward)

- **autoflake stripping** mid-batch imports (Phase 5 lesson) — anchor `__all__` upfront when adding helpers used by later commits.
- **Hard-coded line-number whitelists** (Phase 5 lesson, `test_phase6_exit.py`) — Phase 7's family split (P7-1) should NOT add new line-number whitelists.
- **Gate-B medium triage** (Phase 5 lesson) — fix-now beats defer for trivial mediums.
- **One-way import direction** — `mechdsl-core` → `algo2code` only (Phase 6 lesson). Phase 7 introduces no new cross-package imports.
