# 07 — Conventions (Single Source of Truth)

If any other document, code comment, or generated output disagrees with this file, **this file wins**.

---

## 1  Index conventions

### 1.1  Spatial indices

Lowercase Latin: `i, j, k, l, m, n`

Range: `1..d` where `d` is the spatial dimension (2 or 3)

Used for: Cauchy stress $\sigma_{ij}$, Euler-Almansi strain $e_{ij}$, spatial velocity gradient $L_{ij}$, left Cauchy-Green $b_{ij}$

### 1.2  Material indices

Uppercase Latin: `I, J, K, L, M, N`

Range: `1..D` where `D` is the material dimension (usually $D = d$)

Used for: PK2 stress $S_{IJ}$, Green-Lagrange strain $E_{IJ}$, right Cauchy-Green $C_{IJ}$, material tangent $\mathbb{C}_{IJKL}$

### 1.3  Two-point tensors

Mixed indices: `F_{iI}` (spatial row, material column)

The deformation gradient is the prototypical two-point tensor. PK1 stress $P_{iI}$ is also two-point.

### 1.4  Summation convention

Einstein summation applies: repeated indices in the same term are summed. Free indices must match on both sides of an equation.

Contracting a spatial index with a material index is **only valid** through a two-point tensor. For example, $P_{iI} = F_{iJ} S_{JI}$ contracts material index $J$ — this is valid. Writing $\sigma_{iI}$ with one spatial and one material index is **undefined** unless it is explicitly a two-point tensor.

---

## 2  Voigt conventions

### 2.1  Ordering

**3D (6 components):**

| Voigt idx | Tensor pair | Label |
|-----------|-------------|-------|
| 0 | (0,0) | xx |
| 1 | (1,1) | yy |
| 2 | (2,2) | zz |
| 3 | (0,1) = (1,0) | xy |
| 4 | (0,2) = (2,0) | xz |
| 5 | (1,2) = (2,1) | yz |

**2D (3 components)** *(Plan B — not used in MVP):*

| Voigt idx | Tensor pair | Label |
|-----------|-------------|-------|
| 0 | (0,0) | xx |
| 1 | (1,1) | yy |
| 2 | (0,1) = (1,0) | xy |

### 2.2  Shear scaling

**Tensorial Voigt (this project):** shears are **unscaled**.

$\mathbf{v} = [\sigma_{xx}, \sigma_{yy}, \sigma_{zz}, \sigma_{xy}, \sigma_{xz}, \sigma_{yz}]$

Not $2\sigma_{xy}$. Not $\gamma_{xy} = 2\varepsilon_{xy}$.

For strain: $\mathbf{e} = [\varepsilon_{xx}, \varepsilon_{yy}, \varepsilon_{zz}, \varepsilon_{xy}, \varepsilon_{xz}, \varepsilon_{yz}]$

**Consequence:** the stress-strain relation in Voigt form is $\sigma_I = C_{IJ} \varepsilon_J$ with the **same** $C_{IJ}$ as the 4th-order tensor contraction. No factors of 2 or 4 appear. This is the advantage of tensorial Voigt.

**Warning:** many textbooks and codes use **engineering Voigt** where $\gamma_{xy} = 2\varepsilon_{xy}$. In that convention, shear entries of $C$ are scaled by factors of 2 and 4. Converting between conventions requires careful scaling. The MFEM and MOOSE printers must handle this at the interface.

### 2.3  Voigt map arrays (for code generation)

```python
# 3D
VOIGT_MAP_3D = [(0,0), (1,1), (2,2), (0,1), (0,2), (1,2)]
VOIGT_INV_3D = {(0,0):0, (1,1):1, (2,2):2,
                (0,1):3, (1,0):3, (0,2):4, (2,0):4, (1,2):5, (2,1):5}

# 2D
VOIGT_MAP_2D = [(0,0), (1,1), (0,1)]
VOIGT_INV_2D = {(0,0):0, (1,1):1, (0,1):2, (1,0):2}
```

---

## 3  Mandel conventions

### 3.1  Purpose

Mandel representation makes 6×6 tangent rotation a proper orthogonal similarity transform. Without Mandel scaling, rotating a Voigt tangent by a naive 3×3 rotation matrix gives **wrong results**.

