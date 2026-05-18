# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added — post_recovery_plan Phases 1–7

`dev/plans/post_recovery_plan.md` lands seven follow-up phases that close residual gaps from the LaTeX-first recovery.

- **Phase 1 — Neumann boundary directive flow into emitted code (P1-1..P1-7)**: `BoundaryCondition.traction` widened to `str | tuple[float, float, float] | None`; new `surface_tag` field; `emit_neumann_f_ext_kernel` (literal-baked) and `emit_neumann_f_ext_kernel_for_ir` (parametric) added to `mechdsl.codegen.taichi_printer`; `compile_latex` façade now surfaces `bundle.f_ext_kernel`; symbolic traction routes through directive-only path. Golden coverage in `packages/mechdsl-core/tests/golden/boundary_neumann.ti.txt`.
- **Phase 2 — `docs` pytest-marker tier (P2-1..P2-3)**: registered `@pytest.mark.docs` for documentation-anchor / contract tests; swapped `integration → docs` on the recovery-plan `test_p7_3..6.py` family; new `docs-tests` CI job routes the tier on every PR.
- **Phase 3 — Boundary-condition handoff documentation (P3-1, P3-2)**: `compile_latex` docstring gains an explicit BC handoff paragraph; new `test_compile_latex_docstring.py` regression test pins the paragraph at the canonical entry point.
- **Phase 4 — nrpylatex math grammar integration (P4-1..P4-5)**: NRPyLaTeX 1.4.0 wired through `mechdsl.symbolic.nrpylatex_bridge`; rank-2 surrogate algorithms cover SVK PK1 emission and J2 yield (`σ:σ`) until the upstream parser supports `\det` / `\log` / `\sqrt(s:s)`. Round-trip suite at `tests/test_nrpylatex_round_trip.py`.
- **Phase 5 — `algo2code` radial-return substitution (P5-1..P5-5)**: J2 power-law radial-return scalar Newton loop authored in algpseudocode (`dev/algorithms/radial_return_j2.tex`); `mechdsl.lib.plasticity` consumes `algo2code.transpile(..., backend="taichi")` at module load — the imported algorithm is the runtime function, not a hand translation. Feature-flag dispatcher (`MECHDSL_USE_IMPORTED_RR`).
- **Phase 6 — Test-layer hardening (P6-1..P6-4)**: new `tests/_e2e_helpers.py` consolidates the previously-duplicated `_import_generated_module` helper (P6-1, P6-2 promoted two of four call sites; P7 cleanup promoted the remaining two so all four sites import from one source); `test_phase6_exit.py` cleanup-detector switched from a line-number whitelist to an in-source `intentional-cleanup-site` marker with a ±3-line proximity window — survives ruff reformats.
- **Phase 7 — Docs polish + governance reconciliation (P7-1..P7-7)**: `dev/examples/README.md` regains its `## Inventory` anchor; `test_p7_3.py` ordering check scoped to runnable code fences (markdown `python` / `bash`), with three-prefix path matching (`dev/examples/`, `./dev/examples/`, `/dev/examples/`) for the example-script reference; per-invocation uuid-derived module name in `test_p7_2.py`; `_SUPERSEDED.md` separates runtime-active from archived sub-deliverables; new `baseline-stability` CI job smoke-imports `algo2code` and runs `pytest --collect-only` on both packages on every push / PR.
- **`P2-2` docs-collection invariant retired**: the per-phase prefix list (widened in P3-1 / P4-5 / P5-5 / P7) replaced with a single directory prefix `post_recovery_plan/`. Removes the recurring widen-on-each-phase pattern flagged in `Handoff_Phase_6.md`.

### Fixed — `algo2code` parser

- **Multi-letter scratch identifiers**: `expr_parser.LETTER` regex broadened from `[a-zA-Z]` to `[a-zA-Z][a-zA-Z0-9]*` so identifiers like `ap`, `Hp`, `tol`, `sig_eq` tokenize as single names.
- **Binary `/` in expressions**: `parse_term` now recognises the `SLASH` token (previously dropped, e.g. `a + b / c` parsed as `a + b`).
- **Scalar-only algorithms**: `taichi_codegen._emit_driver` no longer emits the dangling `n = b.shape[0]` line when no vector argument is present.

