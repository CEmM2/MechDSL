# Handoff: Phase 6 → Phase 7

**From:** Phase 6 — Continuum damage (Lemaitre CDM)
**To:** Phase 7 — Explicit dynamics (central-difference time integrator)
**Date:** 2026-04-17
**Phase 6 branch:** `plan-b_phase-6` (off `plan-b_phase-5` tip; Phase 5 not yet merged to main)
**Phase 6 commits:** `d18e945` (P6-1), `cdaba86` (P6-2), `3fcc072` (P6-3), plus tracking commits
**Phase 6 exit baseline:** 1215 passed / 1 skipped / 0 failed in fast suite

---

## What Phase 6 shipped

| Task | Title | Commit | Deliverables |
|------|-------|--------|--------------|
| P6-1 | Lemaitre damage variable + evolution equation | `d18e945` | `symbolic/models/lemaitre.py` (375 lines), `tests/test_lemaitre_evolution.py` (11/11 pass) |
| P6-2 | Plasticity coupling + element deletion at D > D_crit | `cdaba86` | `solver/history_fields.py`, `codegen/taichi_printer.py`, whitelist additions in frontend/ir/lowering, `tests/test_lemaitre_codegen.py` (3/3 pass) |
| P6-3 | D=0 regression + notched bar verification | `3fcc072` | `tests/test_lemaitre_acceptance.py` (2/2 @slow pass) — **Phase 6 exit** |

### Acceptance evidence

- **D=0 regression** (non-isotropic state): `max|u_lemaitre − u_j2_power_law| = 3.75e-16` (7+ orders of magnitude below the 1e-8 spec tolerance). Confirms Lemaitre exactly reduces to Plan A J2 power-law at zero damage.
- **Notched bar damage localisation**: `argmax(D)` at element 14 (geometrically-nearest to notch root `[3.0, 2.25, 0.5]`); damage drop-off 7.5× from notch root to far end of bar; `D_max ≈ 6.23e-2` at 2% strain under linear hardening.
- **Element deletion wiring**: `is_deleted` field + `D > D_crit` one-way deletion verified structurally in both `compute_internal_force` and `tangent_matvec` kernels.

### Model coverage after Phase 6

| Material model | Status |
|----------------|--------|
| St. Venant–Kirchhoff | MVP |
| J2 power-law | MVP |
| Neo-Hookean, Mooney–Rivlin, Ogden, HGO | Plan B Phase 4 |
| Perzyna, Johnson–Cook viscoplasticity | Plan B Phase 3 |
| **Lemaitre CDM** | **Plan B Phase 6** ✅ |

---

## Known trade-offs carried forward

These are **not blockers** — they are documented design choices to address in later phases.

### 1. Undamaged J2 tangent under active damage (Option A)