### 3.2  Scaling

$P = \mathrm{diag}(1, 1, 1, \sqrt{2}, \sqrt{2}, \sqrt{2})$

$\mathbf{C}^{Mandel} = P\,\mathbf{C}^{Voigt}\,P^{-1}$

$\mathbf{C}^{Voigt} = P^{-1}\,\mathbf{C}^{Mandel}\,P$

### 3.3  Tangent rotation in Mandel space

Given a rotation matrix $\mathbf{R} \in SO(3)$, the 6×6 Mandel rotation matrix $\mathbf{T}(\mathbf{R})$ is constructed as:

$T_{IJ} = \sum_{(i,j) \in \text{pair}(I)} \sum_{(k,l) \in \text{pair}(J)} s_I\,s_J\,R_{ik}\,R_{jl}$

where $s_I = 1$ for normal components and $s_I = 1/\sqrt{2}$ for shear components. The pairs are the Voigt map entries.

The rotated Mandel tangent is:

$\mathbf{C}'_M = \mathbf{T}\,\mathbf{C}_M\,\mathbf{T}^T$

Convert back to Voigt: $\mathbf{C}'_V = P^{-1}\,\mathbf{C}'_M\,P$

---

## 4  Sign conventions

### 4.1  Stress

**Tension is positive.** A uniaxial tensile test at stress $\sigma_0$ gives $\sigma_{xx} = +\sigma_0$.

### 4.2  Mean stress and pressure

$m = \frac{1}{3}\mathrm{tr}(\boldsymbol{\sigma})$ — **tension positive**

$p = -m$ — **compression positive**

### 4.3  Hydrostatic stress under EOS

When an equation of state provides pressure: $p_{EOS} > 0$ means **compression**, $p_{EOS} < 0$ means **tension**.

### 4.4  Strain

**Extension is positive.** $\varepsilon_{xx} > 0$ means the material stretched in the $x$ direction.

### 4.5  Normal vectors

Outward-pointing normal on the boundary. Traction: $\mathbf{t} = \boldsymbol{\sigma}\cdot\mathbf{n}$ on $\Gamma_N$.

---

## 5  Stress measures and push-forward / pull-back

| Measure | Symbol | Configuration | Definition |
|---------|--------|--------------|------------|
| Cauchy stress | $\sigma_{ij}$ | Spatial | Force per deformed area |
| Kirchhoff stress | $\tau_{ij} = J\sigma_{ij}$ | Spatial | Weighted Cauchy |
| 1st Piola-Kirchhoff | $P_{iI}$ | Two-point | $P = J\sigma F^{-T}$ or $P = FS$ |
| 2nd Piola-Kirchhoff | $S_{IJ}$ | Material | $S = JF^{-1}\sigma F^{-T}$ or $S = F^{-1}P$ |

**Push-forward / pull-back:**

$\sigma = \frac{1}{J}F\,S\,F^T$ (PK2 → Cauchy)

$S = J\,F^{-1}\sigma\,F^{-T}$ (Cauchy → PK2)

$P = F\,S$ (PK2 → PK1)

---

## 6  Numerical tolerances

| Purpose | Value | Used in |
|---------|-------|---------|
| Zero-area/volume element | $A < 10^{-30}$ | B-matrix computation |
| Jacobian positivity | $J > 10^{-15}$ | Element inversion check |
| Von Mises near zero | $\sigma_{eq} < 10^{-12}\,\sigma_y$ | Flow direction computation |
| CG convergence | $\|\mathbf{r}\| < 10^{-10}\|\mathbf{r}_0\|$ | Linear solver |
| Newton convergence | $\|\mathbf{R}\| < 10^{-8}\|\mathbf{R}_0\|$ | Nonlinear solver |
| Damage clamping | $D \in [0, 1 - 10^{-6}]$ | Lemaitre damage |
| Plastic multiplier | $\Delta\lambda \ge -10^{-15}$ | Return mapping (allow tiny negative from Newton) |

---

## 7  Coordinate system and element orientation

### 7.1  2D *(Plan B — not used in MVP)*