### Added — Recovery: LaTeX-first contract restoration

The `back2latex` meta-plan reshapes `dev/plans/recovery_plan_latex_contract.md` so `Aut_Faciam` can ingest it, then the recovery plan's first three phases land:

- **Canonical entry point**: `mechdsl.compile_latex(source: str, profile: str = "mvp") -> ArtifactBundle` parses `% mechanics` directives, adapts the resulting context dict to a `ProblemIR`, and forwards through the existing pipeline. `mechdsl.compile` (legacy programmatic path) is preserved verbatim. Allowed profile set is exposed as `mechdsl.ALLOWED_PROFILES = frozenset({"mvp"})` (extend via this set, never relax inline).
- **`ProblemIR` semantic enrichment** (recovery R2 / P3-1): four new optional frozen dataclasses — `FieldSpec`, `DomainSpec`, `MeshContract`, `ResidualContract` — exposed from `mechdsl.ir.mechanics_ir`. `ProblemIR` carries them as new optional fields with safe defaults (`fields=()`, `domain=None`, `mesh_contract=None`, `residual_contract=None`). `ProblemIR.to_dict/from_dict` extended to round-trip both legacy (no enrichment keys) and enriched dicts. Backward compat verified across 84 `ProblemIR(...)` construction sites.
- **`FieldSpec.kind` validation**: rejects out-of-vocabulary values; allowed set exposed as `mechdsl.ir.mechanics_ir.ALLOWED_FIELD_KINDS = frozenset({"scalar", "vector", "tensor"})`.
- **Immutable enrichment metadata**: `DomainSpec.metadata`, `MeshContract.metadata`, `ResidualContract.metadata` wrap their backing dicts in `MappingProxyType` so the frozen-dataclass invariant extends through nested mutation.
- **Tier policy and stability contract** (recovery R0): new `## Support tiers` and `### Stability policy` sections in `README.md`. Two tiers: `MVP-stable` (Hex8 + Total Lagrangian + Taichi backend + SVK/J2-power-law) vs `experimental` (MFEM/MOOSE codegen, explicit dynamics, non-MVP materials, non-canonical elements). Module docstrings on `codegen/mfem_printer.py`, `codegen/moose_printer.py`, `solver/lumped_mass.py`, `symbolic/models/__init__.py`, and `ir/mechanics_ir.py::ElementType` carry the `experimental` marker.
- **Frontend architectural split** (recovery R1.3): new `packages/mechdsl-core/src/mechdsl/frontend/ARCHITECTURE.md` documents NRPyLaTeX as the parser of record vs the local adapter / normalizer / validator triad (parser.py / directives.py / build_context / two_point.py). Each module's docstring identifies its role.
- **Tracker status vocabulary** (recovery R0 / P1-4): canonical four-value set defined in new `dev/tracking/STATUS_LEGEND.md` — `not_started`, `done`, `deferred`, `implemented-via-substitute` (plus Aut_Faciam-internal `in_progress`). Replaces the legacy two-value `not_started` / `done` set that conflated three genuinely different states.
- **Frontend deferral history note**: `dev/reviews/frontend_drift_history.md` classifies the deferred MVP `P2.1..P2.5` work against three patterns (planned-but-deferred / never-planned / implemented-via-substitute). Cross-linked to `drift_20_04.md` and the recovery plan.
- **MVP plan supersession**: `dev/plans/MVP_plan.md` and `MVP_sprint{1,2,3}.md` carry banners pointing at the recovery plan; the five legacy `P2.x` rows in `tasks-tracker_MVP_plan.md` are retagged `implemented-via-substitute` with substitute citations.
- **README Quickstart**: leads with the `compile_latex` LaTeX-source example; the programmatic `build_context` path moves to a Secondary subsection.
- **First LaTeX-source contract test suite**: `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p2_5.py` is the first test that begins from a real LaTeX source and reaches an `ArtifactBundle` (SVK + J2 power-law). Companion `test_p2_6.py` covers 10 negative paths through `compile_latex` (unsupported constructs, malformed directives, index semantics, stable-message contract).
- **MVP-stable subset contract** (recovery R2 / P3-4): new `MVP_STABLE_SUBSET` constant (a frozen `MvpStableSubset` dataclass) in `mechdsl.ir.mechanics_ir` enumerates every `ProblemIR` axis covered by the canonical compile path. New `ProblemIR.assert_mvp_stable() / is_mvp_stable()` methods enforce the contract at the IR boundary; `MvpSubsetViolation` subclasses `UnsupportedError` so existing rule-based catches still apply. Contract documented in new `packages/mechdsl-core/src/mechdsl/ir/ARCHITECTURE.md` (sibling of the implementation, since `dev/design_docs/` is hook-protected).
- **Canonical context-dict adapter** (recovery R2 / P3-2): new `ProblemIR.from_context()` and `BoundaryCondition.from_context()` classmethods replace three private duplicates that had drifted across `mechdsl/__init__.py`, `tests/test_full_pipeline.py`, and `tests/test_formulation_switching.py`. The adapter accepts the canonical `name` key as well as legacy `region`/`face` aliases and `dofs`/`components` aliases for the boundary subschema. `compile_latex` now calls the classmethod directly.
- **Targeted IR validation** (recovery R2 / P3-5): six new construction-time checks on `ProblemIR.__post_init__` that surface previously-silent malformed IRs at the construction site instead of deep inside codegen / runtime — duplicate boundary names, out-of-range BC component indices, duplicate spatial / material coordinate names, duplicate `FieldSpec.name` entries, BC `field_name` consistency with declared `fields`. The compile-path `compile_latex` now calls `assert_mvp_stable()`, which adds the seventh check (required material parameters for MVP-stable models) at the user-visible boundary. In-tree research code that builds minimal IRs for shape-only testing is unaffected.
- **Centralized boundary/domain semantic assumptions** (recovery R2 / P3-3): new `ProblemIR.required_region_tags()` and `ProblemIR.derived_mesh_contract()` helpers expose the previously-scattered "BC name == mesh boundary tag" assumption as a single source of truth on the IR. New `mechdsl.solver.mesh_io.validate_mesh_against_contract()` bridges `MeshContract` ↔ `HexMesh.boundary_tags` so the IR/mesh mismatch raises `BoundaryRegionError` at the boundary instead of a deep `KeyError` in codegen / runtime.
- **`ElementIR` execution-contract enrichment** (recovery R3 / P4-1): four new optional frozen dataclasses — `GeometrySummary`, `MaterialEvalContract` (with `ALLOWED_STRESS_MEASURES` / `ALLOWED_STRAIN_MEASURES` allowlists), `LocalForceDescriptor`, `LocalTangentDescriptor` — exposed from `mechdsl.ir.element_ir`. `ElementIR` carries them as new optional fields with safe `None` defaults. Construction-time consistency checks reject mismatched `n_dof`, mismatched `n_quad`, and TL/UL stress-measure conflicts. New `ElementIR.to_dict / from_dict` round-trips both legacy and enriched forms; basis / quadrature numerics are reconstructed from canonical constructors via `element_type`.
- **`EinsumSpec` / `LocalisationResult` demoted to derived views** (recovery R3 / P4-2): docstrings explicitly mark them as derived optimization views over `ElementIR` (the post-P4-1 primary semantic carrier). New `LocalisationResult.from_element_ir(element_ir, problem_ir)` classmethod materialises the optimizer-view bundle from an enriched `ElementIR` — making the derived-view relationship explicit in code. Production path `localise(problem_ir)` unchanged.
- **Lowering emits enriched `ElementIR` first** (recovery R3 / P4-3): new `_enrich_element_ir(legacy_ir, problem_ir)` helper in `fe_localise.py` populates the four P4-1 contract dataclasses from the `ProblemIR` / `ElementIR` semantics. `localise()` now emits the enriched IR first, then derives the einsum optimizer view via `LocalisationResult.from_element_ir`. `ArtifactBundle.from_pipeline` surfaces the four contract blocks in `element_ir_summary`; pre-P4-3 bundles round-trip cleanly (new keys default to `None`).
- **Deterministic lowering rejections with Plan-B pointers** (recovery R3 / P4-4): new `LocalisationError(UnsupportedError, ValueError)` exception re-exported from `mechdsl.lowering`. Multiple inheritance preserves back-compat with both `UnsupportedError` (per `.claude/rules/ir.md`) and pre-P4-4 callers that caught the bare `ValueError`. New `_check_stable_path_combo(problem_ir)` helper fires axis-by-axis (formulation → element → material); every rejection message names the offending construct AND the Plan-B phase that adds support.
- **Artifact bundling reflects enriched IR ownership** (recovery R3 / P4-5): new `ArtifactBundle.element_ir_dict` field carries the canonical `ElementIR.to_dict()` contract surface (P4-1 enrichment included). Default empty dict so pre-P4-5 bundles round-trip cleanly. `content_hash` deliberately unchanged so legacy goldens survive verbatim. The bundle docstring now spells out the ownership hierarchy: `problem_ir_dict` (semantic input) → `element_ir_dict` (primary semantic carrier) → `element_ir_summary` (legacy summary, derived) → `contraction_plans` (derived optimizer view).

