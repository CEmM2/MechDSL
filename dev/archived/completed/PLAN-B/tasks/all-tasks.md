# PLAN-B Task Index

**Plan source:** `dev/design_docs/PLAN-B.md`
**Phases:** 10 (B1 through B9, with B8b numbered as Phase 9 and B9 as Phase 10)
**Total tasks:** 50
**Starting point:** Plan A MVP complete (3D TL Hex8, SVK + J2 power-law, analytical tangent in generated code — see commits `f1110a0`, `2ae532a`).

## Phase-ID mapping

Aut_Faciam requires sequential integer phase IDs. The plan uses B-prefixed sub-section numbering. Original names are preserved in the context summaries:

| Phase ID | Plan section | Phase name |
|---|---|---|
| 1 | B1 | Updated Lagrangian formulation |
| 2 | B2 | Full convected coordinate framework |
| 3 | B3 | Viscoplasticity |
| 4 | B4 | Advanced hyperelasticity |
| 5 | B5 | Additional elements and integration rules |
| 6 | B6 | Continuum damage |
| 7 | B7 | Explicit dynamics |
| 8 | B8 | MFEM and MOOSE backend printers |
| 9 | B8b | Contraction template tuning |
| 10 | B9 | Full V&V suite |

## Task table

| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |
|---|---|---|---|---|---|
| P1-1 | 1 | ConfigurationIR extension (reference/current tagging) | — | P1-2, P1-3, P1-4, P1-5, P2-1, P3-1, P4-1, P4-2, P4-3, P4-4, P5-1, P5-2, P5-3, P5-4, P6-1, P7-1, P8-1, P8-2 | 48-55 |
| P1-2 | 1 | UL kinematics (spatial shape gradients, current Jacobian) | P1-1 | P1-3, P1-4 | 25-36 |
| P1-3 | 1 | UL residual emission (Cauchy stress, current-config volume) | P1-2 | P1-4, P1-6 | 27-36 |
| P1-4 | 1 | UL tangent operator emission (Jaumann + geometric stiffness) | P1-3, P1-5 | P1-6 | 38-46 |
| P1-5 | 1 | Objective stress rates (Jaumann, Truesdell, Green-Naghdi) | P1-1 | P1-4, P1-7 | 56-65 |
| P1-6 | 1 | Formulation switching (directive + codegen dispatch) | P1-3, P1-4 | P1-7 | 66-70 |
| P1-7 | 1 | TL/UL equivalence + rigid rotation tests | P1-5, P1-6 | P10-2, P10-3, P10-7 | 70-72 |
| P2-1 | 2 | Covariant/contravariant bases + metric tensors | P1-1 | P2-2, P2-4 | 82-94 |
| P2-2 | 2 | Christoffel symbols from metric | P2-1 | P2-3, P2-4 | 95-99 |
| P2-3 | 2 | Covariant derivatives (vectors and tensors) | P2-2 | P2-5 | 101-106 |
| P2-4 | 2 | NRPyLaTeX metric-assignment directives (`% mechanics assign gDD/GDD`) | P2-1, P2-2 | P2-5 | 107-112 |
| P2-5 | 2 | Curvilinear patch test + Cartesian equivalence | P2-3, P2-4 | P10-1 | 114-119 |
| P3-1 | 3 | Perzyna viscoplasticity with backward Euler return map | P1-1 | P3-2, P3-3 | 127-129 |
| P3-2 | 3 | Johnson-Cook flow stress + adiabatic temperature evolution | P3-1 | P3-3, P3-4 | 131-133 |
| P3-3 | 3 | Consistent viscoplastic algorithmic tangent | P3-2 | P3-4 | 135-137 |
| P3-4 | 3 | Rate sensitivity + quasi-static limit + thermal softening tests | P3-3 | P10-7 | 139-143 |
| P4-1 | 4 | Neo-Hookean hyperelastic model | P1-1 | P4-5, P10-2 | 152-152 |
| P4-2 | 4 | Mooney-Rivlin hyperelastic model | P1-1 | P4-5 | 153-153 |
| P4-3 | 4 | Ogden hyperelastic model (with symmetric eigendecomposition) | P1-1 | P4-5 | 154-154 |
| P4-4 | 4 | HGO anisotropic hyperelastic model (per-element fiber directions) | P1-1 | P4-5, P10-9 | 155-155 |
| P4-5 | 4 | AD oracle + uniaxial verification for all hyperelastic models | P4-1, P4-2, P4-3, P4-4 | — | 157-161 |
| P5-1 | 5 | Tet4 element (4-node, 1-point quadrature) | P1-1 | P5-6, P5-7 | 171-171 |
| P5-2 | 5 | Tet10 element (10-node quadratic, 4-point quadrature) | P1-1 | P5-6, P5-7, P10-2, P10-3 | 172-172 |
| P5-3 | 5 | Hex20 element (20-node serendipity, 3×3×3 quadrature) | P1-1 | P5-6, P5-7, P10-2, P10-5 | 173-173 |
| P5-4 | 5 | Hex8 reduced integration (1-point quadrature) | P1-1 | P5-5, P5-6, P10-7 | 174-174 |
| P5-5 | 5 | Flanagan-Belytschko hourglass control for reduced Hex8 | P5-4 | P5-6, P5-7, P10-7 | 174-174 |
| P5-6 | 5 | ElementFactory (uniform element/integration/hourglass API) | P5-1, P5-2, P5-3, P5-5 | P5-7, P9-1 | 176-183 |
| P5-7 | 5 | Patch test for all elements + hourglass sanity test | P5-6 | P9-1, P10-1 | 185-185 |
| P6-1 | 6 | Lemaitre damage variable + evolution equation | P1-1 | P6-2 | 193-193 |
| P6-2 | 6 | Plasticity coupling + element deletion at D > D_crit | P6-1 | P6-3 | 193-193 |
| P6-3 | 6 | D=0 regression + notched bar verification | P6-2 | P10-8 | 196-199 |
| P7-1 | 7 | Lumped mass + central difference integrator | P1-1 | P7-2 | 210-211 |
| P7-2 | 7 | Critical time step computation | P7-1 | P7-3 | 211-211 |
| P7-3 | 7 | Free vibration + explicit/implicit cross-check | P7-2 | P10-7 | 213-217 |
| P8-1 | 8 | MFEM printer (C++ NonlinearFormIntegrator + Voigt + MPI) | P1-1 | P8-3, P9-1 | 227-229 |
| P8-2 | 8 | MOOSE printer (ComputeStressBase + RankTwoTensor + input files) | P1-1 | P8-3, P9-1 | 231-233 |
| P8-3 | 8 | Cross-backend verification (Taichi/MFEM/MOOSE ≤ 1e-8) | P8-1, P8-2 | P9-1 | 235-237 |
| P9-1 | 9 | Design named contraction-family templates (per backend × element) | P5-6, P5-7, P8-1, P8-2, P8-3 | P9-2 | 244-249 |
| P9-2 | 9 | Refactor einsum_optimizer to emit via template families | P9-1 | P9-3 | 247-249 |
| P9-3 | 9 | Budget regression test for all element × backend combos | P9-2 | P10-1 | 249-249 |
| P10-1 | 10 | MMS convergence study (every element × constitutive model) | P2-5, P5-7, P9-3 | P10-10 | 257-259 |
| P10-2 | 10 | Cantilever benchmark (TL/UL × SVK/Neo-Hookean × Hex8/Tet10/Hex20) | P1-7, P4-1, P5-2, P5-3 | P10-10 | 264-264 |
| P10-3 | 10 | Cook's membrane benchmark (TL × J2 × Hex8) | — | P10-10 | 265-265 |
| P10-4 | 10 | Thick cylinder benchmark (TL × SVK × Hex8) | P1-7 | P10-10 | 266-266 |
| P10-5 | 10 | Plate with hole benchmark (TL × SVK × Hex8/Hex20) | P5-3 | P10-10 | 267-267 |
| P10-6 | 10 | Necking bar benchmark (TL × J2+SVK × Hex8) | P1-7 | P10-10 | 268-268 |
| P10-7 | 10 | Taylor impact benchmark (UL × JC viscoplastic × reduced Hex8 + hourglass) | P1-7, P3-4, P5-5, P7-3 | P10-10 | 269-269 |
| P10-8 | 10 | Notched bar benchmark (TL × Lemaitre × Hex8) | P6-3 | P10-10 | 270-270 |
| P10-9 | 10 | Fiber-reinforced strip benchmark (TL × HGO × Hex8) | P4-4 | P10-10 | 271-271 |
| P10-10 | 10 | Performance + regression harness + nightly CI integration | P10-1, P10-2, P10-3, P10-4, P10-5, P10-6, P10-7, P10-8, P10-9 | — | 273-276 |

