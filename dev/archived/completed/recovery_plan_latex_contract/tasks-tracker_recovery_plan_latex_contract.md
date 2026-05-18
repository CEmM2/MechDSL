# Development Task Tracker — recovery_plan_latex_contract

Generated on: 2026-04-26 by /Aut_Faciam tasks (recursive invocation from back2latex P2-2).

## recovery_plan_latex_contract Tracker

Plan source: `dev/plans/recovery_plan_latex_contract.md`
Task index: `dev/tasks/recovery_plan_latex_contract/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | Define two support tiers for the repo: `MVP-stable` and `exp | done | claude-opus-4.7 | — | P1-2, P1-3 | 116 | (pending commit) | test_p1_1.py 2/2 | 2026-04-26 |
| P1-2 | Mark MFEM/MOOSE codegen, explicit dynamics, non-MVP material | done | claude-opus-4.7 | — | — | 117 | (pending commit) | test_p1_2.py 5/5 | 2026-04-26 |
| P1-3 | Add a lightweight “stability policy” note to developer-facin | done | claude-opus-4.7 | — | — | 118 | (pending commit) | test_p1_3.py 3/3 | 2026-04-26 |
| P1-4 | Normalize tracker vocabulary to distinguish `done`, `deferre | done | claude-opus-4.7 | — | P1-6 | 119 | (pending commit) | test_p1_4.py 3/3 | 2026-04-26 |
| P1-5 | Record the frontend deferral explicitly as historical execut | done | claude-opus-4.7 | — | — | 120 | (pending commit) | test_p1_5.py 3/3 | 2026-04-26 |
| P1-6 | Mark `dev/plans/MVP_plan.md` and `dev/plans/MVP_sprint{1,2,3 | done | claude-opus-4.7 | — | — | 1 | (pending commit) | test_p1_6.py 3/3 | 2026-04-26 |
| P2-1 | Introduce a canonical façade, e.g. `compile_latex(source: st | done | claude-opus-4.7 | — | P2-2, P2-3, P2-5, P2-6, P3-1, P5-4, P7-2, P7-3, P7-6 | 152 | (pending commit) | test_p2_1.py 4/4 | 2026-04-27 |
| P2-2 | Preserve `build_context()` as a convenience/testing API, but | done | claude-opus-4.7 | — | — | 153 | (pending commit) | test_p2_2.py 4/4 | 2026-04-27 |
| P2-3 | Define the frontend split explicitly: NRPyLaTeX fork/integra | done | claude-opus-4.7 | — | P2-5 | 154 | (pending commit) | test_p2_3.py 6/6 | 2026-04-27 |
| P2-4 | Reconcile or replace the old Phase 2 tasks (`P2.1`–`P2.5`) w | done | claude-opus-4.7 | — | — | 155 | (pending commit) | test_p2_4.py 4/4 | 2026-04-27 |
| P2-5 | Add a minimal frontend contract test suite that begins from  | done | claude-opus-4.7 | — | P2-6 | 156 | (pending commit) | test_p2_5.py 6/6 | 2026-04-27 |
| P2-6 | Ensure frontend failures produce contract-level errors (unsu | done | claude-opus-4.7 | — | — | 157 | (pending commit) | test_p2_6.py 10/10 | 2026-04-27 |
| P3-1 | Add optional semantic fields to `ProblemIR`: `fields`, `doma | done | claude-opus-4.7 | — | P3-2, P3-3, P3-4, P3-5, P4-1, P4-3, P5-4, P7-6 | 194 | (pending commit) | test_p3_1.py 10/10 + 325/325 wider regression | 2026-04-27 |
| P3-2 | Add compatibility constructors/adapters from the current thi | done | claude-opus-4.7 | P3-1 | P3-3, P3-5 | 195 | (pending commit) | test_p3_2.py 14/14 + 139/143 plan_tests+regression | 2026-04-27 |
| P3-3 | Move boundary/domain assumptions out of scattered runtime/co | done | claude-opus-4.7 | P3-1, P3-2 | — | 196 | (pending commit) | test_p3_3.py 12/12 + 1511/1511 wider regression | 2026-04-27 |
| P3-4 | Define a stable `ProblemIR` minimal subset for the MVP-stabl | done | claude-opus-4.7 | P3-1 | — | 197 | (pending commit) | test_p3_4.py 21/21 + 159/159 plan_tests sweep | 2026-04-27 |
| P3-5 | Add targeted IR validation for semantics that were previousl | done | claude-opus-4.7 | P3-1, P3-2 | — | 198 | (pending commit) | test_p3_5.py 22/22 + 1499/1499 wider regression | 2026-04-27 |
| P4-1 | Add structured execution-contract fields to `ElementIR` (geo | done | claude-opus-4.7 | P3-1 | P4-2, P4-3, P4-4, P4-5, P5-4, P6-1, P7-2, P7-6 | 235 | (pending commit) | test_p4_1.py 25/25 + 1535/1535 wider regression | 2026-04-27 |
| P4-2 | Keep `EinsumSpec` and `LocalisationResult`, but demote them  | done | claude-opus-4.7 | P4-1 | P4-3 | 236 | (pending commit) | test_p4_2.py 9/9 + 1545/1545 wider regression | 2026-04-27 |
| P4-3 | Rework lowering so it emits richer `ElementIR` first, then d | done | claude-opus-4.7 | P3-1, P4-1, P4-2 | P4-4 | 237 | (pending commit) | test_p4_3.py 15/15 + 1560/1560 wider regression | 2026-04-27 |
| P4-4 | Make unsupported stable-path combinations fail in lowering w | done | claude-opus-4.7 | P4-1, P4-3 | — | 238 | (pending commit) | test_p4_4.py 11/11 + 1571/1571 wider regression | 2026-04-27 |
| P4-5 | Update artifact bundling to reflect enriched IR ownership cl | done | claude-opus-4.7 | P4-1 | — | 239 | (pending commit) | test_p4_5.py 10/10 + 1581/1581 wider regression | 2026-04-27 |
| P5-1 | Define Taichi as the only stable backend for the canonical L | done | claude-opus-4.7 | — | P5-5, P7-1, P7-2, P7-5, P7-6 | 276 | 538bed1 | test_p5_1.py 7/7 + test_documentation.py 25/25 | 2026-04-28 |
| P5-2 | Mark MFEM/MOOSE printers as experimental backend surfaces. | done | claude-opus-4.7 | — | — | 277 | 7439014 | test_p5_2.py 2/2 + test_p1_2.py 5/5 + regression 1590 | 2026-04-28 |
| P5-3 | Add a small façade layer if needed to present codegen in the | done | claude-opus-4.7 | — | — | 278 | 302028b + 41bcf73 | test_p5_3.py 27/27 + test_taichi_printer.py 58/58 + test_emission_phase5.py 16/16 | 2026-04-28 |
| P5-4 | Ensure the Taichi path consumes enriched IR data where avail | done | claude-opus-4.7 | — | — | 279 | 2ec85da | test_p5_4.py 8/8 + test_p4_{1,3,5}.py + artifact + taichi_printer 136/136 | 2026-04-28 |
| P5-5 | Split codegen verification into stable vs experimental suite | done | claude-opus-4.7 | — | — | 280 | 32a668c | test_p5_5.py 3/3 + codegen 20/20 + mfem 11/11 + moose 8/8 + cross_backend 3 skip | 2026-04-28 |
| P6-1 | Add an optional `algo2code`-generated PCG path behind `Linea | done | claude-opus-4.7 | — | P6-2, P6-3, P6-5 | 317 | 199dedc | test_p6_1.py 7/7 + test_solver.py 18/18 | 2026-04-29 |
| P6-2 | Keep the current imported solver path as the default fallbac | done | claude-opus-4.7 | — | P6-3 | 318 | 4b15191 | test_p6_2.py 2/2 + test_solver.py 18/18 | 2026-04-29 |
| P6-3 | Add a single stable integration test for `algo2code` → PCG → | done | claude-opus-4.7 | — | — | 319 | f498880 | test_p6_3.py 2/2 (Newton converges via Algo2CodePCGSolver, max\|u_gen-u_ref\|=0.0 vs ScipyCGSolver) | 2026-04-29 |
| P6-4 | Defer radial-return replacement until frontend + IR alignmen | done | claude-opus-4.7 | — | — | 320 | 5c310a0 | test_p6_4.py 2/2 + phase6_exit sentinel green | 2026-04-29 |
| P6-5 | Document `algo2code`’s role in the recovered architecture to | done | claude-opus-4.7 | — | — | 321 | 797f945 | test_p6_5.py 2/2 (README + design_docs §1.1/§2.5 + dev/examples/README) | 2026-04-29 |
| P7-1 | Split end-to-end tests into `from_latex` and `from_problem_i | done | claude-opus-4.7 | — | — | 358 | c711eed | test_p7_1.py 2/2 (markers registered + 35 from_problem_ir tests collected) | 2026-04-29 |
| P7-2 | Add at least one canonical LaTeX-to-solution acceptance test | done | claude-opus-4.7 | — | — | 359 | c7964ce | test_p7_2.py 2/2 (LaTeX -> compile_latex -> Taichi -> Newton -> reference < 1e-10) | 2026-04-29 |
| P7-3 | Update examples so the stable story begins from LaTeX input; | done | claude-opus-4.7 | — | — | 360 | 0f37b30 | test_p7_3.py 2/2 (README LaTeX-first ordering + dev/examples/run_compile_latex.py) | 2026-04-29 |
| P7-4 | Add a short architecture decision or recovery-status note cr | done | claude-opus-4.7 | — | — | 361 | 0251afb + 4ec24a8 | test_p7_4.py 2/2 (cross-link note + plan back-ref) | 2026-04-29 |
| P7-5 | Archive or annotate superseded sprint/task documents so they | done | claude-opus-4.7 | — | — | 362 | b79ce6d | test_p7_5.py 2/2 (8 plan banners + 8 task _SUPERSEDED + 8 tracker banners) | 2026-04-29 |
| P7-6 | Close the loop with an updated drift/alignment review after  | done | claude-opus-4.7 | — | — | 363 | 233e441 | test_p7_6.py 2/2 (R1–R4 verdicts RESTORED + 9-bullet sign-off mirrored) | 2026-04-29 |

## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Phase 6 — Test-Task Mapping (scaffolded 2026-04-29)

| Task ID | Tier | Stub file | Stub class::tests | Existing coverage |
|---------|------|-----------|-------------------|-------------------|
| P6-1 | integration | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_1.py` | `TestP6_1::test_generated_pcg_satisfies_solver_interface`, `TestP6_1::test_p6_1_deliverables_present_at_listed_surfaces` | none |
| P6-2 | unit | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_2.py` | `TestP6_2::test_solver_regression_passes_with_both_modes`, `TestP6_2::test_deliverables_present_at_surfaces` | none |
| P6-3 | integration | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_3.py` | `TestP6_3::test_algo2code_generated_pcg_drives_newton_to_convergence`, `TestP6_3::test_deliverables_present_at_surfaces` | none |
| P6-4 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_4.py` | `TestP6_4::test_recovery_plan_labels_radial_return_as_later_stage`, `TestP6_4::test_p6_4_deliverables_present_in_planning_docs` | none |
| P6-5 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p6_5.py` | `TestP6_5::test_readme_architecture_section_names_both_packages`, `TestP6_5::test_p6_5_deliverables_present_at_listed_surfaces` | none |

### Phase 6 verification outcomes

| Task ID | Stub status | Pass/Total | Notes |
|---------|-------------|------------|-------|
| P6-1 | done | 7/7 (2 acceptance + 5 failure routes) | Algo2CodePCGSolver landed; canonical LaTeX shipped in algo2code.library.pcg; commit 199dedc; review 9/10 |
| P6-2 | done | 2/2 (factory + selector + regression) | build_solver/get_default_solver/select_linear_solver landed; Newton default unchanged; commit 4b15191; review 9/10 |
| P6-3 | done | 2/2 (full Newton plumbing) | algo2code-PCG → newton_solve end-to-end on 1x1x1 SVK patch; max\|u_gen-u_ref\|=0.0 vs scipy fallback; commit f498880; review 10/10 |
| P6-4 | done | 2/2 (recovery-plan callout pins radial-return as post-MVP behind R2+R3) | callout at lines 323-335; commit 5c310a0; review 10/10; phase6_exit TODO sentinel resolved |
| P6-5 | done | 2/2 (README + design_docs + dev/examples/README all updated) | resolves P6-1 Gate-B medium (design-doc sync §2.5 → canonical); commit 797f945; review 10/10 |

## Phase 7 — Test-Task Mapping (scaffolded 2026-04-29)

| Task ID | Tier | Stub file | Stub class::tests | Existing coverage |
|---------|------|-----------|-------------------|-------------------|
| P7-1 | integration | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_1.py` | `TestP7_1::test_ci_test_selection_exposes_from_latex_family`, `TestP7_1::test_deliverables_present_at_surfaces` | none |
| P7-2 | integration | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_2.py` | `TestP7_2::test_acceptance_passes_starting_from_latex_input`, `TestP7_2::test_deliverables_present_at_surfaces` | none |
| P7-3 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_3.py` | `TestP7_3::test_first_run_example_in_readme_uses_canonical_path`, `TestP7_3::test_deliverables_present_at_surfaces` | none |
| P7-4 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_4.py` | `TestP7_4::test_cross_link_note_exists_and_references_plan_and_drift`, `TestP7_4::test_deliverables_present_at_surfaces` | none |
| P7-5 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_5.py` | `TestP7_5::test_no_historical_plan_appears_active_by_accident`, `TestP7_5::test_deliverables_present_at_surfaces` | none |
| P7-6 | docs | `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_6.py` | `TestP7_6::test_follow_up_review_confirms_contract_status`, `TestP7_6::test_deliverables_present_at_surfaces` | none |

### Phase 7 verification outcomes

| Task ID | Stub status | Pass/Total | Notes |
|---------|-------------|------------|-------|
| P7-1 | done | 2/2 (markers registered + from_problem_ir non-empty selector) | pyproject.toml markers + 5 e2e modules tagged; 35 from_problem_ir tests collected; from_latex family empty until P7-2; commit c711eed; review 10/10 (0 issues) |
| P7-2 | done | 2/2 (canonical LaTeX -> Newton -> ref within 1e-10) | full Taichi JIT + solve + reference compare in 26.62s; from_latex family now 2; commit c7964ce; review 9/10 (2 minor info: traction-string symbolic binding gap documented at test_p7_2.py:142-144) |
| P7-3 | done | 2/2 (README LaTeX-first ordering + canonical example script) | dev/examples/run_compile_latex.py (new) + README/dev-examples README reorder; commit 0f37b30; review 9/10 (2 minors, informational) |
| P7-4 | done | 2/2 (cross-link note exists + plan back-ref) | dev/reviews/recovery_status_2026_04.md (new) + plan back-link; commits 0251afb + 4ec24a8; review 9/10 (1 minor cosmetic resolved) |
| P7-5 | done | 2/2 (no historical plan looks active + deliverables present) | 8 plan banners + 8 task _SUPERSEDED.md + 8 tracker banners; commit b79ce6d; review 10/10 (0 issues) |
| P7-6 | done | 2/2 (per-pillar verdicts RESTORED + 9/9 sign-off mirrored) | dev/reviews/drift_post_recovery_2026_04.md (new, 343 lines); R1/R2/R3/R4 RESTORED; commit 233e441; review 9/10 (1 minor: pending-list reflects authoring base 44db219, honest) |