### Changed

- **`build_context()`** is now documented as the **secondary** programmatic entry point. It remains importable and functional; `compile_latex` is the canonical surface for new code and documentation.



- **Thick cylinder benchmark** (TL × SVK × Hex8): radial and hoop stress compared against Lamé closed-form; 5% gate on peak hoop stress (`mechdsl.verify.benchmarks.thick_cylinder`)
- **Necking bar benchmark** (TL × J2 × Hex8): load-displacement history compared against Simo & Hughes reference and committed golden within 2% (`mechdsl.verify.benchmarks.necking_bar`)
- **Notched bar benchmark** (TL × Lemaitre × Hex8): full load-displacement history + damage-field sampling; 10% regression gate; damage localises at notch-root element (`mechdsl.verify.benchmarks.notched_bar`)
- **HGO fiber-strip benchmark** (TL × HGO × Hex8): uniaxial FEM stress compared against closed-form HGO reference via damped-Newton lateral-stretch solve; 5% gate at multiple stretch levels (`mechdsl.verify.benchmarks.hgo_strip`)
- **`mechdsl.verify.benchmarks` module**: unified `BenchmarkResult` dataclass + kwargs-injection contract for all four benchmarks; `verify` package remains free of `tests/` imports

### Added — Plan B Phase 9: Contraction-Family Registry (B9)