Right-hand rule. $(x, y)$ are the in-plane coordinates. For plane stress/strain, the out-of-plane direction is $z$.

Triangle nodes are ordered counter-clockwise (positive area). If clockwise, the element has negative area and the B-matrix sign is wrong.

### 7.2  3D *(MVP: Hex8 only)*

Right-hand rule. Tet nodes follow the convention: first three nodes define a face with outward normal pointing away from the fourth node.

Hex nodes follow the standard brick ordering (see MFEM/VTK conventions).

---

## 8  Units

The DSL is **unit-agnostic**. The user is responsible for consistent units. Common systems:

| System | Length | Force | Stress | Mass | Time |
|--------|--------|-------|--------|------|------|
| SI | m | N | Pa | kg | s |
| mm-N-MPa | mm | N | MPa | tonne (10³ kg) | s |
| mm-kN-GPa | mm | kN | GPa | tonne | s |

The generated code does not insert unit conversions.

---

## 9  JIT compilation budget (hard rules)

1) No `@ti.func` may produce more than **512 unrolled lines** from `ti.static` loops.
2) No `@ti.kernel` may exceed **2000 total unrolled lines** across all its `@ti.func` calls.
3) The absolute ceiling of **5000 unrolled lines** is never exceeded under any circumstances.
4) All **physics indices** (spatial, material, Voigt — range ≤ 6) are `ti.static`.
5) All **mesh indices** (nodes, quad points, elements) are runtime loops, never unrolled.
6) The JIT budget counter must be run on every contraction before code emission. If budget is exceeded, the emitter must restructure (split into sub-functions or fall back to Tier 3).

---

## 10  Floating-point precision

All generated code uses **`float64`** (`ti.f64` in Taichi, `np.float64` in NumPy). Taichi kernels must set `default_fp=ti.f64` in `ti.init()`.

No single-precision (`f32`) code paths exist in the pipeline. If a future backend requires mixed precision, it must be handled at the printer level while keeping all symbolic and IR layers in `float64`.

---

## 11  J2 radial-return: algo2code substitution

**Origin.** The J2 radial-return algorithm with power-law isotropic
hardening lives in algpseudocode form at
[`dev/algorithms/radial_return_j2.tex`](../algorithms/radial_return_j2.tex)
and is mirrored into the algo2code library at
`packages/algo2code/src/algo2code/library/radial_return_j2.py`. The
post_recovery_plan Phase 5 substitution makes
`mechdsl.lib.plasticity.radial_return` the canonical consumer-side
entry point — callers should import the dispatcher from
`mechdsl.lib.plasticity` rather than the imported reference at
`mechdsl.symbolic.models.j2_power_law.radial_return` directly.

**Default path.** The dispatcher routes to the algo2code-generated
implementation by default. Today this body is a verbatim Python
translation of the algpseudocode source (the algo2code parser bugs
documented in the source-file header defer direct emission); a future
parser fix replaces the body with an `algo2code.transpile` call without
altering the dispatcher's contract.

**Feature-flag fallback.** Setting the environment variable
`MECHDSL_USE_IMPORTED_RR=1` (or any of `true` / `yes` / `on`,
case-insensitive) reverts the dispatcher to the imported
`mechdsl.symbolic.models.j2_power_law.radial_return` for incident
response. The switch happens via env var alone — no recompilation
needed because the imported path is plain NumPy. The flag re-evaluates
on every dispatcher call, so toggling within a single Python session
swaps the active path immediately.

**Parity contract.** Imported and algo2code paths produce identical
stress, internal-variable, and tangent updates within `1e-12` of each
other for elastic, elastoplastic, and unloading load steps. The parity
is asserted by
[`packages/mechdsl-core/tests/test_j2_radial_return_parity.py`](../../packages/mechdsl-core/tests/test_j2_radial_return_parity.py)
(post_recovery_plan P5-4). Tolerance is derived from the imported-path
Newton convergence baseline, not absolute zero, so a future divergent
algo2code emission still has a clear ceiling.

**Stability soak.** After the substitution lands, the imported path
is retained as a fallback for incident response only. After a stability
soak — defined externally — a future plan may delete the imported
reference entirely.
