# Implementation Plan B — MVP → Full Hyperelastic-Viscoplastic FEM

**Starting point:** Working MVP from Plan A — 3D TL Hex8 with convected coordinates, SVK + power-law J2, Newton-Raphson with imported linear solver.

**End state:** A framework supporting:
- Both Total Lagrangian and Updated Lagrangian formulations
- Full convected coordinate kinematics with Christoffel symbols and covariant derivatives
- Hyperelastic models (neo-Hookean, Mooney-Rivlin, Ogden, HGO)
- Rate-dependent viscoplasticity (Perzyna, Johnson-Cook)
- Continuum damage (Lemaitre)
- Multiple element types (Hex8, Hex20, Tet10) with reduced integration
- Explicit and implicit time integration
- MFEM and MOOSE backend printers

**Acceptance test:** Solve a Taylor impact problem (cylindrical bar striking a rigid wall, Johnson-Cook viscoplasticity, large deformation, Hex8 with hourglass control) and reproduce the final deformed shape and plastic strain distribution from literature within 5%.

---

## Phase B1 — Updated Lagrangian formulation

**Duration:** 2 weeks

**Prerequisite:** Plan A complete (TL working with convected coordinates)

### B1.1  UL residual and tangent

The UL residual integrates over the current (deformed) configuration:

$$
R_i = \int_\Omega \sigma_{ij}\,\frac{\partial v_i}{\partial x_j}\,d\Omega - \int_\Omega b_i\,v_i\,d\Omega
$$

Implementation:
- Compute spatial shape function gradients: $\frac{\partial N_a}{\partial x_i} = \frac{\partial N_a}{\partial \xi_j}\,j^{-1}_{ji}$ where $j_{ij} = \sum_a \frac{\partial N_a}{\partial \xi_j}\,x_{ai}$ is the Jacobian with respect to current coordinates.
- Stress measure: Cauchy $\sigma$ (spatial), not PK2.
- Volume: $dV = \det(j)\,d\xi$ (current configuration).

### B1.2  UL tangent operator

The linearised UL tangent has two terms:

$$
K_{aibj} = \int_\Omega \frac{\partial N_a}{\partial x_k}\,c^{Jau}_{kijl}\,\frac{\partial N_b}{\partial x_l}\,dV + \int_\Omega \sigma_{ij}\,\frac{\partial N_a}{\partial x_j}\,\frac{\partial N_b}{\partial x_i}\,dV
$$

where $c^{Jau}$ is the Jaumann rate tangent.

### B1.3  Configuration-aware IR refactor

Extend Mechanics IR with `ConfigurationIR` entity:
- Fields tagged as reference or current config
- Gradients tagged as material or spatial
- Stress measures tagged with configuration
- Element IR geometry mapping switches between reference (TL) and current (UL) Jacobians

### B1.4  Objective stress rates

Implement for rate-form constitutive models:

| Rate | Formula | Use case |
|------|---------|----------|
| Jaumann | $\overset{\nabla}{\sigma}_{ij} = \dot{\sigma}_{ij} - W_{ik}\sigma_{kj} - \sigma_{ik}W_{kj}$ | Default for metals |
| Truesdell | $\overset{\triangle}{\sigma}_{ij} = \dot{\sigma}_{ij} - L_{ik}\sigma_{kj} - \sigma_{ik}L_{jk} + \sigma_{ij}\mathrm{tr}(D)$ | Alternative |
| Green-Naghdi | $\overset{\circ}{\sigma}_{ij} = \dot{\sigma}_{ij} - \Omega_{ik}\sigma_{kj} - \sigma_{ik}\Omega_{kj}$ | Polar decomposition based |

### B1.5  Formulation switching

Add `% mechanics formulation updated_lagrangian` directive. The code generator produces either TL or UL element kernels. The constitutive model interface is the same — only the kinematic driver and stress measure differ.

Test: TL vs UL on cantilever beam, identical tip displacement within 1e-8.

**Exit criterion B1:** UL solver produces identical results to TL on shared benchmarks. Objective rates verified via rigid rotation test.

---

## Phase B2 — Full convected coordinate framework

**Duration:** 2–3 weeks

