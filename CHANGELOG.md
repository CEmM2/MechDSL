# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.2.1] - 2026-08-31

### Changed — packaging for PyPI

- **`mechdsl-core[verify]` slimmed and pinned**: `ti-runtime` and `algo2code` now carry version bounds (`>=0.2.1,<0.3`), and `torch` was removed from the extra — it was never imported anywhere (the AD oracle is finite-difference based), and dropping it spares ~2 GB per install.
- **`algo2code` metadata fix**: the empty `dependencies` declaration moved into `[project]` where PEP 621 expects it (it had been sitting under `[tool.uv]`).
- **License text ships in every artifact**: `LICENSE` copied into each package directory so sdists/wheels carry it.
- **Development status**: all packages now classify as `3 - Alpha`.
- **README**: PyPI installation section (lean core vs. full `[verify]` install).

## [0.2.0] - 2026-06-16

### Added — Fully-generated solver over a lean Taichi runtime

Every numerical kernel the Newton driver needs can now be generated from LaTeX by `algo2code` and injected over lean `ti_runtime` seams, with no NumPy in the hot paths.

- **`ti-runtime` package**: new neutral Taichi runtime package (`packages/ti-runtime/`) — vector primitives, Tier-1 `@ti.func` helpers, and solver/operator/integrator injection seams (`ti_runtime.{fields,hex8,seams,tensor_ti,vector_ops}`). `mechdsl-core` takes a production dependency on it via the `verify` extra; `algo2code` joins the same extra.
- **Matrix-free tangent operator seam**: `% type A callable` (a.k.a. `A:callable`) emits an in-place `A(out, p)` matching the `ti_runtime` `apply_A(out, x)` contract — no dense `A` field, no inner matvec loop — injected via `LinearSolveContext.set_operator`. `local_tangent` einsum emits an `@ti.kernel` matvec. Proven for the elastic operator and the dissipative J2 algorithmic tangent.
- **Generated linear solver + Jacobi preconditioner seam**: PCG injected via `set_solver`, Jacobi via `set_preconditioner`. Opt-in: `get_default_solver()` still returns the imported `ScipyCGSolver` as the default fallback — selecting the all-Taichi seam path is explicit.
- **Time-integration seam**: Newmark-β / HHT integrators injected via `TimeIntegrationContext.set_integrator` / `step`.

### Added — Integration façade (Tier-1)

A stable, machine-readable surface for driving MechDSL programmatically from external tools.

- **`mechdsl.integration` façade**: new package exposing five entry points — `capabilities()`, `model_catalog()`, `compile_from_sources(*, problem_source, energy_source, energy_file, profile)`, `transpile_algorithm(algpseudocode, backend)`, and `verify(kind, params)`. The façade wraps existing entry points (`compile_latex`, `algo2code.transpile`, the verify harness) and returns JSON-serialisable summaries; no IR layer is bypassed.
- **Taichi-free Tier-1 contract**: `capabilities()` declares `taichi_required_for: ["verify"]`; importing the module and calling the other four entry points never fires `ti.init`. All heavy imports are lazy, and the invariant is proven by fresh-interpreter subprocess guards. `model_catalog()` enumerates **12 constitutive models**.
- **`verify()` kinds**: `patch_test`, `rigid_body`, `ad_oracle_svk`, `ad_oracle_j2`, and `benchmark` (cantilever / cook_membrane over `mechdsl.verify.benchmarks`). `compile_from_sources` returns a JSON-safe `element_ir_summary` plus `content_hash` (semantic IR only — excludes emitted source).
- **Catalog hardening**: `model_catalog()` is memoised and returns per-call deep copies; model introspection fails loudly instead of silently returning empty results.
- **`verify('benchmark', …)` convergence**: `passed` now requires `relative_error <= tolerance` when the benchmark compared against a reference — previously it only checked the solve ran to completion. New `details` keys: `relative_error`, `tolerance`, `reference_checked`.

### Added — Boundary conditions, math grammar, and generated plasticity

