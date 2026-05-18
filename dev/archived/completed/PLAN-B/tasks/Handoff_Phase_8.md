# Handoff: Phase 7 → Phase 8

**From:** Phase 7 — Explicit dynamics (central-difference time integrator)
**To:** Phase 8 — MFEM and MOOSE backend printers
**Date:** 2026-04-17
**Phase 7 branch:** `plan-b_phase-7` (off `plan-b_phase-6` tip; Phases 5, 6, 7 not yet merged to main)
**Phase 7 commits:** `83d722f` (P7-1), `be28b80` (P7-2), `a381e07` (P7-3), plus tracking commits
**Phase 7 exit baseline:** **1220 passed / 0 failed / 1 skipped** in fast suite; slow suite clean.

---

## What Phase 7 shipped

| Task | Title | Commit | Deliverables |
|------|-------|--------|--------------|
| P7-1 | Lumped mass + central difference integrator | `83d722f` | `solver/lumped_mass.py` (133 lines), `DynamicsMode` enum on `ProblemIR`, `emit_explicit_driver` in `taichi_printer.py`, `tests/test_explicit_integrator.py` (3/3 pass) |
| P7-2 | Critical time step computation | `be28b80` | `solver/critical_timestep.py` (162 lines), `tests/test_critical_timestep.py` (3/3 pass) |
| P7-3 | Free vibration + explicit/implicit cross-check | `a381e07` | `tests/test_explicit_dynamics_acceptance.py` (2/2 @slow pass) — **Phase 7 exit** |

### Acceptance evidence

- **Free vibration (1D axial, Hex8)**: FFT peak of tip-node displacement matches analytical `f_1 = c/(4L)` within 1% over 5 analytical periods (free-fixed BC, SVK ν=0).
- **Explicit/implicit quasi-static cross-check**: 2×2×2 Hex8 block under ramp Dirichlet, mass-scaled `ρ·1e6`, 4000 ramp + 16000 hold steps, 2% velocity damping — final-displacement max-abs error < 1e-6.
- **Lumped mass**: 2×2×2 Gauss row-sum of consistent mass matches analytical diagonal within 1e-12 on unit Hex8.
- **Critical time step**: unit-cube Hex8 matches `0.9 · L / sqrt((λ+2μ)/ρ)` within 1e-8; irregular meshes respect global min; safety factor scales linearly.
- **Generator differentiation**: EXPLICIT source contains `advance_one_step` and not `newton_solve`; STATIC source contains `newton_solve` and not `advance_one_step` — STATIC emission byte-identical to pre-P7 output.

### Feature coverage after Phase 7

| Feature | Status |
|---------|--------|
| Implicit Newton driver (STATIC) | MVP |
| Element deletion (`is_deleted[e]`) | Plan B Phase 6 |
| Lumped mass (Hex8 row-sum) | **Plan B Phase 7** ✅ |
| Central-difference integrator (`advance_one_step(dt)`) | **Plan B Phase 7** ✅ |
| Courant critical time step | **Plan B Phase 7** ✅ |
| `DynamicsMode` compile-time switch | **Plan B Phase 7** ✅ |
| Taylor impact (UL + JC + reduced Hex8 + hourglass + P7) | Plan B Phase 10 (P10-7) |
| Contact, adaptive dt, co-rotational stabilisation | Post-MVP |

---

## Known trade-offs carried forward

These are **not blockers** — documented design choices to address later.

### 1. `allocate_explicit_fields` call-ordering gotcha (medium — P7-3 Gate B finding)

- **Where:** generated EXPLICIT-mode Taichi module.
- **Symptom:** Taichi's `materialize()` raises `RuntimeError: These field(s) are not placed` on `v` / `M_lumped` when user code follows the Phase 6 idiom (`allocate_fields(nn, ne)` → `x_ref.from_numpy(...)` → work) and forgets to call `allocate_explicit_fields(nn)` **before** the first `from_numpy`.
- **Why:** the emitter places the explicit-only fields (`v`, `M_lumped`) inside `allocate_explicit_fields` which is a separate callable from `allocate_fields`. First `from_numpy` triggers global materialise across all declared-but-not-placed fields.
- **Workaround in P7-3:** test helper (`_load_mesh_into_module`) calls `allocate_explicit_fields(n_nodes)` before the first `from_numpy`.
- **Phase 8 / P10-7 action:** either (a) merge `allocate_fields` + `allocate_explicit_fields` into one entry point with an `explicit=bool` switch, or (b) emit a module-level docstring that spells out the required call order. Either fix is ~10 lines in `taichi_printer.py`.

### 2. Explicit quasi-static cross-check uses 2% velocity damping

- **Where:** `tests/test_explicit_dynamics_acceptance.py::test_explicit_implicit_quasistatic_equilibrium_matches_within_1e6`.
- **Why:** undamped SVK block rings forever at the natural frequency. The mass-scaling trick damps the ringing's wall-clock but not its amplitude. 2% per-step linear nodal-velocity multiplicative damping brings amplitudes below 1e-6 within 20k steps.
- **Gap:** the test doesn't exercise physical material damping. For P10-7 Taylor impact, hourglass control may supply enough numerical dissipation, but a more principled damping model (Rayleigh, bulk viscosity for shocks) is a likely post-MVP follow-up.
- **Phase 10 action:** if P10-7 cannot reach acceptance without artificial damping, promote a small-scale Rayleigh damping implementation into the EXPLICIT driver.

