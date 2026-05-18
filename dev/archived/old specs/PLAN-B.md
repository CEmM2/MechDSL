# Implementation Plan B — MVP → Full Hyperelastic-Viscoplastic FEM

**Starting point:** Working MVP from Plan A — 3D TL Hex8, neo-Hookean + J2, Newton-Raphson with imported linear solver.

**End state:** A framework supporting:
- Both Total Lagrangian and Updated Lagrangian formulations
- Convected coordinate kinematics with metric tensors
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

**Prerequisite:** Plan A complete (TL working)

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

where $c^{Jau}$ is the Jaumann rate tangent (spatial, possesses both major and minor symmetries).

The geometric stiffness (second term) is the spatial analogue of the initial stress stiffness in TL. It uses current Cauchy stress and current configuration gradients.

### B1.3  Relationship between TL and UL tangents

For verification, the TL and UL formulations must produce identical results (they are equivalent variational statements). The tangent relationship is:

$$
c^{Jau}_{ijkl} = \frac{1}{J}\,F_{iI}\,F_{jJ}\,\mathbb{C}_{IJKL}\,F_{kK}\,F_{lL}
$$

Implement a comparison test: solve the same problem with TL and UL, verify displacement fields match to tolerance.

### B1.4  Objective stress rates

For rate-form constitutive models (plasticity, viscoplasticity), the stress rate must be objective. Implement:

| Rate | Formula | Use case |
|------|---------|----------|
| Jaumann | $\overset{\nabla}{\sigma}_{ij} = \dot{\sigma}_{ij} - W_{ik}\sigma_{kj} - \sigma_{ik}W_{kj}$ | Default for metals |
| Truesdell | $\overset{\triangle}{\sigma}_{ij} = \dot{\sigma}_{ij} - L_{ik}\sigma_{kj} - \sigma_{ik}L_{jk} + \sigma_{ij}\mathrm{tr}(D)$ | Alternative |
| Green-Naghdi | $\overset{\circ}{\sigma}_{ij} = \dot{\sigma}_{ij} - \Omega_{ik}\sigma_{kj} - \sigma_{ik}\Omega_{kj}$ | Polar decomposition based |

The Hughes-Winget midpoint algorithm (already implemented for TL corotational updates) handles the objective integration. The UL driver calls the same stress update infrastructure but uses spatial gradients for L, D, W.

### B1.5  Formulation switching

Add `% mechanics formulation updated_lagrangian` directive. The code generator produces either TL or UL element kernels based on the directive. The constitutive model interface is the same — only the kinematic driver and stress measure differ.

Test: TL vs UL on cantilever beam, identical tip displacement within 1e-8.

**Exit criterion B1:** UL solver produces identical results to TL on shared benchmarks. Objective rates verified via rigid rotation test.

---

## Phase B2 — Convected coordinate framework

**Duration:** 2–3 weeks

### B2.1  Covariant and contravariant bases

In the convected (material-embedded) coordinate system $\theta^I$, the covariant base vectors are:

$$
\mathbf{g}_I = \frac{\partial \mathbf{x}}{\partial \theta^I} = \mathbf{F}\,\mathbf{G}_I
$$

where $\mathbf{G}_I = \frac{\partial \mathbf{X}}{\partial \theta^I}$ are the reference base vectors.

Contravariant bases: $\mathbf{g}^I = g^{IJ}\,\mathbf{g}_J$ where $g^{IJ}$ is the inverse metric.

Implement `compmech.symbolic.convected`:
- Metric tensors: $G_{IJ} = \mathbf{G}_I \cdot \mathbf{G}_J$ (reference), $g_{IJ} = \mathbf{G}_I \cdot \mathbf{G}_J$ (current via $g_{IJ} = C_{IJ}$)
- Christoffel symbols: $\Gamma^K_{IJ} = \frac{1}{2}g^{KL}\left(\frac{\partial g_{IL}}{\partial \theta^J} + \frac{\partial g_{JL}}{\partial \theta^I} - \frac{\partial g_{IJ}}{\partial \theta^L}\right)$
- Covariant derivatives: $\nabla_I v^J = \frac{\partial v^J}{\partial \theta^I} + \Gamma^J_{IK}\,v^K$