- **Neumann boundary directive flow into emitted code**: `BoundaryCondition.traction` widened to `str | tuple[float, float, float] | None`; new `surface_tag` field; literal-baked and parametric `f_ext` kernel emitters added to `mechdsl.codegen.taichi_printer`; `compile_latex` now surfaces `bundle.f_ext_kernel`. Golden coverage included.
- **NRPyLaTeX math grammar integration**: NRPyLaTeX 1.4.0 wired through `mechdsl.symbolic.nrpylatex_bridge`; rank-2 surrogate algorithms cover SVK PK1 emission and J2 yield (`σ:σ`) until the upstream parser supports `\det` / `\log` / `\sqrt(s:s)`. Round-trip test suite included.
- **`algo2code` radial-return substitution**: the J2 power-law radial-return scalar Newton loop is authored in algpseudocode (`examples` + `dev/algorithms/radial_return_j2.tex`); `mechdsl.lib.plasticity` consumes `algo2code.transpile(..., backend="taichi")` at module load — the imported algorithm is the runtime function, not a hand translation. Feature-flag dispatcher (`MECHDSL_USE_IMPORTED_RR`).
- **`docs` pytest-marker tier**: `@pytest.mark.docs` registered for documentation-anchor / contract tests, routed by a dedicated CI job.

### Fixed — `algo2code` parser

- **Multi-letter scratch identifiers**: `expr_parser.LETTER` regex broadened from `[a-zA-Z]` to `[a-zA-Z][a-zA-Z0-9]*` so identifiers like `ap`, `Hp`, `tol`, `sig_eq` tokenize as single names.
- **Binary `/` in expressions**: `parse_term` now recognises the `SLASH` token (previously dropped, e.g. `a + b / c` parsed as `a + b`).
- **Scalar-only algorithms**: `taichi_codegen._emit_driver` no longer emits the dangling `n = b.shape[0]` line when no vector argument is present.

### Added — LaTeX-first contract