- **8-family taxonomy**: `Family` enum classifying all emitted einsum strings — `DISPLACEMENT_GRADIENT`, `FORCE_INTEGRATION`, `MATERIAL_TANGENT_CONTRACTION`, `STRAIN_ENERGY`, `MASS_MATRIX`, `GEOMETRIC_STIFFNESS`, `KINEMATIC_INTEGRATION`, `FALLBACK` — enabling family-aware dispatch and JIT-budget planning (`mechdsl.codegen.family_registry`)
- **Family-aware emission dispatch**: backend printers select optimised code paths per family; rollback flag re-routes to the generic path on unsupported families
- **JIT budget regression suite**: parametric test grid over all (element × material × backend) triples; emitted line counts checked against the 512 / 2000 / 5000 limits

### Added — Plan B Phase 8: MFEM + MOOSE Backends (B8)

- **MFEM printer**: C++ `NonlinearFormIntegrator` + `BilinearFormIntegrator` emission; Voigt conversion helpers (`voigt_tensorial_to_engineering`); CMakeLists template; MPI-compatible output (`mechdsl.codegen.mfem_printer`)
- **MOOSE printer**: `ComputeStressBase` + `RankTwoTensor` emission; MOOSE input-file template; material-block code generation (`mechdsl.codegen.moose_printer`)
- **Cross-backend verification**: Taichi vs MFEM vs MOOSE patch-test equivalence within relative tolerance; mesh-exporter utilities shared across all three backends

### Added — Plan B Phase 7: Explicit Dynamics (B7)

- **Lumped mass matrix**: HRZ row-sum lumping for Hex8 (`mechdsl.solver.mass`)
- **Central-difference explicit driver**: Courant-stable velocity-Verlet loop with diagonal mass inversion and residual-force assembly (`mechdsl.solver.explicit`)
- **Critical time step helper**: `courant_dt(mesh, E, nu, rho)` from minimum element characteristic length and longitudinal wave speed
- **Free vibration cross-check**: explicit driver verified against implicit quasi-static reference on a cantilever beam

