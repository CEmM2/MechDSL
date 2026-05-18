# Phase 1 Task Analysis

**Plan:** `dev/design_docs/PLAN-B.md` (Phase B1 — Updated Lagrangian formulation)
**Phase issue:** #56
**Generated:** 2026-04-15

## Complexity & Risk Matrix

Complexity scale: 1 = trivial / 5 = highly complex
Risk scale:       1 = low risk / 5 = high risk
Combined score:   complexity + risk

Model assignment rules:
- Combined > 6 → **Opus 4.6 only** for implementer and reviewer subagents
- Complexity OR risk ≥ 3 → **Sonnet 4.6 or Opus 4.6**
- Haiku only permitted for read-only search/fetch

| Task ID | Title | Complexity | Risk | Combined | Model Tier | Blocked By | Blocks |
|---------|-------|-----------|------|----------|-----------|-----------|--------|
| P1-1 | ConfigurationIR extension (reference/current tagging) | 4 | 5 | **9** | **Opus** | — | P1-2, P1-5 (+P2-P8 entry) |
| P1-2 | UL kinematics (spatial shape gradients and current Jacobian) | 3 | 3 | 6 | Sonnet/Opus | P1-1 | P1-3, P1-4 |
| P1-3 | UL residual emission (Cauchy stress over current configuration) | 4 | 4 | **8** | **Opus** | P1-2 | P1-4, P1-6 |
| P1-4 | UL tangent operator emission (Jaumann material + geometric stiffness) | 5 | 5 | **10** | **Opus** | P1-3, P1-5 | P1-6 |
| P1-5 | Objective stress rates (Jaumann, Truesdell, Green-Naghdi) | 4 | 3 | **7** | **Opus** | P1-1 | P1-4, P1-7 |
| P1-6 | Formulation switching (directive + codegen dispatch) | 2 | 3 | 5 | Sonnet/Opus | P1-3, P1-4 | P1-7 |
| P1-7 | TL/UL equivalence + rigid rotation tests | 4 | 4 | **8** | **Opus** | P1-5, P1-6 | P10-2, P10-6, P10-7 |

## Ranking rationale

- **P1-1 (9):** Touches the semantic-center IR. A Plan-A regression here breaks 998 fast tests and cascades into every downstream Plan B task. Wide blast radius → max risk.
- **P1-4 (10):** Hardest math in the phase — Jaumann-rate conversion from C_IJKL is notoriously easy to get wrong — plus emits into the generator's tangent path. Both legs carry risk.
- **P1-3 (8):** Code-generator refactor with push-forward at the emission site. Physics bug propagates to the tangent and every benchmark.
- **P1-7 (8):** Requires a handwritten UL reference and a Newton convergence on a cantilever under a new formulation. Convergence bugs are subtle.
- **P1-5 (7):** Three rates, polar-decomposition for Green-Naghdi. Closed-form math, but the rigid-rotation invariant is the gatekeeper.
- **P1-2 (6):** Straightforward inv(j) helpers with one tricky guard (det(j) > 0). Lower risk because P1-3 will immediately stress it.
- **P1-6 (5):** Mostly mechanical rewiring; the risk is the wave of test updates after removing the rejection.

## Parallel-first pass

No tasks qualify for the parallel fast path. Every task has either complexity ≥ 3 or risk ≥ 3 (or both), and the early tasks all touch different files but chain dependencies (P1-1 → P1-2 → P1-3 → P1-4).

## Execution order

1. **P1-1** (no blockers) — foundational IR refactor. Must land first.
2. **P1-2 and P1-5** (both blocked_by P1-1, touch disjoint files) — eligible for parallel dispatch once P1-1 passes its gates.
3. **P1-3** (blocked_by P1-2) — sequential.
4. **P1-4** (blocked_by P1-3 and P1-5).
5. **P1-6** (blocked_by P1-3 and P1-4).
6. **P1-7** (blocked_by P1-5 and P1-6) — phase exit criterion.

## Session scope (this execution)

Per user confirmation, this session executes **P1-1 only**. The other six tasks remain pending until a follow-up `/Aut_Faciam exec 1` or per-task `/Aut_Faciam task <id>` call. P1-1 alone unblocks the rest of the phase.