- **Canonical entry point**: `mechdsl.compile_latex(source: str, profile: str = "mvp") -> ArtifactBundle` parses `% mechanics` directives, adapts the resulting context dict to a `ProblemIR`, and forwards through the existing pipeline. `mechdsl.compile` (legacy programmatic path) is preserved verbatim. Allowed profile set is exposed as `mechdsl.ALLOWED_PROFILES`.
- **`ProblemIR` semantic enrichment**: four new optional frozen dataclasses — `FieldSpec`, `DomainSpec`, `MeshContract`, `ResidualContract` — exposed from `mechdsl.ir.mechanics_ir`, carried by `ProblemIR` with safe defaults and full `to_dict`/`from_dict` round-tripping of both legacy and enriched dicts.
- **`FieldSpec.kind` validation**: rejects out-of-vocabulary values; allowed set exposed as `ALLOWED_FIELD_KINDS = frozenset({"scalar", "vector", "tensor"})`.
- **Immutable enrichment metadata**: nested metadata dicts wrapped in `MappingProxyType` so the frozen-dataclass invariant extends through nested mutation.
- **Tier policy and stability contract**: new `## Support tiers` and `### Stability policy` README sections. Two tiers: `MVP-stable` (Hex8 + Total Lagrangian + Taichi backend + SVK/J2-power-law) vs `experimental` (MFEM/MOOSE codegen, explicit dynamics, non-MVP materials, non-canonical elements), with module-docstring markers on experimental modules.
- **Frontend architectural split**: `mechdsl/frontend/ARCHITECTURE.md` documents NRPyLaTeX as the parser of record vs the local adapter / normalizer / validator triad.
- **README Quickstart**: leads with the `compile_latex` LaTeX-source example; the programmatic `build_context` path moves to a secondary subsection.
- **LaTeX-source contract tests**: end-to-end suites that begin from a real LaTeX source and reach an `ArtifactBundle` (SVK + J2 power-law), plus 10 negative paths through `compile_latex` (unsupported constructs, malformed directives, index semantics, stable-message contract).
- **MVP-stable subset contract**: new `MVP_STABLE_SUBSET` constant in `mechdsl.ir.mechanics_ir` enumerates every `ProblemIR` axis covered by the canonical compile path; `ProblemIR.assert_mvp_stable() / is_mvp_stable()` enforce it at the IR boundary (`MvpSubsetViolation` subclasses `UnsupportedError`). Documented in `mechdsl/ir/ARCHITECTURE.md`.
- **Canonical context-dict adapter**: `ProblemIR.from_context()` and `BoundaryCondition.from_context()` classmethods replace three drifted private duplicates; legacy `region`/`face` and `dofs`/`components` aliases accepted.
- **Targeted IR validation**: six new construction-time checks on `ProblemIR.__post_init__` (duplicate boundary names, out-of-range BC component indices, duplicate coordinate/field names, BC `field_name` consistency), plus required-material-parameter checking via `assert_mvp_stable()` on the compile path.
- **Centralized boundary/domain semantic assumptions**: `ProblemIR.required_region_tags()` and `derived_mesh_contract()` expose the "BC name == mesh boundary tag" assumption as a single source of truth; `mechdsl.solver.mesh_io.validate_mesh_against_contract()` raises `BoundaryRegionError` at the boundary instead of a deep `KeyError` in codegen.
- **`ElementIR` execution-contract enrichment**: four new optional frozen dataclasses — `GeometrySummary`, `MaterialEvalContract` (with stress/strain-measure allowlists), `LocalForceDescriptor`, `LocalTangentDescriptor` — carried by `ElementIR` with construction-time consistency checks (mismatched `n_dof` / `n_quad`, TL/UL stress-measure conflicts) and full `to_dict`/`from_dict` round-tripping.
- **`EinsumSpec` / `LocalisationResult` demoted to derived views**: explicitly documented as derived optimization views over `ElementIR`; new `LocalisationResult.from_element_ir(element_ir, problem_ir)` materialises the optimizer-view bundle.
- **Lowering emits enriched `ElementIR` first**: `localise()` emits the enriched IR, then derives the einsum optimizer view; `ArtifactBundle.from_pipeline` surfaces the contract blocks in `element_ir_summary` with clean round-tripping of pre-enrichment bundles.
- **Deterministic lowering rejections**: new `LocalisationError(UnsupportedError, ValueError)` re-exported from `mechdsl.lowering`; rejections fire axis-by-axis (formulation → element → material) and every message names the offending construct and the roadmap phase that adds support.
- **Artifact bundling reflects enriched IR ownership**: new `ArtifactBundle.element_ir_dict` field carries the canonical `ElementIR.to_dict()` contract surface; `content_hash` deliberately unchanged so legacy goldens survive verbatim.

### Added — Verification benchmarks

- **Thick cylinder benchmark** (TL × SVK × Hex8): radial and hoop stress compared against Lamé closed-form; 5% gate on peak hoop stress (`mechdsl.verify.benchmarks.thick_cylinder`)
- **Necking bar benchmark** (TL × J2 × Hex8): load-displacement history compared against Simo & Hughes reference and committed golden within 2% (`mechdsl.verify.benchmarks.necking_bar`)
- **Notched bar benchmark** (TL × Lemaitre × Hex8): full load-displacement history + damage-field sampling; 10% regression gate; damage localises at notch-root element (`mechdsl.verify.benchmarks.notched_bar`)
- **HGO fiber-strip benchmark** (TL × HGO × Hex8): uniaxial FEM stress compared against closed-form HGO reference via damped-Newton lateral-stretch solve; 5% gate at multiple stretch levels (`mechdsl.verify.benchmarks.hgo_strip`)
- **`mechdsl.verify.benchmarks` module**: unified `BenchmarkResult` dataclass + kwargs-injection contract for all four benchmarks; `verify` package remains free of `tests/` imports

### Added — Contraction-Family Registry

