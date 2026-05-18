# Phase 7 Scaffold Validation

**Plan:** `dev/design_docs/PLAN-B.md` §B7 (lines 206-219)
**Branch:** `plan-b_phase-7` (branched from `plan-b_phase-6` tip)
**Scaffolded:** 2026-04-17

## Validation of task JSONs

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P7-1 | Lumped mass + central difference integrator | `test_artifacts`, `verification_commands` were `[""]` | auto-filled |
| P7-2 | Critical time step computation | `test_artifacts`, `verification_commands` were `[""]` | auto-filled |
| P7-3 | Free vibration + explicit/implicit cross-check | `test_artifacts`, `verification_commands` were `[""]` | auto-filled |

All other fields (`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan.tier`, `test_plan.cases`) were populated with real content by Plan-2-Tasks — no human-review flags.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 8 |
| Cases covered by existing tests | 0 |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 8 |
| New stub files created | 3 |
| Total new stubs generated | 8 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `test_artifacts`, `verification_commands` (all 3 tasks) |

## Existing Test Coverage Found

None. Explicit dynamics is a greenfield subsystem — no pre-existing tests overlap P7 scope.

## Stub files created

| Task ID | File | Stubs | Tier |
|---------|------|-------|------|
| P7-1 | `packages/mechdsl-core/tests/test_explicit_integrator.py` | 3 | unit |
| P7-2 | `packages/mechdsl-core/tests/test_critical_timestep.py` | 3 | unit |
| P7-3 | `packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py` | 2 | integration (also `@slow`) |

### Stub → AC mapping

**P7-1** (`@pytest.mark.unit`)
- `test_lumped_mass_matches_consistent_row_sum` — AC1 (row-sum within 1e-12)
- `test_central_difference_single_step_matches_hand_calc` — AC2 (single-step hand-calc match)
- `test_explicit_static_emission_differs` — AC3 (EXPLICIT vs STATIC emission differs)

**P7-2** (`@pytest.mark.unit`)
- `test_unit_cube_hex8_dt_matches_analytical` — AC1 (unit cube dt = L/c_d within 1e-8)
- `test_irregular_mesh_dt_below_element_min` — AC2 (irregular mesh dt safety)
- `test_safety_factor_applied` — AC3 (default safety 0.9)

**P7-3** (`@pytest.mark.slow` + `@pytest.mark.integration`)
- `test_free_vibration_first_mode_period_within_1_percent` — AC1 (1% frequency match)
- `test_explicit_implicit_quasistatic_equilibrium_matches_within_1e6` — AC2 (cross-check within 1e-6)

## Tasks Needing Human Review Before Execute

None. All three tasks are fully scaffolded.

## Ready for Execute

Fully scaffolded (ready for `Aut_Faciam exec 7 dev/design_docs/PLAN-B.md`):
- P7-1: Lumped mass + central difference integrator
- P7-2: Critical time step computation
- P7-3: Free vibration + explicit/implicit cross-check (Phase 7 exit)

## Phase 7 risk carry-forward (from Phase 6 handoff and plan)

1. **No damage-aware tangent coupling needed** — explicit dynamics is matrix-free, so the P6-2 Option-A undamaged J2 tangent carry-forward is inert in Phase 7. Relevant again in P10-7 Taylor impact (implicit + damage).
2. **Hex20 / Tet10 mass lumping is out of scope** — stub `raise NotImplementedError` and flag as post-MVP follow-up (per `Phase_7_context_summary.md` Allowed Deviations).
3. **dt_crit is state-dependent** under nonlinear materials — P7-2 scope says recompute every N=100 steps in the emitted driver.
4. **Quasi-static cross-check needs mass scaling** (~1e6) to finish in wall-clock; document in P7-3 test.
5. **Integration-break hazard (Phase 5 precedent ×3):** `mechanics_ir.py` gets a new `DynamicsMode` field — any strict-key guards in `test_mechanics_ir.py` may need Lemaitre-style updates. Flag for P7-1 implementer.

## Phase 7 exit criterion (Plan B line 219)

Free vibration period within 1%. Asserted in P7-3 test 1.
