# Phase 9 — Task analysis

**Branch:** `plan-b_phase-9` (off `plan-b_phase-8` tip `5465694`)
**Date:** 2026-04-17
**Plan:** `dev/design_docs/PLAN-B.md` §B8b (lines 243-261)

## Execution graph

Strict sequence (no parallel batches): **P9-1 → P9-2 → P9-3**.

P9-2 blocks on P9-1's family enum; P9-3 blocks on P9-2's emitter dispatch. No tasks can run concurrently.

## Complexity/risk matrix

| Task | Title | Complexity | Risk | Sum | Model | Rationale |
|------|-------|-----------:|-----:|----:|-------|-----------|
| P9-1 | Named contraction-family template design | 4 | 3 | 7 | **Opus** | Codebase audit + authoritative spec write; feeds P9-2's code. |
| P9-2 | Refactor einsum_optimizer to emit via template families | 5 | 4 | 9 | **Opus** | Largest refactor in Plan B; touches einsum optimiser + 3 printers + goldens. |
| P9-3 | Budget regression test for all element × backend combos | 3 | 3 | 6 | **Sonnet** | Parametrised harness + baseline JSON; no semantic changes. |

Per the model-assignment rule (complexity+risk > 6 → Opus), P9-1 and P9-2 run on Opus; P9-3 runs on Sonnet.

## Gate preparation

Relevant failure patterns to watch for (from prior phases):

- `missing_impl` (Phases 2, 4, 5, 6, 8) — P9-2 is a refactor; guard against the "tier-only fallback" path being stubbed out instead of genuinely reachable.
- `integration_break` (Phases 5, 6, 8) — refactor must not break cross-backend equivalence (P8-3) or goldens. Gate B should independently verify golden diffs are whitespace-only.
- `misunderstanding` (Phases 4, 5, 6, 8) — tier vs family orthogonality is the subtlest concept; Gate B reviewer must trace that the two axes never get merged in code.

Phase 8's Gate B lesson (P8-3 attempt 1→3 progression): **"it compiles and tests skip" is not proof of end-to-end reachability.** For P9-2, the feature-flag's legacy-tier-only fallback path must be exercised by at least one test, not just declared.

## Task → issue mapping

| Task | GitHub issue | Blockers | Status |
|------|--------------|----------|--------|
| P9-1 | #105 | none (all predecessors done) | ready |
| P9-2 | #106 | P9-1 | blocked |
| P9-3 | #107 | P9-2 | blocked |

## Exit conditions (from Phase_9_body.md)

1. Every existing contraction maps to exactly one family.
2. All three backend printers dispatch through `family_emitters: dict[Family, EmitterFunc]`.
3. Feature-flag gate permits legacy-tier-only fallback during rollout.
4. JIT budget counter passes for every (element × material × backend) triple.
5. Family-based emission wall-clock within 1.2× of tier-only baseline.
6. Cross-backend equivalence (P8-3) still skip-clean or passes.
7. Golden files regenerated and reviewed.