- **8-family taxonomy**: `Family` enum classifying all emitted einsum strings — `DISPLACEMENT_GRADIENT`, `FORCE_INTEGRATION`, `MATERIAL_TANGENT_CONTRACTION`, `STRAIN_ENERGY`, `MASS_MATRIX`, `GEOMETRIC_STIFFNESS`, `KINEMATIC_INTEGRATION`, `FALLBACK` — enabling family-aware dispatch and JIT-budget planning (`mechdsl.codegen.family_registry`)
- **Family-aware emission dispatch**: backend printers select optimised code paths per family; rollback flag re-routes to the generic path on unsupported families
- **JIT budget regression suite**: parametric test grid over all (element × material × backend) triples; emitted line counts checked against the 512 / 2000 / 5000 limits

### Added — MFEM + MOOSE Backends (experimental)

- **MFEM printer**: C++ `NonlinearFormIntegrator` + `BilinearFormIntegrator` emission; Voigt conversion helpers; CMakeLists template; MPI-compatible output (`mechdsl.codegen.mfem_printer`)
- **MOOSE printer**: `ComputeStressBase` + `RankTwoTensor` emission; MOOSE input-file template; material-block code generation (`mechdsl.codegen.moose_printer`)
- **Cross-backend verification**: Taichi vs MFEM vs MOOSE patch-test equivalence within relative tolerance; mesh-exporter utilities shared across all three backends

### Added — Explicit Dynamics (experimental)

- **Lumped mass matrix**: HRZ row-sum lumping for Hex8 (`mechdsl.solver.mass`)
- **Central-difference explicit driver**: Courant-stable velocity-Verlet loop with diagonal mass inversion and residual-force assembly (`mechdsl.solver.explicit`)
- **Critical time step helper**: `courant_dt(mesh, E, nu, rho)` from minimum element characteristic length and longitudinal wave speed
- **Free vibration cross-check**: explicit driver verified against implicit quasi-static reference on a cantilever beam

### Added — Continuum Damage

- **Lemaitre damage model**: scalar isotropic damage coupled to J2 power-law plasticity; effective-stress principle with strain equivalence; de Souza Neto triaxiality factor; nucleation threshold `eps_D`; clamped at `D_MAX = 1 − 1e-6` (`mechdsl.symbolic.models.lemaitre`)
- **History field integration**: Lemaitre `D` field tracked through Newton iterations; element deletion assembly at `D >= D_crit`
- **Notched bar localisation test**: D=0 regression; damage confirmed to localise at the notch-root element

### Added — Additional Elements

- **Tet4 linear tetrahedron**: 4-node element, 1-point Gauss quadrature (`mechdsl.codegen.tet4_tables`)
- **Tet10 quadratic tetrahedron**: 10-node serendipity, 4-point Gauss quadrature (`mechdsl.codegen.tet10_tables`)
- **Hex20 serendipity**: 20-node element, 27-point Gauss quadrature (`mechdsl.codegen.hex20_tables`)
- **Hex8 reduced integration**: 1-point centre Gauss for hourglass-prone analyses (`mechdsl.codegen.hex8_reduced_tables`)
- **Flanagan-Belytschko hourglass control**: stabilisation for reduced-integration Hex8 (`mechdsl.codegen.hourglass`)
- **ElementFactory API**: `ElementFactory.create(element_type, integration_scheme)` — uniform construction replacing element-specific imports

### Added — Hyperelastic Models

- **Neo-Hookean model**: isochoric-volumetric split (`Psi = mu/2*(I1_bar-3) + kappa/2*(J-1)^2`); analytic PK2 stress and closed-form 4th-order tangent; `NeoHookeanMaterial.from_E_nu()` convenience factory (`mechdsl.symbolic.models.neo_hookean`)
- **Mooney-Rivlin model**: two-parameter `(C10, C01)` with volumetric penalty; analytic stress and FD tangent (`mechdsl.symbolic.models.mooney_rivlin`)
- **Ogden model**: spectral-stretch N-term series; robust positive-definiteness checks; symmetric-perturbation FD tangent (`mechdsl.symbolic.models.ogden`)
- **HGO anisotropic model**: Holzapfel-Gasser-Ogden dispersion model with two fiber families; fiber activation gate (`E_fi > 0`); FD tangent robust at the activation boundary (`mechdsl.symbolic.models.hgo`)
- **AD oracle**: automatic-differentiation cross-check verifying PK2 stress and Voigt tangent for all four models against FD and AD references

