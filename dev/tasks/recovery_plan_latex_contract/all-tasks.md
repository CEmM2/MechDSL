# All Tasks — recovery_plan_latex_contract

Plan source: `dev/plans/recovery_plan_latex_contract.md`
Tracker: `dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`

Decomposed by `/Aut_Faciam tasks` (recursive invocation from back2latex P2-2). Phase IDs and Task IDs were already canonical in the recovery plan after the Phase-1 amendments of back2latex; this decomposition copies them verbatim.

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | Define two support tiers for the repo: `MVP-stable` and `experimental`. | — | P1-2, P1-3 | 116 |
| P1-2 | 1 | Mark MFEM/MOOSE codegen, explicit dynamics, non-MVP materials, and non-canonical | P1-1 | — | 117 |
| P1-3 | 1 | Add a lightweight “stability policy” note to developer-facing docs. | P1-1 | — | 118 |
| P1-4 | 1 | Normalize tracker vocabulary to distinguish `done`, `deferred`, `implemented-via | — | P1-6 | 119 |
| P1-5 | 1 | Record the frontend deferral explicitly as historical execution drift, not missi | — | — | 120 |
| P1-6 | 1 | Mark `dev/plans/MVP_plan.md` and `dev/plans/MVP_sprint{1,2,3}.md` as superseded  | P1-4 | — | 1 |
| P2-1 | 2 | Introduce a canonical façade, e.g. `compile_latex(source: str, profile: str = "m | — | P2-2, P2-3, P2-5, P2-6, P3-1, P5-4, P7-2, P7-3, P7-6 | 152 |
| P2-2 | 2 | Preserve `build_context()` as a convenience/testing API, but document it as seco | P2-1 | — | 153 |
| P2-3 | 2 | Define the frontend split explicitly: NRPyLaTeX fork/integration = parser of rec | P2-1 | P2-5 | 154 |
| P2-4 | 2 | Reconcile or replace the old Phase 2 tasks (`P2.1`–`P2.5`) with the actual recov | — | — | 155 |
| P2-5 | 2 | Add a minimal frontend contract test suite that begins from LaTeX source. | P2-1, P2-3 | P2-6 | 156 |
| P2-6 | 2 | Ensure frontend failures produce contract-level errors (unsupported syntax, miss | P2-1, P2-5 | — | 157 |
| P3-1 | 3 | Add optional semantic fields to `ProblemIR`: `fields`, `domain`, `mesh_contract` | P2-1 | P3-2, P3-3, P3-4, P3-5, P4-1, P4-3, P5-4, P7-6 | 194 |
| P3-2 | 3 | Add compatibility constructors/adapters from the current thin representation. | P3-1 | P3-3, P3-5 | 195 |
| P3-3 | 3 | Move boundary/domain assumptions out of scattered runtime/codegen logic and into | P3-1, P3-2 | — | 196 |
| P3-4 | 3 | Define a stable `ProblemIR` minimal subset for the MVP-stable contract. | P3-1 | — | 197 |
| P3-5 | 3 | Add targeted IR validation for semantics that were previously implicit. | P3-1, P3-2 | — | 198 |
| P4-1 | 4 | Add structured execution-contract fields to `ElementIR` (geometry summary, mater | P3-1 | P4-2, P4-3, P4-4, P4-5, P5-4, P6-1, P7-2, P7-6 | 235 |
| P4-2 | 4 | Keep `EinsumSpec` and `LocalisationResult`, but demote them to derived/optimizat | P4-1 | P4-3 | 236 |
| P4-3 | 4 | Rework lowering so it emits richer `ElementIR` first, then derives contraction/o | P3-1, P4-1, P4-2 | P4-4 | 237 |
| P4-4 | 4 | Make unsupported stable-path combinations fail in lowering with clear phase-scop | P4-1, P4-3 | — | 238 |
| P4-5 | 4 | Update artifact bundling to reflect enriched IR ownership cleanly. | P4-1 | — | 239 |
| P5-1 | 5 | Define Taichi as the only stable backend for the canonical LaTeX compile path. | — | P5-5, P7-1, P7-2, P7-5, P7-6 | 276 |
| P5-2 | 5 | Mark MFEM/MOOSE printers as experimental backend surfaces. | — | — | 277 |
| P5-3 | 5 | Add a small façade layer if needed to present codegen in the design-doc style wh | — | — | 278 |
| P5-4 | 5 | Ensure the Taichi path consumes enriched IR data where available rather than rel | P2-1, P3-1, P4-1 | — | 279 |
| P5-5 | 5 | Split codegen verification into stable vs experimental suites. | P5-1 | — | 280 |
| P6-1 | 6 | Add an optional `algo2code`-generated PCG path behind `LinearSolverInterface`. | P4-1 | P6-2, P6-3, P6-5 | 317 |
| P6-2 | 6 | Keep the current imported solver path as the default fallback until generated PC | P6-1 | P6-3 | 318 |
| P6-3 | 6 | Add a single stable integration test for `algo2code` → PCG → Newton solve plumbi | P6-1, P6-2 | — | 319 |
| P6-4 | 6 | Defer radial-return replacement until frontend + IR alignment is settled. | — | — | 320 |
| P6-5 | 6 | Document `algo2code`’s role in the recovered architecture to prevent renewed dri | P6-1 | — | 321 |
| P7-1 | 7 | Split end-to-end tests into `from_latex` and `from_problem_ir` families. | P5-1 | — | 358 |
| P7-2 | 7 | Add at least one canonical LaTeX-to-solution acceptance test on the MVP-stable p | P2-1, P4-1, P5-1 | — | 359 |
| P7-3 | 7 | Update examples so the stable story begins from LaTeX input; keep programmatic e | P2-1 | — | 360 |
| P7-4 | 7 | Add a short architecture decision or recovery-status note cross-linking this pla | — | — | 361 |
| P7-5 | 7 | Archive or annotate superseded sprint/task documents so they are obviously histo | P5-1 | — | 362 |
| P7-6 | 7 | Close the loop with an updated drift/alignment review after Phases R1–R4 land. | P2-1, P3-1, P4-1, P5-1 | — | 363 |

## Notes

- Cross-phase blockers were authored in the recovery plan during back2latex Phase 1 (P1-3 + P1-5) and are reproduced verbatim here.
- Within-phase dependency edges are taken from each table's `Blocked by` column.
