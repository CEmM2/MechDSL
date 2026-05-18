# Handoff to Phase 8

Phase 7 completed the internal Taylor impact runtime surface (E7) — both
P7-1 (explicit runtime + rigid-wall contact + hourglass tracking) and
P7-2 (Johnson-Cook state + postprocessing) are done with zero upstream
drift. The runtime is a NumPy-only composition of existing primitives
and is now ready to be wrapped by the public Phase 8 benchmark runner.

## Completed Inputs

- **P7-1 done.** `mechdsl.verify.benchmarks._taylor_runtime` exposes
  `ExplicitTaylorState`, `RigidWallSpec`, `init_taylor_runtime`,
  `explicit_step`, `apply_rigid_wall_contact`, and
  `hourglass_energy_increment`. Reduced-Hex8 SVK centroid quadrature
  + Flanagan-Belytschko hourglass + lumped mass + central-difference
  leapfrog + frictionless rigid half-space contact are wired together.
- **P7-2 done.** Same module additionally exposes
  `init_taylor_runtime_jc`, `explicit_step_jc`,
  `extract_equivalent_plastic_strain`, `final_length`, and
  `mushroom_radius`. Per-element Johnson-Cook state (`eqplas`,
  `temperature`, `pk2_stress`) lives on `ExplicitTaylorState.material_state`
  and is updated via the existing `radial_return` primitive.
  Postprocessing helpers are bit-for-bit deterministic.

## Evidence

- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_runtime.py -v` → **5/5 passed** (P7-1 acceptance + 2 failure-route guards).
- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_state.py -v` → **14/14 passed** (P7-2 acceptance + edge cases + 6 failure-route guards).
- `uv run pytest packages/mechdsl-core/tests/test_phase10_taylor_runtime.py packages/mechdsl-core/tests/test_phase10_taylor_state.py packages/mechdsl-core/tests/test_johnson_cook.py packages/mechdsl-core/tests/test_hourglass_control.py -v` → **64/64 passed** (Phase 7 + JC + hourglass regression — zero upstream drift).
- `uv run ruff check` on the runtime module + both Phase 7 test files → clean.
- `uv run mypy` on the runtime module → clean.

## Branch / Commits

- Branch: `work/phase10-e7-taylor-runtime` (off `e23035f`).
- `43a2cbc` — Phase 7 scaffold (test stubs, JSON updates, validation report).
- `861929d` — P7-1 implementation.
- `c8e9b10` — P7-1 tracking + Phase_7_Tasks_analysis.md.
- `dbe3f6b` — P7-2 implementation + dt calibration in `test_finite_johnson_cook_state_update`.

## Phase 8 Notes

### What Phase 8 needs to add

- `TaylorImpactParameters` dataclass (mesh sizing, impact velocity, JC material params, wall geometry, time-stepping config, smoke vs. nightly settings).
- `run_taylor_impact_benchmark(params) -> BenchmarkResult` in `mechdsl.verify.benchmarks` — composes the Phase 7 runtime into a full Taylor-bar simulation, runs to a configured stopping criterion, and returns a `BenchmarkResult`. The plan forbids changes to `BenchmarkResult` itself; map Taylor metrics into the existing schema's metric/result fields.
- Replace the three skipped stubs in `packages/mechdsl-core/tests/test_taylor_impact.py` with active tests covering final length within 5%, mushroom diameter within 5%, and peak equivalent plastic strain within 10% of the Johnson & Cook (1985) reference.
- Provide deterministic smoke settings (small mesh, short horizon, mark `@pytest.mark.integration`) for fast CI; keep the full reference comparison `@pytest.mark.slow @pytest.mark.regression @pytest.mark.nightly` exactly as the existing stubs already are.

### Things to consume from Phase 7

- Build the impact bar mesh via `structured_block_mesh("hex8", ...)` from `_meshes`. The existing `_taylor_runtime` is HEX8-only by lumped-mass constraint — this matches the Johnson-Cook copper-bar reference mesh, so no element-family extension is needed for P10-7.
- Initialize via `init_taylor_runtime_jc(mesh, rho=..., jc_material=..., initial_velocity=v_uniform_inward)`.
- Drive the simulation with a loop over `explicit_step_jc(state, dt=..., jc_material=..., rho=..., lambda_h=...)`, applying `apply_rigid_wall_contact(state, wall)` at the end of each step (the runtime does *not* automatically apply walls — the public runner is responsible for that, intentionally, so contact policy is configurable from outside).
- Extract end-state metrics with `final_length(state)`, `mushroom_radius(state)`, and `extract_equivalent_plastic_strain(state)`. The mushroom-radius metric corresponds to the diameter assertion in the existing P10-7 stubs (multiply by 2 if the reference uses diameter rather than radius).

### Calibration warnings carried forward

- **dt sizing matters.** Wave speed `c = sqrt(E/rho)` and the smallest element edge set `dt_crit`. P7-2's Gate C attempt 1 hit a `physics_error` because the test's `dt` was an order of magnitude smaller than the wave-traversal time, so no element saw the impact wave within the test horizon. For Phase 8 smoke settings, ensure `n_steps * dt` exceeds at least a few wave traversals of the bar (typical Taylor-bar horizons are tens of microseconds; bar length / `c_p` longitudinal). Document the chosen `dt` and horizon in `TaylorImpactParameters` docstrings.
- **Energy bookkeeping is `abs(f.du)`** in the runtime, not signed work — chosen so the AC-1 hourglass-boundedness ratio is monotonic. If Phase 8 reports energy in a `BenchmarkResult.metrics` field, name it `dissipation_estimate` (or similar) rather than `kinetic_energy`/`internal_energy` to avoid implying signed conservation.
- **Carry-forward from Phase 6 P6-1 and Phase 7 P7-2 (both `physics_error`):** convergence / yield-onset assertions need a non-trivial load horizon. Don't assume "a few steps" is enough — verify against the wave-physics scale of the chosen mesh.

### Out of scope for Phase 8

- Tet10 / Hex20 Taylor variants (lumped mass is still HEX8-only).
- Non-Hex8 reduced integration / non-FB hourglass schemes.
- Public runners for non-Taylor explicit benchmarks.
- Extensions to `BenchmarkResult` schema.
- Performance harness (Phase 9 / P10-10).

## Tracker / Plan

- `dev/tracking/tasks-tracker_ph10_preq.md`: P7-1 and P7-2 rows updated to `done`. Phase 7 verification block holds the fresh-run evidence above.
- `dev/tasks/ph10_preq/json/P7-1.json`, `P7-2.json`: status `done`, completion notes, branch `work/phase10-e7-taylor-runtime`.
- `dev/tasks/ph10_preq/gates/phase_7_gates.md`: full gate history (P7-1 1/1/1 attempts, P7-2 1/1/2 attempts with the documented dt-calibration resolution).

Phase 8 starts from `dbe3f6b`. Recommended branch: `work/phase10-e8-public-taylor-benchmark` cut off `dbe3f6b`.