### B2.2  Strain measures in convected coordinates

The Green-Lagrange strain in convected components:

$$
E_{IJ} = \frac{1}{2}(g_{IJ} - G_{IJ}) = \frac{1}{2}(C_{IJ} - \delta_{IJ})
$$

This is identical to the Cartesian TL expression when the reference configuration uses Cartesian coordinates, but generalises to curvilinear meshes.

The rate of deformation in convected coordinates:

$$
d_{IJ} = \frac{1}{2}\dot{g}_{IJ} = \frac{1}{2}(\dot{C}_{IJ})
$$

### B2.3  Stress in convected coordinates

The contravariant PK2 stress $S^{IJ}$ is work-conjugate to $E_{IJ}$:

$$
\mathcal{P} = S^{IJ}\,\dot{E}_{IJ}
$$

Cauchy stress in terms of convected PK2:

$$
\sigma^{ij} = \frac{1}{J}\,F^i{}_I\,S^{IJ}\,F^j{}_J
$$

### B2.4  NRPyLaTeX integration for convected notation

Leverage NRPyLaTeX's native covariant/contravariant index support (already handles upper/lower indices, metric raising/lowering). Extend with mechanics-specific semantics:

- `% mechanics assign gDD --metric_current` — current metric
- `% mechanics assign GDD --metric_reference` — reference metric
- Auto-compute Christoffel symbols when metric is assigned

This connects directly to NRPyLaTeX's existing `% assign gDD --metric` functionality from GR — we reuse the same infrastructure for continuum mechanics.

### B2.5  Verification

- Curvilinear patch test: prescribe uniform strain in curvilinear coordinates, verify exact stress recovery
- Equivalence test: convected and Cartesian formulations on a Cartesian mesh produce identical results

**Exit criterion B2:** Convected formulation passes patch test on curvilinear mesh. Matches Cartesian TL on regular mesh within 1e-12.

---

## Phase B3 — Viscoplasticity

**Duration:** 2 weeks

### B3.1  Perzyna viscoplasticity

Rate-dependent yield:

$$
\dot{\bar{\varepsilon}}_p = \frac{1}{\eta}\left\langle\frac{f}{\sigma_y}\right\rangle^m
$$

where $\eta$ is the viscosity parameter, $m$ is the rate exponent, and $f$ is the yield function overstress.

Algorithmic update: implicit backward Euler integration of the flow rule. Scalar Newton iteration on the viscoplastic multiplier $\Delta\lambda$ satisfying:

$$
\Delta\lambda = \frac{\Delta t}{\eta}\left(\frac{\sigma_{eq}^{tr} - 3\mu\Delta\lambda - \sigma_y(\bar{\varepsilon}_p^n + \Delta\lambda)}{\sigma_y}\right)^m
$$

### B3.2  Johnson-Cook with rate dependence

Extend the J2 return mapping from Plan A (A7) with Johnson-Cook flow stress:

$$
\sigma_y = (A + B\bar{\varepsilon}_p^n)(1 + C\ln\dot{\bar{\varepsilon}}_p^*)(1 - T^{*m})
$$

The rate $\dot{\bar{\varepsilon}}_p^*$ requires the time step $\Delta t$ and the plastic multiplier increment: $\dot{\bar{\varepsilon}}_p = \Delta\lambda / \Delta t$.

Temperature evolution (adiabatic):

$$
T^{n+1} = T^n + \frac{\beta}{\rho C_p}\,\sigma_y\,\Delta\lambda
$$

where $\beta$ is the Taylor-Quinney coefficient (typically 0.9).

### B3.3  Consistent viscoplastic tangent

The algorithmic tangent for viscoplasticity differs from rate-independent J2 because $\Delta\lambda$ depends on $\Delta t$:

$$
\mathbb{C}^{vp,alg} = \kappa\,\delta\otimes\delta + 2\mu\theta_{vp}\,\mathbb{I}^{dev} - 2\mu(\theta_{vp} - \bar{\theta}_{vp})\,n\otimes n
$$

