# Phase 7 Tasks Analysis

Plan: `dev/plans/ph10_preq.md` — Phase E7 Taylor Impact Runtime Surface
Branch: `work/phase10-e7-taylor-runtime`

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P7-1 | Taylor explicit runtime, contact, and hourglass sanity | 4 | 3 | 7 | P1-2 (done) | P7-2 |
| P7-2 | Taylor Johnson-Cook state and postprocessing | 4 | 3 | 7 | P7-1 | P8-1 |

## Model Assignment (per Step 2 rules)

Both tasks have combined score > 6 → **Opus 4.6 (or equivalent)** for implementer and reviewer subagents. Haiku is permitted only for read-only / search subagents.

## Complexity Justification

- **P7-1**: New internal explicit-dynamics runtime composing reduced Hex8 internal forces, Flanagan-Belytschko hourglass forces, lumped-mass central-difference time integration, and rigid-wall contact (signed-distance + normal-velocity reflection / clamp). Each piece exists upstream, but the runtime composition is new.
- **P7-2**: Johnson-Cook state update integration into the Taylor runtime, plus postprocessing helpers (final length, mushroom radius, PEEQ extraction). Touches the runtime created in P7-1 and depends on existing JC return-mapping behavior.

## Risk Justification

- Both tasks are *runtime-only*, so they cannot perturb upstream model semantics — but they consume `flanagan_belytschko_force`, JC `radial_return`, reduced Hex8 element factory output, lumped mass, and critical-timestep helpers. Risk comes from accidentally changing one of those upstream symbols (forbidden by the plan) or from numerical instabilities in the explicit loop.

## Execution Order

Sequential: **P7-1 → P7-2**. P7-2's `blocked_by` is P7-1, both modify a shared runtime module, and combined risk warrants one commit per task.

## Files Likely Touched (within phase scope)

- `packages/mechdsl-core/src/mechdsl/verify/benchmarks/_taylor_runtime.py` (new, primary)
- `packages/mechdsl-core/tests/test_phase10_taylor_runtime.py` (existing stub, fleshed out by P7-1)
- `packages/mechdsl-core/tests/test_phase10_taylor_state.py` (existing stub, fleshed out by P7-2)

## Forbidden Edits (per plan)

- `JohnsonCookMaterial`, JC `radial_return`, JC `yield_stress` semantics
- `flanagan_belytschko_force` / `flanagan_belytschko_stiffness` semantics
- Reduced Hex8 element semantics
- Public `run_taylor_impact_benchmark` — that surface is Phase 8 (P8-1/P8-2)
- `BenchmarkResult` schema
- Frontend `build_context`
- `ElementFactory`

## Cross-Phase Failure-Pattern Lookup

Scan of prior gate files (`gates/phase_1_gates.md` … `gates/phase_6_gates.md`):
- Phase 6 P6-1 hit `physics_error` ("[1,2,4] interpolation levels under-measured Hex8/Tet10 asymptotic L2 rates"). Resolution: use richer mesh refinement and cache repeated element computations. **Carry-over warning for P7-1**: when validating hourglass boundedness, ensure the test horizon and load case are non-trivial enough to expose hourglass growth — short / trivial loadings can mask the very behavior the test is meant to bound.
- No prior `integration_break` or `missing_impl` patterns in earlier phases. The repo's hourglass and JC primitives have stable test coverage already, so the dominant failure surface for Phase 7 will be runtime composition correctness, not upstream regressions.