**Note:** The MVP builds the basic convected infrastructure (metric tensors, convected-form kinematics with Cartesian reference). This phase extends to **curvilinear reference configurations** with non-trivial Christoffel symbols.

### B2.1  Covariant and contravariant bases

In the convected coordinate system $\theta^I$:

$$
\mathbf{g}_I = \frac{\partial \mathbf{x}}{\partial \theta^I} = \mathbf{F}\,\mathbf{G}_I
$$

Implement `compmech.symbolic.convected`:
- Metric tensors: $G_{IJ}$, $g_{IJ}$ (non-trivial for curvilinear reference)
- Inverse metric: $g^{IJ}$
- Contravariant bases: $\mathbf{g}^I = g^{IJ}\,\mathbf{g}_J$

### B2.2  Christoffel symbols

$$
\Gamma^K_{IJ} = \frac{1}{2}g^{KL}\left(\frac{\partial g_{IL}}{\partial \theta^J} + \frac{\partial g_{JL}}{\partial \theta^I} - \frac{\partial g_{IJ}}{\partial \theta^L}\right)
$$

### B2.3  Covariant derivatives

$$
\nabla_I v^J = \frac{\partial v^J}{\partial \theta^I} + \Gamma^J_{IK}\,v^K
$$

### B2.4  NRPyLaTeX integration

Leverage NRPyLaTeX's native covariant/contravariant index support:
- `% mechanics assign gDD --metric_current` → current metric
- `% mechanics assign GDD --metric_reference` → reference metric
- Auto-compute Christoffel symbols when metric is assigned

### B2.5  Verification

- Curvilinear patch test: uniform strain in curvilinear coordinates → exact stress
- Cartesian equivalence: convected and Cartesian formulations on Cartesian mesh → identical results within 1e-12

**Exit criterion B2:** Convected formulation passes patch test on curvilinear mesh.

---

## Phase B3 — Viscoplasticity

**Duration:** 2 weeks

### B3.1  Perzyna viscoplasticity

Rate-dependent yield with implicit backward Euler.

### B3.2  Johnson-Cook with rate dependence

Extend return mapping with Johnson-Cook flow stress and adiabatic temperature evolution.

### B3.3  Consistent viscoplastic tangent

Algorithmic tangent incorporating viscoplastic regularisation.

### B3.4  Verification

- Rate sensitivity, quasi-static limit, thermal softening
- Taylor impact test: reproduced within 5%

**Exit criterion B3:** Taylor impact test passes.

---

## Phase B4 — Advanced hyperelasticity

**Duration:** 1–2 weeks

### B4.1  Models

- Neo-Hookean: $\Psi = (\mu/2)(\bar{I}_1 - 3) + (\kappa/2)(J-1)^2$
- Mooney-Rivlin: $\Psi = C_1(\bar{I}_1 - 3) + C_2(\bar{I}_2 - 3) + (\kappa/2)(J-1)^2$
- Ogden: eigenvalue-based, requires 3×3 symmetric eigendecomposition
- HGO (anisotropic): fiber directions as per-element data

### B4.2  Verification

Each model: AD oracle + uniaxial against closed-form 1D solution.

**Exit criterion B4:** All models pass AD oracle and uniaxial verification.

---

## Phase B5 — Additional elements and integration rules

**Duration:** 1–2 weeks

### B5.1  Elements

- Tet4 (4-node, 1-point quadrature)
- Tet10 (10-node quadratic, 4-point quadrature)
- Hex20 (20-node serendipity, 3×3×3 quadrature)
- Hex8 reduced (1-point, with Flanagan-Belytschko hourglass control)

### B5.2  Element factory

```python
element = ElementFactory.create('hex8', integration='full')
element = ElementFactory.create('hex8', integration='reduced', hourglass='flanagan_belytschko')
```

**Exit criterion B5:** Patch test passes for all element types. Hourglass test passes for reduced Hex8.

---

## Phase B6 — Continuum damage

**Duration:** 1–2 weeks

### B6.1  Lemaitre CDM

Damage variable $D \in [0, 1)$, coupled with plasticity. Element deletion at $D > D_{crit}$.

### B6.2  Verification

- $D = 0$ regression against standard J2
- Notched bar: damage localises at notch root

**Exit criterion B6:** Notched bar matches qualitative expectations. D=0 matches J2.