where $\theta_{vp}$ and $\bar{\theta}_{vp}$ incorporate the viscoplastic regularisation through $\partial\Delta\lambda/\partial\sigma_{eq}^{tr}$.

### B3.4  Internal variable fields

Additional per-quadrature-point fields:
- `T[n_elem, n_quad]` — temperature
- `edot_p[n_elem, n_quad]` — plastic strain rate (for rate-dependent models)

### B3.5  Verification

- Rate sensitivity: increase loading rate by 10× → yield stress increases (proportional to $C\ln\dot{\varepsilon}^*$)
- Quasi-static limit: at very low rate, viscoplastic solution → rate-independent J2
- Thermal softening: at elevated temperature, yield stress decreases
- Taylor impact: cylindrical bar striking rigid wall. Compare final deformed shape (mushrooming) against experiments and published simulations (Johnson & Cook, 1983).

**Exit criterion B3:** Taylor impact test reproduces published deformed profile within 5%.

---

## Phase B4 — Advanced hyperelasticity

**Duration:** 1–2 weeks

### B4.1  Mooney-Rivlin

$$
\Psi = C_1(\bar{I}_1 - 3) + C_2(\bar{I}_2 - 3) + \frac{\kappa}{2}(J-1)^2
$$

Symbolic auto-differentiation from A3 framework handles this directly. Only the energy function definition changes.

### B4.2  Ogden

$$
\Psi = \sum_{p=1}^{N}\frac{\mu_p}{\alpha_p}(\bar{\lambda}_1^{\alpha_p} + \bar{\lambda}_2^{\alpha_p} + \bar{\lambda}_3^{\alpha_p} - 3) + \frac{\kappa}{2}(J-1)^2
$$

