# Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-15
This tracker records execution status for the PLAN-B task set.

## PLAN-B Tracker

Plan source: `dev/design_docs/PLAN-B.md`
Task index: `dev/tasks/PLAN-B/all-tasks.md`

**Phase-ID mapping:** Plan B uses B-prefixed sub-section numbering; Aut_Faciam uses sequential integers. See `all-tasks.md` for the mapping. Task IDs follow the `P<phase>-<seq>` pattern — e.g. `P1-1` is Phase 1 (B1 Updated Lagrangian) task 1.

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | ConfigurationIR extension | done |  | — | P1-2, P1-3, P1-4, P1-5, P2-1, P3-1, P4-1, P4-2, P4-3, P4-4, P5-1, P5-2, P5-3, P5-4, P6-1, P7-1, P8-1, P8-2 | 48-55 | 07ed832 | tests/test_mechanics_ir_configuration.py, tests/test_symbolic_ir_interface.py::TestFormulationGuard, tests/test_mechanics_ir.py::TestInvalidFormulation, tests/test_localise.py::TestIncompatibleFormulation, tests/test_frontend_build_context.py, tests/test_frontend_parser.py, tests/test_documentation.py::TestTaskP5T5 | 2026-04-15 |
| P1-2 | UL kinematics (spatial shape gradients) | done |  | — | P1-3, P1-4 | 25-36 | c9f980e | tests/test_kinematics_ul.py | 2026-04-15 |
| P1-3 | UL residual emission | done |  | — | P1-4, P1-6 | 27-36 | a364b4b | tests/test_taichi_printer_ul.py::TestTaskP1_3InternalForce, tests/test_codegen.py::TestGoldenSnapshot | 2026-04-16 |
| P1-4 | UL tangent operator emission | done |  | — | P1-6 | 38-46 | 39b5ff6 | tests/test_taichi_printer_ul.py::TestTaskP1_4TangentMatvec, tests/test_emission_verification.py::TestTangentMatvecEmission | 2026-04-16 |
| P1-5 | Objective stress rates | done |  | — | P1-4, P1-7 | 56-65 | 82f3d4a + 70ca2b7 (follow-up) | tests/test_objective_rates.py | 2026-04-15 (follow-up 2026-04-16) |
| P1-6 | Formulation switching (directive + codegen) | done |  | — | P1-7 | 66-70 | 49ebdcd | tests/test_formulation_switching.py, tests/test_frontend_build_context.py, tests/test_frontend_parser.py, tests/test_symbolic_ir_interface.py::TestFormulationGuard | 2026-04-16 |
| P1-7 | TL/UL equivalence + rigid rotation tests | done |  | — | P10-2, P10-3, P10-7 | 70-72 | ec6ca2e | tests/test_ul_equivalence.py, tests/ref/ref_hex8_ul.py, tests/test_taichi_printer_ul.py::test_ul_tangent_matches_handwritten_reference | 2026-04-16 |
| P2-1 | Covariant/contravariant bases + metrics | done |  | — | P2-2, P2-4 | 82-94 | 4d287ae | tests/test_convected_curvilinear.py::TestTaskP2_1MetricTensors (6), tests/test_convected.py (8) | 2026-04-16 |
| P2-2 | Christoffel symbols | done |  | P2-1 | P2-3, P2-4 | 95-99 | d41f70d | tests/test_convected_curvilinear.py::TestTaskP2_2ChristoffelSymbols (4) | 2026-04-16 |
| P2-3 | Covariant derivatives | done |  | P2-2 | P2-5 | 101-106 | c469c7c | tests/test_convected_curvilinear.py::TestTaskP2_3CovariantDerivatives (4) | 2026-04-16 |
| P2-4 | NRPyLaTeX metric-assign directives | done |  | P2-1, P2-2 | P2-5 | 107-112 | edaf84c | tests/test_metric_assign_directives.py (5+1skip), tests/test_frontend_parser.py | 2026-04-16 |
| P2-5 | Curvilinear patch test + Cartesian equivalence | done |  | — | P10-1 | 114-119 | d2a4bf9 | tests/test_convected_patch.py::TestTaskP2_5CurvilinearPatchTest (2) | 2026-04-16 |
| P3-1 | Perzyna viscoplasticity | done |  | — | P3-2, P3-3 | 127-129 | 9e0baa6 + follow-up | tests/test_perzyna.py::TestTaskP3_1PerzynaReturnMap (4), tests/test_perzyna.py (21 total), tests/test_j2.py (28) | 2026-04-17 |
| P3-2 | Johnson-Cook flow stress + thermal | done |  | — | P3-3, P3-4 | 131-133 | 5e9efc4 + 3afcc7f (Gate B fix) | tests/test_johnson_cook.py::TestTaskP3_2JohnsonCookReturnMap (4), tests/test_johnson_cook.py (38 total), tests/test_j2.py (28) | 2026-04-17 |
| P3-3 | Consistent viscoplastic tangent | done |  | — | P3-4 | 135-137 | 8101a14 | tests/test_perzyna.py::TestTaskP3_3PerzynaTangent (4), tests/test_johnson_cook.py::TestTaskP3_3JohnsonCookTangent (3), tests/test_j2.py (28 regression) | 2026-04-17 |
| P3-4 | Rate / quasi-static / thermal verification | done |  | — | P10-7 | 139-143 | e659d5d | tests/test_viscoplastic_acceptance.py::TestTaskP3_4ViscoplasticAcceptance (5), full mechdsl-core fast sweep (1115 passed) | 2026-04-17 |
| P4-1 | Neo-Hookean | done |  | — | P4-5, P10-2 | 152-152 | 6ab8bd3 | tests/test_neo_hookean.py::TestTaskP4_1NeoHookean (9 passed) | 2026-04-17 |
| P4-2 | Mooney-Rivlin | done |  | — | P4-5 | 153-153 | <pending> | tests/test_mooney_rivlin.py::TestTaskP4_2MooneyRivlin (9 passed), full fast suite 1127 passed | 2026-04-17 |
| P4-3 | Ogden (with eigendecomposition) | done |  | — | P4-5 | 154-154 | bb9900a | tests/test_ogden.py::TestTaskP4_3Ogden (9 passed), full fast suite 1136 passed | 2026-04-17 |
| P4-4 | HGO anisotropic (fiber directions) | done |  | — | P4-5, P10-9 | 155-155 |  | tests/test_hgo.py::TestTaskP4_4HGO | 2026-04-17 |
| P4-5 | AD oracle + uniaxial for all hyperelastics | done |  | P4-1, P4-2, P4-3, P4-4 | — | 157-161 |  | tests/test_hyperelastic_uniaxial.py::TestTaskP4_5HyperelasticAcceptance | 2026-04-17 |
| P5-1 | Tet4 element | done |  | — | P5-6, P5-7 | 171-171 | 5a248ca | tests/test_tet4_basis.py (4/4) | 2026-04-17 |
| P5-2 | Tet10 element | done |  | — | P5-6, P5-7, P10-2, P10-3 | 172-172 | 3549830 | tests/test_tet10_basis.py (4/4) | 2026-04-17 |
| P5-3 | Hex20 element | done |  | — | P5-6, P5-7, P10-2, P10-5 | 173-173 | 37e087c | tests/test_hex20_basis.py (4/4) | 2026-04-17 |
| P5-4 | Hex8 reduced integration | done |  | — | P5-5, P5-6, P10-7 | 174-174 | 93b9d9d | tests/test_hex8_reduced.py (3/3) | 2026-04-17 |
| P5-5 | Flanagan-Belytschko hourglass control | done |  | — | P5-6, P5-7, P10-7 | 174-174 | 02c575e | tests/test_hourglass_control.py (4/4) | 2026-04-17 |
| P5-6 | ElementFactory | done |  | — | P5-7, P9-1 | 176-183 | 5b668ca | tests/test_element_factory.py (10/10) | 2026-04-17 |
| P5-7 | Patch tests for all elements + hourglass | done |  | — | P9-1, P10-1 | 185-185 | 21d0e2b | tests/test_patch_test_all_elements.py (5/5), tests/test_hourglass_suppression.py (2/2) | 2026-04-17 |
| P6-1 | Lemaitre damage variable + evolution | done |  | — | P6-2 | 193-193 | d18e945 | tests/test_lemaitre_evolution.py (11/11) | 2026-04-17 |
| P6-2 | Damage plasticity coupling + element deletion | done |  | — | P6-3 | 193-193 | cdaba86 | tests/test_lemaitre_codegen.py (3/3) | 2026-04-17 |
| P6-3 | D=0 regression + notched bar | done |  | — | P10-8 | 196-199 | 3fcc072 | tests/test_lemaitre_acceptance.py (2/2) | 2026-04-17 |
| P7-1 | Lumped mass + central difference | done |  | — | P7-2 | 210-211 | 83d722f | tests/test_explicit_integrator.py (3/3) | 2026-04-17 |
| P7-2 | Critical time step computation | done |  | P7-1 | P7-3 | 211-211 | be28b80 | tests/test_critical_timestep.py (3/3) | 2026-04-17 |
| P7-3 | Free vibration + explicit/implicit cross-check | done |  | P7-2 | P10-7 | 213-217 | a381e07 | tests/test_explicit_dynamics_acceptance.py (2/2 @slow) | 2026-04-17 |
| P8-1 | MFEM printer | done |  | — | P8-3, P9-1 | 227-229 | a5c14f3 + bdfbe1a (Gate B fix) | tests/test_mfem_printer.py (11/11) | 2026-04-17 |
| P8-2 | MOOSE printer | done |  | — | P8-3, P9-1 | 231-233 | af370da | tests/test_moose_printer.py (8/8) | 2026-04-17 |
| P8-3 | Cross-backend verification | done |  | — | P9-1 | 235-237 | 2fd7d78 + 87f2cd2 + 4733e3f (Gate B fixes) | tests/test_cross_backend.py (3/3 skip-clean) | 2026-04-17 |
| P9-1 | Named contraction-family template design | done |  | — | P9-2 | 244-249 | 6480434 | tests/test_p9_1_family_spec_completeness.py (3/3); spec patch applied to dev/design_docs/09-EINSUM-OPTIMISER.md §9 | 2026-04-17 |
| P9-2 | Refactor einsum_optimizer for family emission | done | 1 | P9-1 | P9-3 | 247-249 | plan-b_phase-9 | tests/test_p9_2_family_emitters.py (4/4); dispatch reachable Taichi 945/996/1067/1165, MFEM 471/493/590, MOOSE 445/471; flag-OFF byte-identical; _dispatch_family emits DEBUG on fallback | 2026-04-18 |
| P9-3 | Budget regression across all (elt × backend) | done | 0 | P9-2 | P10-1 | 249-249 | plan-b_phase-9 | tests/test_template_family_budget.py (32 active / 80 skipped, all realisable HEX8 triples pass budget; family/tier ratio 0.9009-1.0761, all < 1.2×); golden at tests/golden/template_family_emission_baseline.json; regen script at tests/tools/regen_p9_3_baseline.py | 2026-04-18 |
| P10-1 | MMS convergence study matrix | done |  | — | P10-10 | 257-259 | ph10_preq PR #122 (work/phase10-e6-generalized-mms) | tests/test_mms_convergence_matrix.py (10/10 pass; matrix covers Hex8/Tet10/Hex20×SVK + Hex8×{J2/Perzyna/Lemaitre} via elastic_regime_interpolation policy) | 2026-04-26 |
| P10-2 | Cantilever benchmark (12 cells) | done |  | — | P10-10 | 264-264 | ph10_preq PR #122 (work/phase10-e3-public-cantilever) | tests/test_benchmarks_cantilever_matrix.py (15/15 pass; 12-cell matrix at smoke profile, 40×8×4 preserved on CantileverParameters.nightly()) | 2026-04-26 |
| P10-3 | Cook's membrane benchmark (TL × J2 × Hex8) | done |  | — | P10-10 | 265-265 | uncommitted | tests/test_benchmarks_cook_membrane_matrix.py (2/2 pass); tests/test_benchmarks.py -k cook (4/4 pass) | 2026-04-23 |
| P10-4 | Thick cylinder (Lamé) benchmark | done | 2026-04-18 | P1-7 | P10-10 | 266-266 | 2/2 pass | tests/test_thick_cylinder.py (u_r 0.81%, sigma_tt 1.75% vs Lamé) | plan-b_phase-10 |
| P10-5 | Plate with hole (Kirsch K_t=3) benchmark | done |  | P5-3 | P10-10 | 267-267 | uncommitted | tests/test_plate_with_hole.py (2/2 pass; Hex20 K_t~=3.11, Hex8 K_t~=2.66) | 2026-04-23 |
| P10-6 | Necking bar (Simo & Hughes) benchmark | done | 2026-04-18 | P1-7 | P10-10 | 268-268 | 2/3 pass, 1 skip | tests/test_benchmarks_necking_bar_matrix.py (TL within 2% of Simo-Hughes; UL deferred — no UL+J2 ref kernel) | plan-b_phase-10 |
| P10-7 | Taylor impact benchmark | done |  | — | P10-10 | 269-269 | ph10_preq PR #122 (work/phase10-e8-public-taylor-benchmark) | tests/test_taylor_impact.py (6/6 pass; Path A frozen-reference regression — final length 5%, mushroom diameter 5%, peak PEEQ 10%) | 2026-04-26 |
| P10-8 | Notched bar (Lemaitre) benchmark | done | 2026-04-18 | P6-3 | P10-10 | 270-270 | 3/3 pass | tests/test_notched_bar_benchmark.py (load-disp within 10% self-consistent ref; damage at notch root) | plan-b_phase-10 |
| P10-9 | Fiber-reinforced strip (HGO) benchmark | done | 2026-04-18 | P4-4 | P10-10 | 271-271 | 4/4 pass | tests/test_hgo_benchmark.py (long + trans stress rel-err ~1e-10 vs HGO closed-form; stiffness ratio 386.6) | plan-b_phase-10 |
| P10-10 | Performance + nightly CI harness | done |  | — | — | 273-276 | ph10_preq PR #122 (work/phase10-e9-perf-harness) + closure on SOSOVSKI/plan-b-ph10-exec | tests/test_perf_regression.py (4/4 pass; .github/workflows/nightly.yml + tests/golden/perf/baseline_smoke.json + mechdsl.verify.perf.run_compare CLI; cron policy-disabled per feedback_ci_manual_dispatch) | 2026-04-26 |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

