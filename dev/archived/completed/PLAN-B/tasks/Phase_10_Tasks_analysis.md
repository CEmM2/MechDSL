# Phase 10 — Tasks Analysis

**Plan:** `dev/design_docs/PLAN-B.md` §B9 (Full V&V suite)
**Date:** 2026-04-18
**Branch target:** `plan-b_phase-10` (off `plan-b_phase-9` tip `dab2514`)

---

## Dependency Gate — Hard Reality Check

| Task | Title | Blocked by | Resolved? | State |
|---|---|---|---|---|
| P10-1 | MMS convergence matrix | P2-5 ✅, P5-7 ❌, P9-3 ✅ | No | **BLOCKED on P5-7** |
| P10-2 | Cantilever matrix (12 cells) | P1-7 ✅, P4-1 ✅, P5-2 ❌, P5-3 ❌ | No | **BLOCKED on P5-2/P5-3** |
| P10-3 | Cook's membrane matrix (4 cells) | P1-7 ✅, P5-2 ❌ | No | **BLOCKED on P5-2** |
| **P10-4** | **Thick cylinder (Lamé)** | **P1-7 ✅** | **Yes** | **Ready** |
| P10-5 | Plate with hole (Kirsch K_t=3) | P5-3 ❌ | No | **BLOCKED on P5-3** |
| **P10-6** | **Necking bar (Simo & Hughes) matrix** | **P1-7 ✅** | **Yes** | **Ready** |
| P10-7 | Taylor impact | P1-7 ✅, P3-4 ✅, P5-5 ❌, P7-3 ✅ | No | **BLOCKED on P5-5** |
| **P10-8** | **Notched bar (Lemaitre)** | **P6-3 ✅** | **Yes** | **Ready** |
| **P10-9** | **Fiber-reinforced strip (HGO)** | **P4-4 ✅** | **Yes** | **Ready** |
| P10-10 | Nightly CI + perf harness | P10-1..P10-9 | No | **BLOCKED on all of P10** |

**Unblocked:** P10-4, P10-6, P10-8, P10-9 (4 of 10).
**Blocked:** P10-1, P10-2, P10-3, P10-5, P10-7, P10-10 (6 of 10).
**Root cause of the blockers:** Phase 5 (B5 element zoo — Tet10/Hex20/reduced-Hex8/hourglass/patch tests) has not started. `P5-1..P5-7` all `pending` in the tracker. Executing the blocked P10 tasks would require bypassing ScaffoldPhase Step 4.1 ("Never execute a task whose blocker has not been marked complete"). Not on the table.

---

## Complexity + Risk Scoring (unblocked subset)

| Task | Title | Complexity | Risk | Combined | Blocked By | Blocks | Model |
|---|---|---:|---:|---:|---|---|---|
| P10-4 | Thick cylinder (Lamé) benchmark | 3 | 2 | 5 | — | P10-10 | Sonnet 4.6 |
| P10-6 | Necking bar matrix (TL + UL) | 3 | 3 | 6 | — | P10-10 | Sonnet 4.6 |
| P10-8 | Notched bar (Lemaitre) benchmark | 4 | 4 | 8 | — | P10-10 | **Opus 4.6** |
| P10-9 | Fiber-reinforced strip (HGO) benchmark | 4 | 3 | 7 | — | P10-10 | **Opus 4.6** |

### Scoring rationale

- **P10-4** (complexity 3, risk 2): quarter-cylinder mesh is parametric; Lamé solution is closed-form; SVK-only TL-Hex8 path is fully supported today. The novel work is the `mechdsl.verify.benchmarks` harness module and internal-pressure BC on a curved face. Biggest risk is the pressure-BC loader if it doesn't exist.
- **P10-6** (complexity 3, risk 3): TL necking bar already exists in `test_benchmarks.py::TestNeckingBar`. The net new work is the UL variant + intra-run consistency check. Risk: UL under J2+SVK at a localisation-snap-through load step may diverge without arc-length continuation; Plan B has not built that driver.
- **P10-8** (complexity 4, risk 4): Lemaitre with full reference geometry is mesh-sensitive, and `test_phase6_exit.py` is a small-geometry unit test, not a load-displacement benchmark. No literature reference is currently named in the Phase 6 handoff. Needs: reference selection, matched parameters, load-displacement extraction, damage-field sampling.
- **P10-9** (complexity 4, risk 3): `test_hgo.py` is a state-point unit test, not a full-field benchmark. Needs: fiber-direction per-element field loader, uniaxial-strip geometry, literature curve digitisation. HGO parameter spread across papers is the main risk.

---

## Common Infrastructure Gap

All 4 unblocked tasks reference **`mechdsl.verify.benchmarks`**, which does not exist in the codebase. First concrete work item for any P10 task is defining and landing that module. Proposed minimum surface:

```python
# packages/mechdsl-core/src/mechdsl/verify/benchmarks/__init__.py
#
# - BenchmarkResult   dataclass(outputs, wallclock, newton_iters, cg_iters)
# - run_benchmark(config: BenchmarkConfig) -> BenchmarkResult
# - compare_to_reference(result, reference_curve, tolerance_pct) -> bool
```

This is effectively a **P10-0 pathfinder** that is not broken out in the plan. My recommendation is to fold it into P10-4 (the lowest-risk task) and then reuse it for P10-6/8/9.

---

## Recommended Execution Order

1. **P10-4 (pathfinder)** — lowest complexity + risk; establishes the benchmark harness module; analytical reference means no literature digitisation risk.
2. **P10-6** — reuses P10-4's harness; extends the already-passing necking bar test.
3. **P10-9** — new problem class (anisotropic) but mesh is trivial (rectangular strip).
4. **P10-8** — highest-risk; damage is mesh-sensitive; tackle last so P10-4/6/9 gate-C evidence stiffens our confidence in the harness.

P10-10 (nightly CI harness) remains blocked until all of P10-1..P10-9 complete; merging main-ward is blocked on Phase 5 regardless.

---

## Scope Recommendation for This Session

Auto mode is active, but the full 4-task unblocked set is **~8-15 hours of genuine engineering work** (new harness module + mesh generators + reference solutions + Newton drives + gate reviews × 4). A single session should not silently claim all four. Two realistic options:

- **Option A (pathfinder):** implement P10-4 end-to-end this session. Lands the `mechdsl.verify.benchmarks` harness, validates the approach against Lamé analytical, and gives Opus runs for P10-6/8/9 a solid base. Single-task gate cycle.
- **Option B (cascade):** P10-4 pathfinder → P10-6 → P10-9 → P10-8 in sequence, best-effort, pausing at any gate failure. Likely multi-session.

**Proceeding with Option A** unless the user overrides. Rationale: P10-4 is the smallest unit that delivers real Phase 10 value and unblocks the other three. Anything larger risks half-finished benchmarks that create false acceptance-evidence for Phase 10.

---

## Non-Goals for This Session

- **Not touching Phase 5.** The element zoo is a separate plan phase with its own acceptance gates. Silently implementing Tet10/Hex20 to unblock P10-2/3/5 would be an unscoped refactor and a scope violation.
- **Not wiring P10-10.** CI workflow work gated on all nine benchmark tasks passing in nightly CI.
- **Not merging Phase 5-9 to main.** Still carrying 5 unmerged phase branches (`plan-b_phase-5` onward). Merge policy is user-owned.