### 3. `critical_timestep` uses reference-stiffness wave speed (damage-blind)

- **Where:** `solver/critical_timestep.py`.
- **Symptom:** `c_d = sqrt((λ + 2μ) / ρ)` uses the undamaged material moduli, but under active Lemaitre damage the effective stiffness is `(1 − D)·C`, giving `c_eff = c_0 · sqrt(1 − D)`. For `D = 0.95`, `c` drops to ~22% of undamaged → the **undamaged** estimate is too large by a factor of ~4.5, i.e. **unsafe** (actual critical dt is smaller than the estimate, so integrating at the estimated dt will go unstable as damage grows).
- **Why accepted in P7:** the Phase 7 free-vibration and cross-check tests are both elastic — damage is never active. The acceptance spec doesn't require damage-aware dt estimation.
- **Phase 10 action:** P10-7 Taylor impact combines JC viscoplasticity + Lemaitre CDM — the dt estimator must use `(1 − max(D_per_element)) · (λ + 2μ)` as the effective stiffness, and recompute every N steps (the 100-step default is already plumbed as a convention in `Phase_7_context_summary.md`). Add a `damage_state` optional argument to `critical_timestep`.

### 4. Free-vibration BC: free-fixed, not fixed-fixed

- **Where:** `tests/test_explicit_dynamics_acceptance.py::test_free_vibration_first_mode_period_within_1_percent`.
- **Task JSON suggested** fixed-fixed, test **chose** free-fixed (analytical `f_1 = c/(4L)` instead of `c/(2L)`). Either is physically valid; the exit criterion is 1% frequency match, met under free-fixed.
- **Gap:** no test currently verifies fixed-fixed modal behaviour. If a future consumer (contact, modal analysis) needs it, add it.

### 5. `ProblemIR.dynamics_mode` auto-infer

- **Where:** `ir/mechanics_ir.py`.
- Passed `None` → auto-infers to `STATIC` (mirrors the `configuration` auto-infer pattern). No validation error if a user accidentally passes `None` expecting EXPLICIT.
- **Fix opportunity:** if telemetry ever shows users getting silent STATIC fallback when they meant EXPLICIT, tighten to a required field. Low priority — Phase 8+ when user-facing API stabilises.

---

## Phase 8 scope at a glance (Plan B §B8)

- **P8-1** MFEM printer: emit C++ `NonlinearFormIntegrator`, handle Voigt convention conversion, MPI-parallel.
- **P8-2** MOOSE printer: emit MOOSE userobject/kernel classes, reuse the Einsum IR.
- **P8-3** Cross-backend verification: same ProblemIR → all three backends (Taichi, MFEM, MOOSE) → compare nodal displacements under a reference patch test.

### Implications of Phase 7 choices for Phase 8

1. **`DynamicsMode` is now part of `ProblemIR.to_dict`/`from_dict`.** Phase 8 printers must read this field and branch emission accordingly — or, more cheaply, Phase 8 can scope MVP to `DynamicsMode.STATIC` only and raise `NotImplementedError` for `EXPLICIT` (central difference on MFEM/MOOSE is a distinct codegen story).
2. **Explicit vs implicit emission split is a codegen precedent.** Phase 8 MFEM/MOOSE printers can mirror the pattern: `emit_mfem_newton_driver` / `emit_mfem_explicit_driver` (same for MOOSE). But MVP should likely ship STATIC-only.
3. **`advance_one_step(dt)` call-ordering gotcha (Known Trade-off 1)** doesn't affect MFEM/MOOSE — they don't use Taichi's lazy materialise. Phase 8 can proceed without touching that fix.
4. **Golden files.** Any golden-file regressions from Phase 7 codegen edits: none observed. The STATIC emission path is byte-identical.

---

## Recommended next action

Run `Aut_Faciam scaffold 8 dev/design_docs/PLAN-B.md` to scaffold Phase 8 from the current `plan-b_phase-7` tip. **Branching suggestion:** consider merging Phases 5, 6, 7 to `main` before Phase 8 begins — the stack is now five branches deep off main (plan-b_phase-5 → -6 → -7 → ...), which increases merge-conflict risk once Phase 8 touches `taichi_printer.py` extensively.

---

## File index (Phase 7 deliverables)

### Source
- `packages/mechdsl-core/src/mechdsl/solver/lumped_mass.py` (new, 133 lines)
- `packages/mechdsl-core/src/mechdsl/solver/critical_timestep.py` (new, 162 lines)
- `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` (+41 lines: `DynamicsMode` enum, `dynamics_mode` field + auto-infer)
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` (+119 lines: `emit_explicit_driver`, conditional `v`/`M_lumped` allocation, `advance_one_step` kernel)

### Tests
- `packages/mechdsl-core/tests/test_explicit_integrator.py` (3 tests, 2 `@slow`)
- `packages/mechdsl-core/tests/test_critical_timestep.py` (3 unit tests)
- `packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py` (2 `@slow @integration` tests)

### Tracking
- `dev/tasks/PLAN-B/json/P7-1.json`, `P7-2.json`, `P7-3.json` (all status=done)
- `dev/tasks/PLAN-B/gates/phase_7_gates.md` (9 gate entries, all PASS)
- `dev/tasks/PLAN-B/Phase_7_Tasks_analysis.md`
- `dev/tracking/tasks-tracker_PLAN-B.md` (P7 rows updated)
- GitHub: #62 (phase), #99, #100, #101 all closed with `done` label.