**Scaffolded:** 2026-04-15 — 6 stub files created, 28 stub test cases generated across 7 tasks. See `dev/tasks/PLAN-B/Phase_1_Scaffold_Validation.md` for the full scaffold report.

#### Phase 1 mapping between test and task:

| Task ID | Title | Primary stub file | Regression / existing coverage | Tier |
|---|---|---|---|---|
| P1-1 | ConfigurationIR extension | tests/test_mechanics_ir_configuration.py | tests/test_symbolic_ir_interface.py::TestFormulationGuard (update), tests/test_mechanics_ir.py (regression) | unit |
| P1-2 | UL kinematics | tests/test_kinematics_ul.py | tests/test_kinematics.py (identity/inverse reference path) | unit |
| P1-3 | UL residual emission | tests/test_taichi_printer_ul.py::TestTaskP1_3InternalForce | tests/test_emission_verification.py::TestInternalForceEmission, tests/golden/generated_elastic.py.golden, generated_plastic.py.golden | unit |
| P1-4 | UL tangent emission | tests/test_taichi_printer_ul.py::TestTaskP1_4TangentMatvec | tests/test_emission_verification.py::TestTangentMatvecEmission, tests/test_plastic_emission.py | unit |
| P1-5 | Objective stress rates | tests/test_objective_rates.py | (none — new area) | unit |
| P1-6 | Formulation switching | tests/test_formulation_switching.py | tests/test_frontend_build_context.py::test_formulation_updated_lagrangian_raises_unsupported_error (invert), tests/test_frontend_parser.py::test_updated_lagrangian_rejected_with_plan_b1 (invert), tests/test_symbolic_ir_interface.py::TestFormulationGuard | integration |
| P1-7 | TL/UL equivalence + rigid rotation | tests/test_ul_equivalence.py | tests/test_ref_elastic.py (reference pattern), tests/ref/ref_hex8_elastic.py (template for ref_hex8_ul.py) | integration |

