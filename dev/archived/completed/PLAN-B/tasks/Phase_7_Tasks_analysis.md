# Phase 7 — Task Complexity & Risk Analysis

**Plan:** `dev/design_docs/PLAN-B.md` §B7
**Branch:** `plan-b_phase-7` (off `plan-b_phase-6` tip; Phases 5 & 6 not yet merged to main)
**Scaffold HEAD:** `ce263fd`
**Baseline fast-suite state:** 1214 passed / 1 failed (transient P6-exit TODO-marker tripwire on scaffold stubs — will clear when stubs become implementations) / 7 skipped

## Summary

| Task | Complexity | Risk | Combined | Model | Rationale |
|------|-----------:|-----:|---------:|-------|-----------|
| P7-1 | 4 | 4 | **8** | **Opus** | New IR field (DynamicsMode) + new codegen branch (`emit_explicit_driver`) + new solver module (lumped mass) + new Taichi `v` field. Integration-break hazard: Phase 5 precedent ×3 (strict-key guards in `test_mechanics_ir*`). |
| P7-2 | 3 | 2 | **5** | **Sonnet** | Pure Python helper (numpy-only). Well-bounded: char length + c_d = sqrt((λ+2μ)/ρ) + safety factor. Unit tests on a regular Hex8 mesh. |
| P7-3 | 3 | 3 | **6** | **Opus** | Phase-7 exit acceptance: FFT of free-vibration time history + quasi-static explicit/implicit cross-check. Requires mass scaling rationale and convergence tuning. Opus for exit criterion robustness. |

**Execution order:** strictly sequential P7-1 → P7-2 → P7-3 (dependency chain).

## Per-task hazard notes

### P7-1 (Opus) — Lumped mass + central-difference integrator

- `ProblemIR` gets a new optional `dynamics_mode: DynamicsMode` field. **Phase 5 integration-break precedent**: strict-key-set guards in `test_frontend_build_context.py`, `test_mechanics_ir.py` must accept the new key; `from_dict` must accept missing `dynamics_mode` (auto-infer to `STATIC` — same pattern as `configuration`).
- `emit_explicit_driver` branches off `DynamicsMode == EXPLICIT`. Emits `advance_one_step(dt)` and a conditional `v` Taichi field. Must **not** break the default STATIC emission path — 100% of existing Taichi printer tests must stay green.
- Hex20 / Tet10 row-sum lumping is OUT OF SCOPE — stub with `raise NotImplementedError("Plan B phase ≥ B7 follow-up: row-sum lumping for {element_type.value}")`.
- Element deletion: honour `if is_deleted[e] != 0: continue` in `advance_one_step` (Phase 6 carry-forward).
- **Single-step hand calc**: unit test advances a free Hex8 under uniform body-force with known M_lumped and compares v^{1/2}, u^1 to analytical.

### P7-2 (Sonnet) — Critical time step

- `critical_timestep(coords, conn, lam, mu, rho, safety=0.9)` returns global dt.
- Char length: Hex8 = volume^(1/3); tet = shortest edge (stub other element types with NotImplementedError).
- Wave speed `c_d = sqrt((lam + 2*mu) / rho)`.
- Per-element dt = L_min / c_d; global = min × safety.
- **Unit-cube Hex8 sanity**: dt = 1.0 / sqrt((λ+2μ)/ρ) · 0.9 within 1e-8.
- No IR changes, no codegen changes.

### P7-3 (Opus) — Free vibration + explicit/implicit cross-check

- `@pytest.mark.slow @pytest.mark.integration` acceptance test file.
- Free-vibration: fixed-fixed elastic block, small initial displacement, FFT of center-node displacement history, peak frequency vs analytical 1st mode within 1%. Analytical first mode for 1D bar fixed-fixed: `f_1 = c_d / (2L)`.
- Explicit/implicit cross-check: slow ramp load, quasi-static (mass-scaled `rho·1e6`), both solvers must converge to final displacement within 1e-6.
- Document mass-scaling factor in test docstring.

## Cross-phase hazards (from prior gate history)

- **Phase 5 integration-break ×3**: strict-key-set guards tripped three separate times. Mitigation: P7-1 implementer prompt explicitly calls out `test_mechanics_ir.py`, `test_frontend_build_context.py`, and `to_dict/from_dict` round-trip.
- **Phase 2 physics_error** (isotropic-state masking): not directly applicable but reinforces need for non-trivial multi-axial test states — single-step hand-calc on free element should use multi-component displacement.
- **Phase 6 coverage gap**: Lemaitre damage-aware tangent deferred; explicit dynamics is matrix-free so Phase 7 gets a free ride on that front.
