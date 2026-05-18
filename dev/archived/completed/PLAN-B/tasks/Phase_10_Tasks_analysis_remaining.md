# Phase 10 — Remaining Task Analysis

**Analysis date:** 2026-04-20
**Branch:** `plan-b_phase-10-remaining` (off `main`)
**Baseline:** main @ `6251f84` — 1308 passed / 84 skipped in fast suite (per alpha readiness audit)

## Situation

Phase 10 was partially delivered in PR #118 (2026-04-19). Four tasks (P10-4, P10-6, P10-8, P10-9) shipped. The PR description claimed the remaining six were "hard-blocked on Phase 5 (element zoo)" — but Phase 5 had actually landed earlier (2026-04-17, commits `5a248ca`..`21d0e2b`). The tracker markdown was out of sync, and the PR author appears to have read the stale tracker.

All Phase 5 deliverables verified present and 36/36 tests passing. All 6 remaining Phase 10 tasks are now genuinely unblocked.

## Task scoring

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined | Blocked by (now) | Blocks | Model |
|---------|-------|-----------------|------------|----------|------------------|--------|-------|
| P10-3 | Cook's membrane (TL/UL × J2 × Hex8/Tet10) — 4 cells | 3 | 2 | 5 | — | P10-10 | Sonnet |
| P10-5 | Plate with hole (TL × SVK × Hex8/Hex20) — 2 cells | 3 | 3 | 6 | — | P10-10 | Sonnet/Opus |
| P10-2 | Cantilever matrix (TL/UL × SVK/NH × Hex8/Tet10/Hex20) — 12 cells | 4 | 3 | 7 | — | P10-10 | **Opus** |
| P10-1 | MMS convergence matrix (8 cells) | 4 | 3 | 7 | — | P10-10 | **Opus** |
| P10-7 | Taylor impact (UL × JC × reduced Hex8 + FB + explicit) | 5 | 5 | 10 | — | P10-10 | **Opus only** |
| P10-10 | Perf harness + nightly CI | 4 | 3 | 7 | P10-1..P10-9 (5 still pending) | — | **Opus** |

## Execution order (dependency-respecting)

1. **P10-3 Cook's membrane** — pilot task. Smallest (4 cells), existing reference, no new capability required.
2. **P10-5 Plate with hole** — new mesh + stress extraction, but self-contained.
3. **P10-2 Cantilever matrix** — 12 cells, existing infrastructure, expected Tet4 shear-locking caveats.
4. **P10-1 MMS convergence matrix** — 8 cells, parametric over element × material, relies on analytical MMS.
5. **P10-7 Taylor impact** — combined test of Phase 1+3+5+7. Highest risk. May surface regressions in any upstream phase.
6. **P10-10 Perf harness** — final task, blocks on all above.

## Parallelization analysis

Per Aut_Faciam rules, parallel first pass requires complexity ≤ 3 AND risk ≤ 3 AND no file overlap. Only P10-3 qualifies. All other tasks run sequentially.

All 6 tasks modify `mechdsl.verify.benchmarks` (new harness per task) and may touch shared reference kernels. File overlap likely — sequential is safer.

## Known risks across the remaining work

- **P10-7 is a Plan B acceptance gate.** It combines UL (P1-7) + JC viscoplastic (P3-4) + reduced Hex8 + FB hourglass (P5-5) + explicit dynamics (P7-3) + rigid-wall contact (new, not in Plan B). Contact is the open issue — suggest penalty on `y = 0` to avoid full contact-detection.
- **MMS has no closed form for every material.** P10-1 task note says "restrict MMS to elastic combinations and use engineering benchmarks for dissipative models."
- **Tet4 shear locking.** Cantilever matrix (P10-2) may fail the 5% tolerance on Tet4 at 40×8×4 — task note allows 80×16×8 for tet cells.
- **Stress concentration extraction.** P10-5 depends on nodal extrapolation, not raw QP values.
- **CI runner noise.** P10-10 baselines need median-of-3 + rolling average per the task's own risk note.

## Out-of-band notes

- P9-1 test issue in the tracker ("awaits /tmp/section9_new.md") is stale. All 3 P9-1 tests now pass — spec patch was applied at some point.
- GitHub issues #89–95 (Phase 5 tasks) and #60 (Phase 5 parent) were correctly closed when Phase 5 completed. No action needed.
