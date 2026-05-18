# Phase 6 Context Summary: Continuum damage

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B6 Continuum damage

## Conventions

- Damage variable `D ∈ [0, 1)`, element-deletion threshold `D_crit` (default 0.95).
- State variables: `(alpha, D)` — plastic strain and damage, both per quadrature point.
- Effective stress principle: `σ_eff = σ / (1 − D)`. All plastic return mapping runs on the effective stress, then damage evolves after.
- Energy release rate `Y = σ_eq² R_v / (2 E (1 − D)²)` where `R_v` is the triaxiality factor (standard Lemaitre form).

## Key Principles

- **D = 0 is a regression guard.** At zero damage, Lemaitre must reproduce Plan A `j2_power_law` byte-for-byte. Every test covering this path is a regression test for BOTH models, not just Lemaitre.
- **D is monotonically non-decreasing** under monotonic plastic loading. Enforce this as an invariant in every unit test.
- **Element deletion is a per-element binary switch** on a new `is_deleted` field. Deleted elements contribute zero to force and tangent; they do NOT re-activate even if the damage equation would allow it.
- **Damage localises at geometric singularities.** The classical Lemaitre model is mesh-dependent at localisation sites; this is a known pathology, not a bug. Nonlocal regularisation is out of scope for Plan B.
- **(1 − D) divisor is numerically fragile** as D → 1. Clamp `D < 1 − 1e-6` and mark the element for deletion before the divisor explodes.

## Pre-resolved Design Decisions

- Lemaitre couples to J2 power-law plasticity (Plan A), NOT to Perzyna or Johnson-Cook. Rate-dependent damage is a post-MVP follow-up.
- `is_deleted` is a per-element Taichi field of type `ti.i32` (0 or 1), allocated alongside the history fields.
- Element deletion is detected at the end of each `compute_internal_force` call; the next Newton iteration sees the element as deleted.
- Damage threshold `eps_D` means no damage occurs until plastic strain exceeds this value.

## Allowed Deviations

- Mesh-dependence of damage localisation is expected and documented. The notched bar benchmark uses a fixed mesh density matched to the literature reference.

## Downstream Impact

- **P10-8 notched bar benchmark** is the full benchmark version of P6-3's unit verification. Same problem, different reference data.
- Phase 8 (MFEM/MOOSE) must emit the Lemaitre damage model in both backends.
- Phases 3 and 6 are independent: Lemaitre does not depend on viscoplasticity.