### Added — Viscoplasticity

- **Perzyna viscoplasticity**: backward-Euler return map with overstress function; rate-dependent yield; consistent algorithmic tangent (`mechdsl.symbolic.models.perzyna`)
- **Johnson-Cook flow stress**: strain-rate sensitivity, adiabatic heating via Taylor-Quinney coefficient, JC parameter validation (`mechdsl.symbolic.models.johnson_cook`)
- **Rate-sensitivity acceptance suite**: Perzyna collapses to J2 in the quasi-static limit; rate/thermal cross-checks

### Added — Updated Lagrangian

- **Updated Lagrangian formulation**: spatial shape gradients, Cauchy stress residual, and Jaumann material + geometric stiffness tangent emission — full UL codegen alongside existing Total Lagrangian
- **ConfigurationIR extension**: `Formulation.UPDATED_LAGRANGIAN` variant with `reference_frame` and `stress_measure` on `ProblemIR`
- **Objective stress rates**: Jaumann and Truesdell rate functions with full-F Piola push-forward (`mechdsl.symbolic.objective_rates`)
- **Formulation switching**: `% mechanics set formulation updated_lagrangian` directive; `build_context` and codegen auto-infer configuration from formulation
- **TL/UL equivalence verification**: handwritten UL reference solver, rigid rotation invariance test, and TL-vs-UL displacement comparison within 1e-10

### Added — Convected Coordinates

- **Curvilinear reference configurations**: `MetricField` wrapper with symmetry validation, convected metric `g_IJ = G_ref^T C G_ref`, symbolic metric inversion (`mechdsl.symbolic.convected`)
- **Differential geometry**: covariant/contravariant base vectors, Christoffel symbols `Gamma^K_{IJ}` with Cartesian fast-path, covariant derivatives for contravariant vectors, covariant vectors, and rank-2 tensors
- **Metric-assign directives**: `% mechanics assign gDD --metric_current` parser directive via NRPyLaTeX integration
- **Curvilinear patch test**: SVK stress through convected pathway verified constant across 15 (r, theta) points; Cartesian-convected equivalence within 1e-13

### Changed

- **`build_context()`** is now documented as the **secondary** programmatic entry point. It remains importable and functional; `compile_latex` is the canonical surface for new code and documentation.

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
- **Examples and docs**: README installation/quickstart/architecture guide and runnable examples for cantilever, plastic uniaxial, Cook's membrane, necking bar, and patch test
- **CI tiers**: fast push validation, broader PR validation, and nightly e2e benchmark coverage

### Fixed

- **Taichi codegen** (5 critical fixes): J2 Newton `ti.static` → runtime for `break` support; quadrature loop to `ti.static` for Python list access; Newton non-convergence raises `RuntimeError`; NaN/Inf guard on residual; node loops to runtime per convention
- **Error handling** (8 fixes): CG/PCG breakdown warning; J2 radial return stall guard; emitted CG failure counter; FLOPS extraction sentinel (-1.0); reference elastic Newton `for...else`; boundary codegen face area/axis/empty guards
- **Type validation** (7 types): `__post_init__` on `J2PowerLawMaterial`, `SVKMaterial`, `HexMesh`, `QuadratureRule`, `DirichletBC`, `NeumannBC`; `ReturnMappingResult` frozen; `HistoryFields` descriptive errors + duplicate guard
- **Reference solvers**: Dirichlet BC tangent changed from zeroing to identity (`Kv[bc_mask] = v[bc_mask]`) for CG non-singularity
