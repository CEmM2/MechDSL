# Phase 8 Tasks Analysis

Plan: `dev/plans/ph10_preq.md` — Phase E8 Public Taylor Impact Benchmark
Branch: `work/phase10-e8-public-taylor-benchmark` (off `3bc9e37`, which is Phase 7 final + Phase 8 scaffold)

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks |
|---------|-------|-----------------|------------|----------------|------------|--------|
| P8-1 | Public Taylor impact benchmark API | 4 | 3 | 7 | P7-2 (done) | P8-2 |
| P8-2 | Taylor impact benchmark test activation | 3 | 4 | 7 | P8-1 | P9-1 |

## Model Assignment (per Step 2 rules)

Both tasks have combined score > 6 → **Opus 4.6 (or equivalent)** for implementer and reviewer subagents.

## Complexity Justification

- **P8-1**: New public benchmark module composing the entire Phase 7 internal runtime (init_jc → loop of explicit_step_jc + apply_rigid_wall_contact → postprocessing) into a single deterministic runner returning the shared `BenchmarkResult` schema. Includes `TaylorImpactParameters` with `smoke()` / `nightly()` classmethods (mirroring `CantileverParameters`), parameter validation, and `__init__.py` export updates. New module wiring + parameter contract design.
- **P8-2**: Activates the existing `test_taylor_impact.py` stubs by replacing `pytest.skip` with real assertions against Johnson & Cook (1985) reference values. Lower implementation complexity (no new modules) but higher *physics* risk: must source/document JC reference values, handle the mushroom diameter ↔ radius factor, and ensure the nightly run is deterministic and stays well under the wave-physics calibration trap from Phase 7 P7-2.

## Risk Justification

- **P8-1 risk 3**: Adds public API surface that downstream Phase 9 (P10-10 perf harness) will lock into. The plan forbids changing `BenchmarkResult` — must map Taylor-specific metrics into `extras` per the existing benchmark convention. Forbidden upstream edits include `BenchmarkResult`, `build_context`, `ElementFactory`, and any Phase 7 runtime symbol's signature.
- **P8-2 risk 4**: Highest-risk piece in the phase — actual physics validation against published reference data, plus the nightly run must converge in finite time on a Taylor-bar geometry (much larger than the Phase 7 smoke bar). Carry-forward from Phase 7 P7-2: `dt` sizing must respect the wave-traversal time of the smallest element.

## Execution Order

Sequential: **P8-1 → P8-2**. P8-2 depends on P8-1's public runner.

## Files Likely Touched (within phase scope)

- `packages/mechdsl-core/src/mechdsl/verify/benchmarks/taylor_impact.py` (NEW — primary, P8-1)
- `packages/mechdsl-core/src/mechdsl/verify/benchmarks/__init__.py` (export updates, P8-1)
- `packages/mechdsl-core/tests/test_phase10_taylor_benchmark.py` (existing stub, fleshed out by P8-1)
- `packages/mechdsl-core/tests/test_taylor_impact.py` (existing P10-7 stubs, activated by P8-2)

## Forbidden Edits (per plan + Phase 7 invariants)

- `BenchmarkResult` schema (CRITICAL impact per plan)
- Any Phase 7 runtime symbol signature: `init_taylor_runtime`, `init_taylor_runtime_jc`, `explicit_step`, `explicit_step_jc`, `apply_rigid_wall_contact`, `RigidWallSpec`, `ExplicitTaylorState`, `extract_equivalent_plastic_strain`, `final_length`, `mushroom_radius`, `hourglass_energy_increment`
- Johnson-Cook model semantics (`JohnsonCookMaterial`, `radial_return`, `yield_stress`)
- Flanagan-Belytschko hourglass force/stiffness
- Reduced Hex8 element semantics
- `build_context`, `ElementFactory`

## Cross-Phase Failure-Pattern Lookup

Scan of `gates/phase_1_gates.md` … `gates/phase_7_gates.md`:

- **Phase 7 P7-2 (`physics_error`)**: `dt = 1e-9` was an order of magnitude smaller than 1mm-element wave-traversal time (~200 ns), so the impact wave didn't reach any element within the test horizon. **Carry-forward warning for P8-1 smoke + P8-2 nightly**: when sizing `TaylorImpactParameters` `dt` and `n_steps`, ensure `n_steps * dt` ≫ `bar_length / c` where `c = sqrt(E/rho)`. For typical Taylor copper-bar parameters (E ≈ 117 GPa, rho ≈ 8930 kg/m³, c ≈ 3620 m/s, L ≈ 25 mm), traversal is ~7 µs — total simulation time should be tens of µs. Document this in the `TaylorImpactParameters` docstrings.
- **Phase 6 P6-1 (`physics_error`)**: too-coarse mesh refinement under-measured asymptotic rates. Resolution: richer refinement levels. **Less directly applicable to Phase 8** — the Taylor benchmark is a fixed-geometry comparison, not a refinement study. But the smoke profile must be coarse enough to be fast yet fine enough that the centroid plastic flow is non-trivial.
- No `integration_break` patterns in earlier phases. Public-API exports have stable test coverage; the main regression risk is the `__init__.py` `__all__` list.

## Phase 8 Implementer Notes (from handoff + scaffold validation)

- **Mushroom diameter vs radius**: Existing P10-7 stub at `test_taylor_impact.py::test_taylor_impact_mushroom_diameter_within_5pct` asserts on diameter, but Phase 7 helper returns radius. Either (a) expose a `mushroom_diameter` helper on `_taylor_runtime` (preferred — keep the public benchmark API in diameter for consistency with the J&C reference), or (b) multiply by 2 in the runner / test. Document the choice. Note: a `mushroom_diameter` helper would be a tiny extension to the runtime, allowed because it's purely additive — does not modify `mushroom_radius`'s signature.
- **HEX8-only**: lumped mass + Phase 7 runtime are HEX8-only. Reject non-Hex8 element types in `TaylorImpactParameters.__post_init__`.
- **Smoke vs nightly classmethod pattern**: mirror `CantileverParameters.smoke()` / `.nightly()` exactly.
- **Reuse `BenchmarkResult` verbatim**. Map Taylor metrics into `extras` (`extras["final_length"]`, `extras["mushroom_radius"]`, `extras["mushroom_diameter"]`, `extras["peak_peeq"]`).
- **Johnson & Cook (1985) reference values for P8-2**: copper bar, L_0 = 25.4 mm, D_0 = 7.62 mm, v_0 ≈ 190 m/s. Reported values in literature: L_f / L_0 ≈ 0.825 (final length ≈ 21 mm), D_f / D_0 ≈ 1.91 (mushroom diameter ≈ 14.6 mm), peak PEEQ ≈ 1.4–2.0 depending on mesh resolution. P8-2 should pull these from a documented source and cite it in the test docstring.