### Added — Plan B Phase 6: Continuum Damage (B6)

- **Lemaitre damage model**: scalar isotropic damage coupled to J2 power-law plasticity; effective-stress principle with strain equivalence; de Souza Neto triaxiality factor; nucleation threshold `eps_D`; clamped at `D_MAX = 1 − 1e-6` (`mechdsl.symbolic.models.lemaitre`)
- **History field integration**: Lemaitre `D` field tracked through Newton iterations; element deletion assembly at `D >= D_crit`
- **Notched bar localisation test**: D=0 regression; damage confirmed to localise at the notch-root element

### Added — Plan B Phase 5: Additional Elements (B5)

- **Tet4 linear tetrahedron**: 4-node element, 1-point Gauss quadrature (`mechdsl.codegen.tet4_tables`)
- **Tet10 quadratic tetrahedron**: 10-node serendipity, 4-point Gauss quadrature (`mechdsl.codegen.tet10_tables`)
- **Hex20 serendipity**: 20-node element, 27-point Gauss quadrature (`mechdsl.codegen.hex20_tables`)
- **Hex8 reduced integration**: 1-point centre Gauss for hourglass-prone analyses (`mechdsl.codegen.hex8_reduced_tables`)
- **Flanagan-Belytschko hourglass control**: stabilisation for reduced-integration Hex8 (`mechdsl.codegen.hourglass`)
- **ElementFactory API**: `ElementFactory.create(element_type, integration_scheme)` — uniform construction replacing element-specific imports

### Added — Plan B Phase 4: Hyperelastic Models (B4)

- **Neo-Hookean model**: isochoric-volumetric split (`Psi = mu/2*(I1_bar-3) + kappa/2*(J-1)^2`); analytic PK2 stress and closed-form 4th-order tangent; `NeoHookeanMaterial.from_E_nu()` convenience factory (`mechdsl.symbolic.models.neo_hookean`)
- **Mooney-Rivlin model**: two-parameter `(C10, C01)` with volumetric penalty; analytic stress and FD tangent (`mechdsl.symbolic.models.mooney_rivlin`)
- **Ogden model**: spectral-stretch N-term series; robust positive-definiteness checks; symmetric-perturbation FD tangent (`mechdsl.symbolic.models.ogden`)
- **HGO anisotropic model**: Holzapfel-Gasser-Ogden dispersion model with two fiber families; fiber activation gate (`E_fi > 0`); FD tangent robust at the activation boundary (`mechdsl.symbolic.models.hgo`)
- **AD oracle**: automatic-differentiation cross-check verifying PK2 stress and Voigt tangent for all four models against FD and AD references

### Added — Plan B Phase 3: Viscoplasticity (B3)

- **Perzyna viscoplasticity**: backward-Euler return map with overstress function; rate-dependent yield; consistent algorithmic tangent (`mechdsl.symbolic.models.perzyna`)
- **Johnson-Cook flow stress**: strain-rate sensitivity, adiabatic heating via Taylor-Quinney coefficient, JC parameter validation (`mechdsl.symbolic.models.johnson_cook`)
- **Rate-sensitivity acceptance suite**: Perzyna collapses to J2 in the quasi-static limit; rate/thermal cross-checks

### Added — Plan B Phase 1: Updated Lagrangian (B1)

- **Updated Lagrangian formulation**: spatial shape gradients, Cauchy stress residual, and Jaumann material + geometric stiffness tangent emission — full UL codegen alongside existing Total Lagrangian
- **ConfigurationIR extension**: `Formulation.UPDATED_LAGRANGIAN` variant with `reference_frame` and `stress_measure` on `ProblemIR`
- **Objective stress rates**: Jaumann and Truesdell rate functions with full-F Piola push-forward (`mechdsl.symbolic.objective_rates`)
- **Formulation switching**: `% mechanics set formulation updated_lagrangian` directive; `build_context` and codegen auto-infer configuration from formulation
- **TL/UL equivalence verification**: handwritten UL reference solver (`ref_hex8_ul.py`), rigid rotation invariance test, and TL-vs-UL displacement comparison within 1e-10