## Dependency-graph sanity checks

**No circular dependencies.** The graph is a DAG. Phases 1 through 10 form a topological chain with cross-phase parallelism permitted after Phase 1:

```
           ┌─→ P2 (convected, B2) ───┐
           │                          │
           ├─→ P3 (viscoplastic) ─────┤
           ├─→ P4 (hyperelastic) ─────┤
Plan A → P1 ─┼─→ P5 (elements) ─────────┼─→ P10 (V&V)
           ├─→ P6 (damage) ───────────┤     ↑
           ├─→ P7 (explicit) ─────────┤     │
           └─→ P8 (MFEM/MOOSE) ───────┴─→ P9 (templates) ─┘
```

**Phase entry points.** Each non-first phase has one or more tasks whose `blocked_by` crosses the phase boundary back to a Phase 1 deliverable (typically `P1-1 ConfigurationIR`). This respects the plan's "B1 first, everything else parallel" structure.

**Cross-phase edges from the benchmark suite (P10-*).** Each benchmark depends on exactly the phases that deliver the required constitutive model, element type, or formulation:
- P10-2 Cantilever → P4-1 (Neo-Hookean), P5-2 (Tet10), P5-3 (Hex20), P1-7 (UL equivalence)
- P10-7 Taylor impact → P3-4 (JC viscoplastic), P5-5 (hourglass), P7-3 (explicit), P1-7 (UL)
- P10-8 Notched bar → P6-3 (Lemaitre verification)
- P10-9 Fiber strip → P4-4 (HGO)
- P10-10 final regression → all 9 individual benchmarks

**P9 (contraction templates)** depends on BOTH P5 (element variety) and P8 (backend variety) per the plan's explicit note at lines 244-247: "With multiple element types (B5) and backend printers (B8) in place, evolve the einsum tier system…". It also feeds P10-1 (MMS convergence) because the template system affects per-element JIT budgets.

**Parallel-execution cluster.** After P1 completes, seven phases (P2, P3, P4, P5, P6, P7, P8) can proceed in parallel. P9 waits for P5 + P8. P10 waits for everything.
