# 08 — Verification and Validation

---

## 1  Strategy

Verification follows a layered approach matching the system architecture. Each layer is tested independently before integration tests exercise the full pipeline.

| Level | What is tested | Method |
|-------|---------------|--------|
| **Unit** | Individual functions (Voigt map, B-matrix, shape functions) | Pytest assertions against known values |
| **Symbolic** | Constitutive derivations (Ψ → S → ℂ) | AD oracle comparison |
| **Element** | Single-element response | Patch test, rigid body motion |
| **Solver** | Multi-element boundary value problem | Analytical solutions, convergence study |
| **Cross-backend** | Same problem on Taichi, MFEM, MOOSE | Solution comparison within tolerance |

---

## 2  Unit tests

### 2.1  Voigt conversions

- Round-trip: `tensor → voigt → tensor` recovers original (exact equality)
- Symmetry: `voigt_to_tensor` produces symmetric matrix
- Known values: identity tensor → `[1, 1, 1, 0, 0, 0]`

### 2.2  Mandel conversions

- Round-trip: `voigt → mandel → voigt` recovers original
- Rotation invariance: rotate a tangent by identity → unchanged
- Known rotation: 90° rotation of uniaxial tangent

### 2.3  B-matrix (CST)

- Constant strain field $u_x = ax + by$, $u_y = cx + dy$: B-matrix times nodal displacements must recover $(a, d, b+c)$ exactly.
- Element with known coordinates: verify B against hand calculation.

### 2.4  Shape functions

- Partition of unity: $\sum_a N_a(\xi) = 1$ at all quadrature points
- Kronecker delta: $N_a(\xi_b) = \delta_{ab}$ at nodes
- Gradient consistency: numerical gradient matches analytical

---

## 3  Symbolic verification (AD oracle)

### 3.1  Purpose

For every energy-based constitutive model, the symbolic engine derives $S_{IJ} = 2\partial\Psi/\partial C_{IJ}$ and $\mathbb{C}_{IJKL} = 2\partial S_{IJ}/\partial C_{KL}$ using SymPy's symbolic differentiation. These expressions can be complex and error-prone after simplification. The AD oracle provides an independent numerical check.

### 3.2  Method

1. Implement $\Psi(\mathbf{C})$ as a numerical function in PyTorch or Taichi autodiff.
2. At $N$ random deformation states (random $\mathbf{F}$ with $J > 0$, hence random $\mathbf{C} = \mathbf{F}^T\mathbf{F}$):
   a. Evaluate the symbolic $S_{IJ}$ expression (lambdified via SymPy).
   b. Evaluate $S_{IJ}^{AD} = 2\partial\Psi/\partial C_{IJ}$ via AD.
   c. Assert $|S_{IJ} - S_{IJ}^{AD}| < \epsilon$ (relative tolerance $10^{-10}$).
3. Repeat for the tangent $\mathbb{C}_{IJKL}$ (second derivative of $\Psi$ or first derivative of $S$).

### 3.3  Random deformation state generation

A random deformation gradient with controlled condition number:

```python
def random_F(dim=3, max_stretch=1.5, rng=None):
    """Generate random F with J > 0 and bounded condition number."""
    rng = rng or np.random.default_rng(42)
    # Random rotation
    Q, _ = np.linalg.qr(rng.standard_normal((dim, dim)))
    if np.linalg.det(Q) < 0:
        Q[:, 0] *= -1
    # Random stretches in (1/max_stretch, max_stretch)
    stretches = np.exp(rng.uniform(-np.log(max_stretch), np.log(max_stretch), dim))
    U = np.diag(stretches)
    return Q @ U  # F = R U (polar decomposition)
```

### 3.4  Required tests per model

| Model | Derivatives to verify |
|-------|----------------------|
| NeoHookean | $\partial\Psi/\partial C$, $\partial^2\Psi/\partial C^2$ |
| MooneyRivlin | $\partial\Psi/\partial C$, $\partial^2\Psi/\partial C^2$ |
| Ogden | $\partial\Psi/\partial\lambda_i$, tangent via numerical perturbation |
| IsotropicElastic | $C_{ijkl}$ symmetries: major ($C_{ijkl} = C_{klij}$), minor ($C_{ijkl} = C_{jikl}$) |

---

## 4  Element-level tests

### 4.1  Patch test

**Definition:** A mesh of arbitrary element shapes is loaded with a displacement field that produces a uniform strain. Every element must recover the exact stress (to machine precision).

**Implementation:**

1. Create an irregular mesh (non-rectangular quadrilaterals, non-equilateral triangles).
2. Prescribe nodal displacements corresponding to a known constant strain: e.g. $\varepsilon_{xx} = 10^{-3}$, all others zero.
3. Compute stress at every quadrature point.
4. Assert: $\sigma_{xx} = C_{11} \times 10^{-3}$, $\sigma_{yy} = C_{12} \times 10^{-3}$, etc. Tolerance: $10^{-12}$ relative.

If any element fails the patch test, the B-matrix or element formulation is wrong. No further testing is meaningful until this passes.

### 4.2  Rigid body motion

**Definition:** Apply a rigid translation and/or rotation to all nodes. The internal force vector must be zero (to machine precision).

- Translation: $u_i = c_i$ (constant) → $\varepsilon = 0$ → $\sigma = 0$ → $f_{int} = 0$
- Rotation (small): $u_i = \omega_{ij} x_j$ (antisymmetric $\omega$) → $\varepsilon = 0$ for linear elements

For nonlinear formulations (TL/UL), rigid rotation should produce zero stress via the objectivity of the constitutive model.

### 4.3  Single-element uniaxial

One element, constrained on one face, loaded on the opposite face.