### Added — Plan B Phase 2: Convected Coordinates (B2)

- **Curvilinear reference configurations**: `MetricField` wrapper with symmetry validation, convected metric `g_IJ = G_ref^T C G_ref`, symbolic metric inversion (`mechdsl.symbolic.convected`)
- **Differential geometry**: covariant/contravariant base vectors, Christoffel symbols `Gamma^K_{IJ}` with Cartesian fast-path, covariant derivatives for contravariant vectors, covariant vectors, and rank-2 tensors
- **Metric-assign directives**: `% mechanics assign gDD --metric_current` parser directive via NRPyLaTeX integration
- **Curvilinear patch test**: SVK stress through convected pathway verified constant across 15 (r, theta) points; Cartesian-convected equivalence within 1e-13

### Fixed

- **UL tangent**: Jaumann + Hadamard geometric stiffness replaced with Truesdell + standard geometric stiffness for correct spatial tangent
- **Convected metric formula**: `F^T @ G_metric @ F` corrected to `G_ref_vecs^T @ C @ G_ref_vecs` — API takes base vectors, not the metric tensor

## [0.1.0] - 2026-04-12

### Added

- **mechdsl-core MVP**: 3D Hex8 Total Lagrangian compilation pipeline from validated frontend context to emitted Taichi solver source
- **Supported constitutive models**: SVK elasticity and J2 power-law plasticity
- **IR pipeline**: immutable `ProblemIR` and `ElementIR` schemas with construction-time validation and FE localisation
- **Einsum optimisation**: contraction planning, tier classification, and JIT-budget enforcement
- **Taichi code generation**: deterministic source emission for solver kernels and Newton drivers
- **Solver infrastructure**: CG/PCG adapters, structured Hex8 mesh utilities, boundary-condition codegen, adaptive load stepping, and history-field lifecycle
- **Verification assets**: handwritten NumPy references, golden regression bundles, patch test, rigid body, cantilever, Cook's membrane, necking bar, and full-pipeline end-to-end tests
- **Examples and docs**: README installation/quickstart/architecture guide and runnable programmatic examples for cantilever, plastic uniaxial, Cook's membrane, necking bar, and patch test
- **CI tiers**: fast push validation, broader PR validation, and nightly e2e benchmark coverage with regression issue filing

### Fixed

- **Taichi codegen** (5 critical fixes): J2 Newton `ti.static` → runtime for `break` support; quadrature loop to `ti.static` for Python list access; Newton non-convergence raises `RuntimeError`; NaN/Inf guard on residual; node loops to runtime per convention
- **Error handling** (8 fixes): CG/PCG breakdown warning; J2 radial return stall guard; emitted CG failure counter; FLOPS extraction sentinel (-1.0); reference elastic Newton `for...else`; boundary codegen face area/axis/empty guards
- **Type validation** (7 types): `__post_init__` on `J2PowerLawMaterial`, `SVKMaterial`, `HexMesh`, `QuadratureRule`, `DirichletBC`, `NeumannBC`; `ReturnMappingResult` frozen; `HistoryFields` descriptive errors + duplicate guard
- **CI**: workspace install consistency across jobs and nightly benchmark failures downgraded from merge blockers to issue-creation events
- **Tests** (+25): Error path tests (radial return non-convergence, stalled Newton, degenerate element, invalid face); `__post_init__` validation tests for all 6 types; tolerance tightening (rigid body 1e-10, elastic FD tangent 1e-8)
- **Reference solvers**: Dirichlet BC tangent changed from zeroing to identity (`Kv[bc_mask] = v[bc_mask]`) for CG non-singularity
- **Comments**: Simo & Hughes §3.3 → §3.4; "unit normal" → "flow direction"; function rename `emit_constitutive_stub` → `emit_constitutive_update`; convention docs updated for quadrature point carve-out

### Not yet implemented

- Phase 2: LaTeX frontend parsing (blocked on NRPyLaTeX fork dependency)
- Plan B features beyond the MVP scope, including Updated Lagrangian (B1), curvilinear reference coordinates (B2), advanced constitutive models (B3/B4/B6), additional elements (B5), explicit dynamics (B7), and alternative backends (B8)