---

## Phase B7 — Explicit dynamics

**Duration:** 1 week

### B7.1  Central difference

Lumped mass, critical time step computation, no linear solver needed.

### B7.2  Verification

- Free vibration period vs analytical
- Explicit/implicit cross-check (same quasi-static result)

**Exit criterion B7:** Free vibration period within 1%.

---

## Phase B8 — MFEM and MOOSE backend printers

**Duration:** 2–3 weeks

### B8.1  MFEM printer

Generate C++ `NonlinearFormIntegrator`. Handle Voigt convention conversion. MPI-parallel.

### B8.2  MOOSE printer

Generate `ComputeStressBase` subclass. `RankTwoTensor`/`RankFourTensor` mapping. Input file generation.

### B8.3  Cross-backend verification

Same problem, three backends, displacement field max difference < 1e-8.

**Exit criterion B8:** Three backends produce matching results.

---

## Phase B8b — Contraction template tuning

**Duration:** 3–5 days

With multiple element types (B5) and backend printers (B8) in place, evolve the einsum tier system into named contraction-family templates (see `09-EINSUM-OPTIMISER.md §9`). The tier system remains the scheduling decision; template families become the realisation decision (what shape the emitted code takes per backend).

**Exit criterion B8b:** All existing element types pass budget with named template families. No performance regression vs tier-only emission.

---

## Phase B9 — Full V&V suite

**Duration:** 1–2 weeks

### B9.1  MMS convergence study

For each element type × constitutive model: verify convergence rates.

### B9.2  Physical benchmark suite

| Problem | Formulation | Material | Element | Reference |
|---------|-------------|----------|---------|-----------|
| Cantilever (elastic) | TL, UL | SVK / Neo-Hookean | Hex8, Tet10, Hex20 | EB theory |
| Cook's membrane | TL, UL | J2 power-law | Hex8, Tet10 | de Souza Neto |
| Thick cylinder | TL | SVK | Hex8 | Lamé solution |
| Plate with hole | TL | SVK | Hex8, Hex20 | Kirsch $K_t = 3$ |
| Necking bar | TL | J2 + SVK | Hex8 | Simo & Hughes |
| Taylor impact | UL | JC viscoplastic | Hex8 (reduced) | Johnson & Cook |
| Notched bar | TL | Lemaitre damage | Hex8 | Literature |
| Fiber-reinforced strip | TL | HGO | Hex8 | Holzapfel et al. |

### B9.3  Performance and regression

Wall-clock time, GPU utilisation, Newton/CG iteration counts. All benchmarks in nightly CI.

**Exit criterion B9:** All benchmarks pass. Convergence rates match theory. Cross-backend results agree.

---

## Total estimated duration: 12–18 weeks (from MVP completion)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| B1 Updated Lagrangian | 2 weeks | 2 weeks |
| B2 Full convected coordinates | 2–3 weeks | 5 weeks |
| B3 Viscoplasticity | 2 weeks | 7 weeks |
| B4 Advanced hyperelasticity | 1–2 weeks | 9 weeks |
| B5 Additional elements | 1–2 weeks | 11 weeks |
| B6 Damage | 1–2 weeks | 13 weeks |
| B7 Explicit dynamics | 1 week | 14 weeks |
| B8 MFEM + MOOSE printers | 2–3 weeks | 17 weeks |
| B9 Full V&V | 1–2 weeks | 18 weeks |

---

## Dependency graph

```
Plan A (MVP) ──→ B1 (UL) ──→ B2 (full convected) ──→ B9 (V&V)
                  │                                     ↑
                  ├──→ B3 (viscoplasticity) ────────────┤
                  │                                     │
                  ├──→ B4 (hyperelastic models) ────────┤
                  │                                     │
                  ├──→ B5 (elements) ───────────────────┤
                  │                                     │
                  ├──→ B6 (damage) ─────────────────────┤
                  │                                     │
                  ├──→ B7 (explicit dynamics) ──────────┤
                  │                                     │
                  └──→ B8 (MFEM/MOOSE) ────────────────┘
```

B3–B7 can proceed in parallel once B1 is complete. B2 (full convected) requires B1 but is independent of B3–B7. B8 can start after any constitutive model is working. B9 is the final integration.