- Linear elastic: compare stress against $\sigma = E\varepsilon$ (1D) or plane stress equivalent.
- Neo-Hookean: compare PK2 stress against closed-form uniaxial solution.

---

## 5  Solver-level benchmarks

### 5.1  Cantilever beam (linear elastic)

**Geometry:** $L \times H$ rectangle (2D) or $L \times H \times W$ box (3D).  
**BCs:** fixed left face, distributed load on right face.  
**Reference:** Euler-Bernoulli beam theory $\delta_{tip} = PL^3/(3EI)$.  
**Expected:** FEM converges to EB solution from below (CST is stiff). Convergence rate $\approx 1.0$ for linear elements, $\approx 2.0$ for quadratic.

**Convergence study protocol:**

1. Solve on meshes with $n = [4, 8, 16, 32, 64]$ elements per side.
2. Record tip displacement.
3. Compute convergence rate: $p = \log(e_1/e_2) / \log(h_1/h_2)$.
4. Assert $p$ is within $[0.8, 1.2]$ for linear elements (allowing for mesh irregularity effects).

### 5.2  Cook's membrane

**Geometry:** tapered quadrilateral domain (Cook's membrane shape).  
**BCs:** fixed left edge, distributed shear on right edge.  
**Reference:** established numerical benchmarks from literature (e.g., de Souza Neto et al.).  
**Purpose:** tests shear-dominated response, sensitivity to mesh distortion, incompressibility locking.

### 5.3  Thick cylinder under pressure

**Geometry:** quarter-cylinder (symmetry BCs).  
**BCs:** internal pressure $p_i$, traction-free outer surface.  
**Reference:** Lamé solution.

$$
\sigma_{rr}(r) = \frac{p_i a^2}{b^2 - a^2}\left(1 - \frac{b^2}{r^2}\right), \quad
\sigma_{\theta\theta}(r) = \frac{p_i a^2}{b^2 - a^2}\left(1 + \frac{b^2}{r^2}\right)
$$

Tests: correct stress distribution in polar coordinates, convergence.

### 5.4  Plate with circular hole

**Geometry:** quarter-plate with hole (symmetry BCs).  
**BCs:** uniaxial tension on outer edges.  
**Reference:** Kirsch solution. Stress concentration factor $K_t = 3$.

### 5.5  Necking bar (nonlinear, plasticity)

**Geometry:** cylindrical bar with geometric imperfection at centre.  
**BCs:** uniaxial displacement-controlled tension.  
**Purpose:** tests J2 plasticity with large deformation, necking localisation.  
**Reference:** load-displacement curve from literature (Simo & Hughes, 1998).

### 5.6  Notched bar (damage)

**Geometry:** bar with circumferential notch.  
**BCs:** uniaxial tension.  
**Purpose:** tests Lemaitre damage model, damage localisation at notch root.  
**Reference:** damage evolution at notch root from literature.

---

## 6  Method of Manufactured Solutions (MMS)

### 6.1  Purpose

MMS provides a systematic way to verify the discretisation order of accuracy for any PDE without needing an analytical solution to the BVP.

### 6.2  Procedure

1. Choose a smooth displacement field $\mathbf{u}^*(x)$ (e.g. polynomial or trigonometric).
2. Compute the corresponding strain $\boldsymbol{\varepsilon}^* = \mathrm{sym}(\nabla\mathbf{u}^*)$.
3. Compute stress $\boldsymbol{\sigma}^* = \mathbb{C}:\boldsymbol{\varepsilon}^*$.
4. Compute body force $\mathbf{b}^* = -\nabla\cdot\boldsymbol{\sigma}^*$ (this is the manufactured source term).
5. Solve the FEM problem with body force $\mathbf{b}^*$ and Dirichlet BCs from $\mathbf{u}^*$.
6. Compare FEM solution against $\mathbf{u}^*$ in $L^2$ and $H^1$ norms.
7. Refine mesh and check convergence rate.

**Expected rates:**

| Element | $L^2$ error rate | $H^1$ error rate |
|---------|------------------|------------------|
| Linear (Tri3, Tet4, Q4, Hex8) | 2 | 1 |
| Quadratic (Tri6, Tet10, Q8, Hex20) | 3 | 2 |

### 6.3  Manufactured solutions for nonlinear problems

For hyperelastic problems, the procedure is analogous but uses the nonlinear constitutive law. The manufactured body force becomes:

$\mathbf{b}^*_0 = -\nabla_0 \cdot \mathbf{P}(\mathbf{u}^*)$

where $\mathbf{P}$ is computed from the constitutive model.

---

## 7  Cross-backend validation

When the same problem is solved by Taichi and MFEM (or MOOSE) backends:

1. Run identical mesh, material, BCs.
2. Compare displacement fields: $\|\mathbf{u}_{Taichi} - \mathbf{u}_{MFEM}\|_\infty < 10^{-8}$.
3. Compare stress fields at corresponding quadrature points.
4. Compare convergence iteration counts (should match for same solver settings).

Differences beyond tolerance indicate a bug in one of the printers.

---

## 8  Regression test suite

Every merged change runs the following minimum suite:

| Test | Time budget | Threshold |
|------|-------------|-----------|
| Unit tests (Voigt, B-matrix, shape funcs) | < 5 s | All pass |
| AD oracle (all hyperelastic models, N=100 states) | < 30 s | Relative error < 1e-10 |
| Patch test (all supported elements) | < 10 s | Relative error < 1e-12 |
| Rigid body motion (all elements) | < 5 s | Force norm < 1e-12 |
| Cantilever convergence (linear elastic, CST) | < 30 s | Rate ∈ [0.8, 1.2] |
| Cantilever convergence (linear elastic, Q4) | < 30 s | Rate ∈ [1.8, 2.2] |

Full benchmark suite (Cook's membrane, cylinder, hole, necking, damage) runs nightly.