- **Where:** `codegen/taichi_printer.py` `tangent_matvec` — uses `constitutive_update_plastic` (J2) even in the Lemaitre branch. `(1 − D)` scaling and `∂D/∂ε` cross-term are **not** baked into the algorithmic tangent.
- **Why:** full damage-aware consistent tangent is ~300 extra emitted lines and would need its own verification pass. Deferred to keep P6-2 scope tight.
- **Impact:** Newton convergence degrades from super-linear (quadratic with consistent tangent) to sub-linear when damage is actively evolving. Mitigation in P6-3: small strain increments (≤0.5%/step) + `max_iter=40` Newton budget.
- **Phase 7 impact:** none (explicit dynamics doesn't use a tangent).
- **Phase 10 action:** P10-7 Taylor impact acceptance test needs the damage-aware tangent; consider `C_alg^damaged = (1 − D) · C_alg^J2 − (∂D/∂ε) ⊗ σ_eff` or implicit-explicit partitioning.

### 2. Notched-bar acceptance uses linear hardening (`n_hard=1.0`)

- **Where:** `tests/test_lemaitre_acceptance.py::test_notched_bar_damage_localises_at_notch_root`.
- **Why:** the MVP power-law tangent has an `n · α^(n−1)` factor that blows up at small α in early time-steps when Newton overshoots (sub-linear convergence amplifies the issue). Linear hardening keeps the tangent non-singular.
- **Gap:** **full power-law nonlinearity is never exercised under active damage in any acceptance test.** D=0 regression has power-law but no damage; notched bar has damage but linear hardening.
- **Phase 10 action:** add a companion acceptance test once the damage-aware tangent lands.

### 3. Silent emit-time defaults for damage parameters

- **Where:** `codegen/taichi_printer.py::emit_main` calls `params.get('S_d', 1.0)`, `params.get('s_d', 1.0)`, `params.get('eps_D', 0.0)`, `params.get('D_crit', 0.95)`.
- **Impact:** a ProblemIR missing these params silently compiles with arbitrary defaults (e.g. `eps_D=0` triggers damage from first plastic step).
- **Workaround in P6-3 tests:** all damage parameters passed explicitly.
- **Action:** consider emit-time validation at the start of Phase 7 or Phase 10, or an IR-level validation pass.

### 4. Damage localisation is mesh-dependent (classical CDM pathology)

- **Documented in:** `dev/design_docs/PLAN-B.md` §B6 and P6-3 test docstrings.
- **Deferred to:** Phase 9 / P10 V&V — nonlocal or gradient regularisation. Reference implementation options: Bazant-Jirasek integral nonlocal or Peerlings-type gradient-enhanced damage.

### 5. `HistoryFields` dtype asymmetry for `is_deleted`

- Python-side `HistoryFields.register` uses hard-coded `np.float64` for all fields; Taichi-side `is_deleted` field declared `ti.i32`. Boolean comparisons use `!= 0` consistently so no runtime hazard, but cross-layer inspection (e.g. comparing `is_deleted_np` from Taichi vs `history.get_current("is_deleted")` from Python) is dtype-asymmetric.
- **Fix opportunity:** `HistoryFields.register` could accept a `dtype` argument. Small refactor, any phase.

---

## Phase 7 scope at a glance (Plan B §B7)

- Central-difference explicit time integrator for dynamics.
- Lumped mass matrix + critical time-step estimator.
- Contact-free (contact is a separate later phase, or omitted from Plan B entirely).
- Taylor-impact acceptance test is **Phase 10** (P10-7), not Phase 7. Phase 7 provides the engine; Phase 10 does the V&V.

### Implications of Phase 6 choices for Phase 7

1. **Element deletion works via `is_deleted[e]` one-way switch.** Phase 7 explicit dynamics kernels must honour the same skip-if-deleted guard. The pattern is already established in `compute_internal_force`.
2. **`damage_D` is a per-QP history field.** Explicit-dynamics update loops must read-modify-write `damage_D[e, q]` atomically per element (no issue in practice — elements are the Taichi parallel axis).
3. **No tangent needed** in explicit dynamics — the Option-A undamaged-tangent compromise is invisible here. Phase 7 gets a free ride on that front.
4. **Critical time-step estimator** should include elastic wave speed `c = sqrt(λ+2μ)/ρ)` — if Lemaitre material is in play, the effective stiffness is `(1−D)·C`, so `c_eff = c_0 · sqrt(1−D)`. For D = 0.95, c drops to ~22% of undamaged → the time-step estimator must use the *current* D, not the reference stiffness. Flag this for the P7 implementer.
5. **Element deletion mid-step**: in explicit dynamics, deleting an element within a step leaves a hole in the mass matrix. Usually handled by zeroing the element's contribution to the nodal inertia and letting nodes not shared with live elements stay in place (the solver harness already tracks Dirichlet DoFs; deleted-element free nodes should be pinned or removed from the active set).

---

## Recommended next action

Run `Aut_Faciam scaffold 7 dev/design_docs/PLAN-B.md` to scaffold Phase 7 from the current `plan-b_phase-6` tip (branch off as `plan-b_phase-7`).

**Before scaffolding:** decide whether to merge Phase 5 and Phase 6 to main now or keep stacking branches. Stacking has worked so far, but the tree is now four branches deep off main.

---

## File index (Phase 6 deliverables)

### Source
- `packages/mechdsl-core/src/mechdsl/symbolic/models/lemaitre.py`
- `packages/mechdsl-core/src/mechdsl/solver/history_fields.py` (extended)
- `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` (extended: Lemaitre branch)
- `packages/mechdsl-core/src/mechdsl/frontend/__init__.py` (whitelist)
- `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py` (whitelist)
- `packages/mechdsl-core/src/mechdsl/lowering/fe_localise.py` (whitelist)

### Tests
- `packages/mechdsl-core/tests/test_lemaitre_evolution.py` (11 unit tests)
- `packages/mechdsl-core/tests/test_lemaitre_codegen.py` (3 integration tests)
- `packages/mechdsl-core/tests/test_lemaitre_acceptance.py` (2 @slow acceptance tests)

### Tracking
- `dev/tasks/PLAN-B/json/P6-1.json`, `P6-2.json`, `P6-3.json` (all status=done)
- `dev/tasks/PLAN-B/gates/phase_6_gates.md` (9 gate entries, all PASS)
- `dev/tracking/tasks-tracker_PLAN-B.md` (P6 rows updated)
- GitHub: #61 (phase) closed with all tasks checked off; #96, #97, #98 closed.