Requires eigenvalue decomposition of $C$. At code generation:
- Emit a `@ti.func` for 3×3 symmetric eigendecomposition (closed-form Cardano's formula or iterative Jacobi)
- Compute $\bar{\lambda}_i = J^{-1/3}\sqrt{\lambda_i^C}$
- Compute $\partial\Psi/\partial\lambda_i$ analytically, then use the eigenprojection formula:

$$
S_{IJ} = \sum_p \frac{\partial\Psi}{\partial\lambda_p}\frac{1}{\lambda_p}\,\hat{M}^{(p)}_{IJ}
$$

where $\hat{M}^{(p)}$ are the eigenprojections of $C$.

### B4.3  Holzapfel-Gasser-Ogden (anisotropic)

Add fiber direction fields $\mathbf{a}_0$, $\mathbf{b}_0$ as per-element data. The energy function from the constitutive spec (04-CONSTITUTIVE.md) is implemented directly.

Pseudo-invariant computation: $I_4 = \mathbf{a}_0 \cdot C\,\mathbf{a}_0$ requires the fiber direction rotated to the reference configuration.

### B4.4  Verification

Each model: uniaxial tension match against closed-form 1D solution + AD oracle.

**Exit criterion B4:** All hyperelastic models pass AD oracle and uniaxial verification.

---

## Phase B5 — Additional elements and integration rules

**Duration:** 1–2 weeks

### B5.1  Tet10 (10-node quadratic tetrahedron)

- Quadratic shape functions (10 nodes, 4 vertices + 6 midside)
- 4-point Gauss quadrature
- Budget check: same physics kernel as Hex8 (123 static lines), just 10 nodes in runtime loops

### B5.2  Hex20 (20-node serendipity hexahedron)

- Serendipity shape functions (20 nodes)
- 3×3×3 = 27-point Gauss quadrature
- Budget check: 123 static lines for physics, runtime loops over 20 nodes × 27 quad points

### B5.3  Reduced integration + hourglass control

**1-point Hex8:**
- Single centroid quadrature point, weight = 8.0
- 8× fewer quadrature evaluations than full integration
- Requires hourglass stabilisation

**Flanagan-Belytschko hourglass viscosity:**

$$
\mathbf{f}^{hg}_a = \alpha_{hg}\,\rho\,c_d\,V_e^{1/3}\,\sum_{\gamma=1}^{4}\dot{q}_\gamma\,\Gamma_{a\gamma}
$$

where $\Gamma_{a\gamma}$ are the hourglass base vectors (orthogonal to the linear field), $\dot{q}_\gamma$ are the hourglass velocities, $c_d$ is the dilatational wave speed, and $\alpha_{hg}$ is a user parameter (typically 0.05–0.1).

Implement as a separate `@ti.kernel` called after internal force computation.

### B5.4  Element factory

Refactor element code into a factory pattern:

```python
element = ElementFactory.create('hex8', integration='full')
element = ElementFactory.create('hex8', integration='reduced', hourglass='flanagan_belytschko')
element = ElementFactory.create('tet10')
```

Each element provides: `n_nodes`, `n_quad`, `shape_functions()`, `shape_gradients()`, `quadrature_weights()`.

**Exit criterion B5:** Patch test passes for all element types. Reduced-integration Hex8 with hourglass control passes the hourglass test (no zero-energy modes).

---

## Phase B6 — Continuum damage

**Duration:** 1–2 weeks

### B6.1  Lemaitre CDM

Implement the model from 04-CONSTITUTIVE.md:
- Damage variable $D \in [0, 1)$ evolving with plasticity
- Effective stress concept: $\tilde{\sigma} = \sigma/(1-D)$
- Energy release rate $Y$
- Damage threshold $\varepsilon_D$

Integration: coupled return mapping in effective stress space. The yield function uses $\tilde{\sigma}_{eq}$ but the damage update uses the converged plastic increment.

### B6.2  Phase-field degradation coupling (optional)

If the existing Taichi codebase already has phase-field infrastructure (deviatoric $\omega_s$, tensile $\omega_t$ degradation from `stress-integration.md`), wire the Lemaitre damage variable into the same degradation interface:

$$
\omega_s(D) = (1 - D)^2, \qquad \omega_t(D) = (1 - D)^2
$$

### B6.3  Element deletion / erosion

When $D > D_{crit}$ (e.g. 0.99), the element is "killed": its stress is set to zero and its contribution to internal forces is removed. Implement via a per-element status flag.

### B6.4  Verification

- $D = 0$ reduces to standard J2 (regression test)
- Notched bar: damage localises at notch root
- Single element: $D$ increases monotonically, stress decreases monotonically
- $D \to D_{crit}$: stress → 0

**Exit criterion B6:** Notched bar damage localisation matches qualitative expectations. Regression: D=0 case matches J2 from A7.

---

## Phase B7 — Explicit dynamics

**Duration:** 1 week

### B7.1  Central difference time integration

$$
\mathbf{v}^{n+1/2} = \mathbf{v}^{n-1/2} + \Delta t\,\mathbf{M}^{-1}_L\,(\mathbf{f}^{ext,n} - \mathbf{f}^{int,n})
$$
$$
\mathbf{u}^{n+1} = \mathbf{u}^n + \Delta t\,\mathbf{v}^{n+1/2}
$$

where $\mathbf{M}_L$ is the lumped (diagonal) mass matrix.

No linear solver needed — this is a purely element-local computation.

### B7.2  Lumped mass matrix

Row-sum lumping: $M^L_{aa} = \sum_b M_{ab}$ where $M_{ab} = \int \rho\,N_a\,N_b\,dV$.

For uniform density: $M^L_{aa} = \rho\,V_e / n_{nodes}$ (equal distribution).

### B7.3  Critical time step

$$
\Delta t_{crit} = \min_e \frac{h_e}{c_d}
$$

where $h_e$ is a characteristic element length and $c_d = \sqrt{(\lambda + 2\mu)/\rho}$ is the dilatational wave speed.

Implement a `@ti.kernel` that computes $\Delta t_{crit}$ as a reduction over all elements. Apply a safety factor (0.8).

### B7.4  Stable time step with plasticity

During plastic deformation, the effective tangent stiffness decreases, so $c_d$ decreases and $\Delta t_{crit}$ increases. However, for safety, compute $c_d$ from the elastic moduli (conservative bound).

### B7.5  Verification

- Free vibration of an elastic bar: compare period against analytical $T = 2L/c_d$
- Impact: block on rigid surface, compare rebound velocity
- Cross-check: quasi-static loading with explicit dynamics (long time, damping) vs implicit Newton — same final state

**Exit criterion B7:** Free vibration period matches analytical within 1%. Explicit and implicit give same quasi-static result.

---

## Phase B8 — MFEM and MOOSE backend printers

**Duration:** 2–3 weeks

### B8.1  MFEM printer

Generate C++ source files:
- `CompMechIntegrator.hpp/cpp` — custom `NonlinearFormIntegrator`
- `CompMechMaterial.hpp/cpp` — material model evaluation
- `main.cpp` — driver with mesh loading, Newton solve, output
- `CMakeLists.txt` — build system linking MFEM

The printer translates:
- Tier 1 contractions → MFEM `DenseMatrix` multiply
- Tier 2 contractions → inline loops with MFEM element access
- Voigt conventions → MFEM's internal ordering (may require permutation)

### B8.2  MOOSE printer

Generate:
- `CompMechStress.h/C` — material class deriving from `ComputeStressBase`
- `CompMechAction.h/C` — action for adding kernels and materials
- `.i` input file — minimal MOOSE input

### B8.3  Cross-backend verification

Run Cook's membrane with:
1. Taichi (generated)
2. MFEM (generated)
3. MOOSE (generated)

Compare: displacement field max difference < 1e-8.

**Exit criterion B8:** Same problem, three backends, matching results.

---

## Phase B9 — Full V&V suite

**Duration:** 1–2 weeks

### B9.1  MMS convergence study

For each element type × each constitutive model:
- Manufacture a smooth solution $u^*(x) = \sin(\pi x)\cos(\pi y)\sin(\pi z)$
- Compute manufactured body force
- Solve on 4+ mesh refinements
- Verify convergence rate: $L^2$ rate ≥ $p+1$, $H^1$ rate ≥ $p$

### B9.2  Physical benchmark suite

| Problem | Formulation | Material | Element | Reference |
|---------|-------------|----------|---------|-----------|
| Cantilever (elastic) | TL, UL | Neo-Hookean | Hex8, Tet10, Hex20 | EB theory |
| Cook's membrane | TL, UL | J2 | Hex8, Tet10 | de Souza Neto |
| Thick cylinder | TL | Isotropic elastic | Hex8 | Lamé solution |
| Plate with hole | TL | Isotropic elastic | Hex8, Hex20 | Kirsch $K_t = 3$ |
| Necking bar | TL | J2 + neo-Hookean | Hex8 | Simo & Hughes |
| Taylor impact | UL | JC viscoplastic | Hex8 (reduced) | Johnson & Cook |
| Notched bar | TL | Lemaitre damage | Hex8 | Literature |
| Fiber-reinforced strip | TL | HGO | Hex8 | Holzapfel et al. |

### B9.3  Performance benchmarks

- Wall-clock time vs DOF count for each element type
- GPU utilisation (Taichi profiler)
- Newton iteration count vs load step size
- CG iteration count vs preconditioner

### B9.4  Regression test integration

All benchmarks run nightly in CI. Any result outside acceptance bounds triggers a failure.

**Exit criterion B9:** All benchmarks pass. Convergence rates match theory. Cross-backend results agree.

---

## Total estimated duration: 12–18 weeks (from MVP completion)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| B1 Updated Lagrangian | 2 weeks | 2 weeks |
| B2 Convected coordinates | 2–3 weeks | 5 weeks |
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
Plan A (MVP) ──→ B1 (UL) ──→ B2 (convected) ──→ B9 (V&V)
                  │                                 ↑
                  ├──→ B3 (viscoplasticity) ────────┤
                  │                                 │
                  ├──→ B4 (hyperelastic models) ────┤
                  │                                 │
                  ├──→ B5 (elements) ───────────────┤
                  │                                 │
                  ├──→ B6 (damage) ─────────────────┤
                  │                                 │
                  ├──→ B7 (explicit dynamics) ──────┤
                  │                                 │
                  └──→ B8 (MFEM/MOOSE) ────────────┘
```

B3–B7 can proceed in parallel once B1 is complete. B2 (convected coordinates) requires B1 but is independent of B3–B7. B8 (backend printers) can start after any constitutive model is working. B9 (V&V) is the final integration and requires all other phases.