#### Verification outcomes:

- `uv run pytest packages/mechdsl-core/tests/test_mechanics_ir_configuration.py packages/mechdsl-core/tests/test_kinematics_ul.py packages/mechdsl-core/tests/test_taichi_printer_ul.py packages/mechdsl-core/tests/test_objective_rates.py packages/mechdsl-core/tests/test_formulation_switching.py packages/mechdsl-core/tests/test_ul_equivalence.py --collect-only -q` -> 28 stubs collected (2026-04-15)
- `uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" -v` -> pending (run after P1-1 ... P1-7 land)
- **P1-1 (done, 2026-04-15, `07ed832`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1005 passed, 21 skipped, 0 failed**; task-scoped `test_mechanics_ir_configuration.py + TestFormulationGuard` -> **9 passed, 0 failed**.
- **P1-2 (done, 2026-04-15, `c9f980e`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1009 passed, 17 skipped, 0 failed** (27.20s); task-scoped `test_kinematics_ul.py -v` -> **4 passed, 0 failed**.
- **P1-5 (done, 2026-04-15, `82f3d4a`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1013 passed, 13 skipped, 0 failed** (24.02s); task-scoped `test_objective_rates.py -v` -> **4 passed, 0 failed**.
- **P1-5 follow-up (2026-04-16, `70ca2b7`):** closed Gate B m2 (full-F Piola push-forward in `truesdell_tangent`); added module-level out-of-scope marker for direct rate functions. `uv run pytest -m 'not slow and not gpu'` -> **1016 passed, 13 skipped, 0 failed** (23.42s); task-scoped `test_objective_rates.py -v` -> **7 passed, 0 failed** (4 original + 3 new). Review score 8 -> 9.
- **P1-3 (done, 2026-04-16, `a364b4b`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1020 passed, 10 skipped, 0 failed** (23.52s); task-scoped `test_taichi_printer_ul.py::TestTaskP1_3InternalForce -v` -> **4 passed, 0 failed**; TL goldens -> **3/3 passed**. Review score 10/10.
- **P1-4 (done, 2026-04-16, `39b5ff6`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1023 passed, 7 skipped, 0 failed** (17.87s); task-scoped `TestTaskP1_4TangentMatvec` -> **3 passed, 1 skipped** (P1-7 deferred). Review score 10/10.
- **P1-6 (done, 2026-04-16, `49ebdcd`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1027 passed, 4 skipped, 0 failed** (18.16s); task-scoped `test_formulation_switching.py` -> **4 passed, 0 failed**; verification commands -> **58/58 passed**. Review score 10/10.
- **P1-7 (done, 2026-04-16, `ec6ca2e`):** `uv run pytest packages/mechdsl-core/tests/ -m 'not slow and not gpu'` -> **1031 passed, 0 skipped, 0 failed** (19.56s); task-scoped `test_ul_equivalence.py -v` -> **4 passed, 0 failed** (incl. slow cantilever 2.97s); P1-4 deferred stub resolved -> **1 passed**. Review score 10/10. **Phase 1 complete — zero remaining skips.**

### Phase 2 aggregate verification:

**Scaffolded:** 2026-04-16 — 3 stub files created, 19 stub test cases generated across 5 tasks. See `dev/tasks/PLAN-B/Phase_2_Scaffold_Validation.md` for the full scaffold report.

#### Phase 2 mapping between test and task:

| Task ID | Title | Primary stub file | Regression / existing coverage | Tier |
|---|---|---|---|---|
| P2-1 | Covariant bases + metrics | tests/test_convected_curvilinear.py::TestTaskP2_1MetricTensors | tests/test_convected.py (Cartesian path regression) | unit |
| P2-2 | Christoffel symbols | tests/test_convected_curvilinear.py::TestTaskP2_2ChristoffelSymbols | (none — new area) | unit |
| P2-3 | Covariant derivatives | tests/test_convected_curvilinear.py::TestTaskP2_3CovariantDerivatives | (none — new area) | unit |
| P2-4 | NRPyLaTeX metric-assign | tests/test_metric_assign_directives.py::TestTaskP2_4MetricAssignDirectives | tests/test_frontend_parser.py (parser regression) | integration |
| P2-5 | Curvilinear patch + equivalence | tests/test_convected_patch.py::TestTaskP2_5CurvilinearPatchTest | tests/test_convected.py, tests/test_kinematics.py::TestConvectedMetric | integration |

#### Verification outcomes:

- `uv run pytest packages/mechdsl-core/tests/test_convected_curvilinear.py packages/mechdsl-core/tests/test_metric_assign_directives.py packages/mechdsl-core/tests/test_convected_patch.py --collect-only -q` -> 19 stubs collected (2026-04-16)
- **P2-1 (done, 2026-04-16, `4d287ae`):** Gate A fail (test_gap: curvilinear branch untested) → pass. Gate B fail (physics_error: F^T G F wrong formula) → pass. Gate C pass. 1038 passed, 13 skipped.
- **P2-2 (done, 2026-04-16, `d41f70d`):** All 3 gates first attempt. 1042 passed, 9 skipped. Review score 9/10.
- **P2-3 (done, 2026-04-16, `c469c7c`):** All 3 gates first attempt. 1052 passed, 1 skipped. Review score 10/10.
- **P2-4 (done, 2026-04-16, `edaf84c`):** All 3 gates first attempt. 1052 passed, 1 skipped. Review score 9/10.
- **P2-5 (done, 2026-04-16, `d2a4bf9`):** Gate A fail (misunderstanding: FEM solve out of scope) → pass. Gate B fail (test_gap: theta=0 only) → pass (theta sweep added). Gate C pass. 1055 passed, 1 skipped, 0 failed. Review score 9/10. **Phase 2 complete — exit criterion met.**

### Phase 3 aggregate verification:

**Scaffolded:** 2026-04-16 — 3 stub files created, 17 stub test cases generated across 4 tasks. See `dev/tasks/PLAN-B/Phase_3_Scaffold_Validation.md` for the full scaffold report.

#### Phase 3 mapping between test and task:

| Task ID | Title | Primary stub file | Regression / existing coverage | Tier |
|---|---|---|---|---|
| P3-1 | Perzyna model | tests/test_perzyna.py::TestTaskP3_1PerzynaReturnMap | tests/test_j2.py (J2 reference for rate-independent limit) | unit |
| P3-2 | Johnson-Cook model | tests/test_johnson_cook.py::TestTaskP3_2JohnsonCookReturnMap | tests/test_j2.py (J2 reference for baseline match) | unit |
| P3-3 | Consistent viscoplastic tangent | tests/test_perzyna.py::TestTaskP3_3PerzynaTangent, tests/test_johnson_cook.py::TestTaskP3_3JohnsonCookTangent | (none — new area) | unit |
| P3-4 | Rate / quasi-static / thermal | tests/test_viscoplastic_acceptance.py::TestTaskP3_4ViscoplasticAcceptance | (none — acceptance suite) | unit |

#### Verification outcomes:

- `uv run pytest packages/mechdsl-core/tests/test_perzyna.py packages/mechdsl-core/tests/test_johnson_cook.py packages/mechdsl-core/tests/test_viscoplastic_acceptance.py --collect-only -q` -> 17 stubs collected (2026-04-16)

### Phase 4 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P4-1 | Neo-Hookean | tests/test_neo_hookean.py |
| P4-2 | Mooney-Rivlin | tests/test_mooney_rivlin.py |
| P4-3 | Ogden | tests/test_ogden.py |
| P4-4 | HGO | tests/test_hgo.py |
| P4-5 | AD oracle + uniaxial | tests/test_hyperelastic_uniaxial.py |

#### Verification outcomes:

- `uv run pytest packages/mechdsl-core/tests/test_neo_hookean.py packages/mechdsl-core/tests/test_mooney_rivlin.py packages/mechdsl-core/tests/test_ogden.py packages/mechdsl-core/tests/test_hgo.py packages/mechdsl-core/tests/test_hyperelastic_uniaxial.py --collect-only -q` -> 22 stubs collected (2026-04-17)

### Phase 5 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P5-1 | Tet4 | tests/test_tet4_basis.py |
| P5-2 | Tet10 | tests/test_tet10_basis.py |
| P5-3 | Hex20 | tests/test_hex20_basis.py |
| P5-4 | Hex8 reduced | tests/test_hex8_reduced.py |
| P5-5 | Hourglass control | tests/test_hourglass_control.py |
| P5-6 | ElementFactory | tests/test_element_factory.py |
| P5-7 | Patch tests for all | tests/test_patch_test_all_elements.py, test_hourglass_suppression.py |

### Phase 6 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P6-1 | Lemaitre variable + evolution | tests/test_lemaitre_evolution.py |
| P6-2 | Coupling + element deletion | tests/test_lemaitre_codegen.py |
| P6-3 | D=0 regression + notched bar | tests/test_lemaitre_acceptance.py |

### Phase 7 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P7-1 | Lumped mass + central diff | tests/test_explicit_integrator.py |
| P7-2 | Critical time step | tests/test_critical_timestep.py |
| P7-3 | Free vibration + cross-check | tests/test_explicit_dynamics_acceptance.py |

### Phase 8 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P8-1 | MFEM printer | tests/test_mfem_printer.py |
| P8-2 | MOOSE printer | tests/test_moose_printer.py |
| P8-3 | Cross-backend verification | tests/test_cross_backend.py |

### Phase 9 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P9-1 | Template family spec | tests/test_p9_1_family_spec_completeness.py + dev/design_docs/09-EINSUM-OPTIMISER.md |
| P9-2 | Family-based refactor | tests/test_p9_2_family_emitters.py |
| P9-3 | Budget regression matrix | tests/test_template_family_budget.py + golden/template_family_emission_baseline.json |

### Phase 10 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P10-1 | MMS convergence matrix | tests/test_mms_convergence_matrix.py |
| P10-2 | Cantilever matrix | tests/test_benchmarks_cantilever_matrix.py |
| P10-3 | Cook's membrane benchmark (TL × J2 × Hex8) | tests/test_benchmarks_cook_membrane_matrix.py |
| P10-4 | Thick cylinder | tests/test_thick_cylinder.py |
| P10-5 | Plate with hole | tests/test_plate_with_hole.py |
| P10-6 | Necking bar matrix | tests/test_benchmarks_necking_bar_matrix.py |
| P10-7 | Taylor impact | tests/test_taylor_impact.py |
| P10-8 | Notched bar benchmark | tests/test_notched_bar_benchmark.py |
| P10-9 | HGO fiber strip | tests/test_hgo_benchmark.py |
| P10-10 | Nightly CI harness | .github/workflows/nightly.yml |

#### Phase 10 close-out evidence (2026-04-26):

The remaining four tasks (P10-1, P10-2, P10-7, P10-10) were delivered through the
`ph10_preq` sub-plan (PRs #121 + #122) and reconciled into PLAN-B on
`SOSOVSKI/plan-b-ph10-exec`. Cross-walk: see
`dev/tasks/ph10_preq/Plan_Completion_Summary.md` and
`dev/tasks/PLAN-B/gates/phase_10_gates.md` (P10-1/P10-2/P10-7/P10-10 entry).

Closure pass results:

- `uv run pytest packages/mechdsl-core/tests/test_mms_convergence_matrix.py -v` -> **10/10 passed** (34.7 s)
- `uv run pytest packages/mechdsl-core/tests/test_benchmarks_cantilever_matrix.py -v` -> **15/15 passed** (0.2 s)
- `uv run pytest packages/mechdsl-core/tests/test_taylor_impact.py -v -m "nightly or regression or integration"` -> **6/6 passed** (3.3 s)
- `uv run pytest packages/mechdsl-core/tests/test_perf_regression.py -v -m "nightly or regression"` -> **4/4 passed** (0.2 s, after the test_nightly_workflow_runs_end_to_end update for the manual-dispatch policy)
- Combined targeted tier: **35 passed in 29.5 s**
- `uv run pytest -m "not slow and not gpu and not e2e"` (full fast tier, including the test_ci_config update) -> **1377 passed / 80 skipped / 113 deselected**
- `uv run ruff check` clean across the changed test files; `uv run mypy packages/mechdsl-core/src/mechdsl/verify/` -> 0 issues across 27 files.

Carry-forwards (from `ph10_preq` Plan Completion Summary; not blocking PLAN-B closure):

1. `TaylorImpactParameters.nightly()` overruns the JC radial-return budget on the shipped 6×6×20 mesh — P10-7 ships smoke + frozen-reference profile instead.
2. PEEQ on long horizons (~16.6 at n_steps=200) is unphysical on smoke mesh — JC calibration sanity pass deferred.
3. `@nightly`-marked tests run in default tier (~0.18 s impact; cosmetic).
4. PLAN-B P10-10 stub premise that "all P10 tests carry @nightly" was rescoped to "the nightly tier loads what it should" — recorded.
5. Nightly workflow `schedule:` cron stays commented per repo policy (memory `feedback_ci_manual_dispatch`); workflow runs on `workflow_dispatch` only.

**Phase 10 status:** 10/10 done. PLAN-B is now complete (54/54 tasks across phases 1–10).
