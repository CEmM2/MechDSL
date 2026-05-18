# 04 — Constitutive Model Library

---

## 1  Model hierarchy

```
ConstitutiveModel (abstract)
├── ElasticModel
│   ├── IsotropicElastic          (E, ν)
│   └── OrthotropicElastic        (E_i, G_ij, ν_ij)
├── HyperelasticModel
│   ├── NeoHookean                (μ, κ)
│   ├── MooneyRivlin              (C1, C2, κ)
│   ├── Ogden                     (μ_i, α_i, κ)
│   └── HolzapfelGasserOgden      (μ, k1, k2, κ, κ_f)
├── PlasticModel
│   ├── J2Plasticity              (σ_y, H_iso, H_kin)
│   ├── J2JohnsonCook             (A, B, n, C, m, ε̇_0, T_melt, T_ref)
│   └── J2VoceHardening           (σ_y, Q, b)
└── DamageModel
    ├── LemaitreDamage            (S, s, ε_D)
    └── GursonTvergaardNeedleman  (q1, q2, q3, f_0, f_c, f_f)
```

Each model implements the `ConstitutiveModel` interface from `03-SYMBOLIC-ENGINE.md`. Models can be composed: `J2Plasticity` wraps an `ElasticModel` for its elastic response.

---

## 2  Linear elastic models

### 2.1  Isotropic

**Parameters:** `E` (Young's modulus), `ν` (Poisson's ratio)

**Derived:** `μ = E/(2(1+ν))` (shear modulus), `λ = Eν/((1+ν)(1-2ν))` (Lamé's first parameter), `κ = E/(3(1-2ν))` (bulk modulus)

**Constitutive tensor (3D):**

$$
C_{ijkl} = \lambda\,\delta_{ij}\delta_{kl} + \mu\left(\delta_{ik}\delta_{jl} + \delta_{il}\delta_{jk}\right)
$$

**Voigt matrix (3D):**

$$
\mathbf{C} = \begin{bmatrix}
\lambda+2\mu & \lambda & \lambda & 0 & 0 & 0 \\
\lambda & \lambda+2\mu & \lambda & 0 & 0 & 0 \\
\lambda & \lambda & \lambda+2\mu & 0 & 0 & 0 \\
0 & 0 & 0 & \mu & 0 & 0 \\
0 & 0 & 0 & 0 & \mu & 0 \\
0 & 0 & 0 & 0 & 0 & \mu
\end{bmatrix}
$$

**Plane stress (2D Voigt):**

$$
\mathbf{C}_{ps} = \frac{E}{1-\nu^2}\begin{bmatrix}
1 & \nu & 0 \\
\nu & 1 & 0 \\
0 & 0 & \frac{1-\nu}{2}
\end{bmatrix}
$$

**Plane strain (2D Voigt):**

$$
\mathbf{C}_{pe} = \frac{E}{(1+\nu)(1-2\nu)}\begin{bmatrix}
1-\nu & \nu & 0 \\
\nu & 1-\nu & 0 \\
0 & 0 & \frac{1-2\nu}{2}
\end{bmatrix}
$$

### 2.2  Orthotropic

Nine independent parameters. Voigt matrix has the standard form with compliance matrix inverted. Omitted here for brevity — the implementation follows Reddy (2003).

---

## 3  Hyperelastic models

All hyperelastic models define a strain energy function $\Psi$ from which stress and tangent are derived symbolically via `sympy.diff`.

### 3.1  Neo-Hookean (compressible)

**Parameters:** `μ`, `κ`

**Energy:**

$$
\Psi = \frac{\mu}{2}\left(\bar{I}_1 - 3\right) + \frac{\kappa}{2}\left(J - 1\right)^2
$$

where $\bar{I}_1 = J^{-2/3}\,\mathrm{tr}(\mathbf{C})$.

**PK2 stress (auto-derived):**

$$
S_{IJ} = 2\frac{\partial\Psi}{\partial C_{IJ}} = \mu J^{-2/3}\left(\delta_{IJ} - \frac{1}{3}I_1 C^{-1}_{IJ}\right) + \kappa(J-1)J\,C^{-1}_{IJ}
$$

**Material tangent (auto-derived):**

$$
\mathbb{C}_{IJKL} = 2\frac{\partial S_{IJ}}{\partial C_{KL}}
$$

Computed by SymPy symbolic differentiation of the PK2 expression with respect to `C_KL`.

### 3.2  Mooney-Rivlin

**Parameters:** `C1`, `C2`, `κ`

**Energy:**

$$
\Psi = C_1\left(\bar{I}_1 - 3\right) + C_2\left(\bar{I}_2 - 3\right) + \frac{\kappa}{2}\left(J-1\right)^2
$$

### 3.3  Ogden

**Parameters:** `N` (number of terms), `μ_p`, `α_p` for `p = 1..N`, `κ`

**Energy:**

$$
\Psi = \sum_{p=1}^{N} \frac{\mu_p}{\alpha_p}\left(\bar{\lambda}_1^{\alpha_p} + \bar{\lambda}_2^{\alpha_p} + \bar{\lambda}_3^{\alpha_p} - 3\right) + \frac{\kappa}{2}(J-1)^2
$$

where $\bar{\lambda}_i = J^{-1/3}\lambda_i$ and $\lambda_i$ are the principal stretches (eigenvalues of $\mathbf{U}$).

Note: Ogden requires principal-stretch representation. The symbolic engine operates on eigenvalues of `C`, which may produce complex expressions. For code generation, numerical eigenvalue decomposition is used.

### 3.4  Holzapfel-Gasser-Ogden (HGO)

**Parameters:** `μ`, `k1`, `k2`, `κ` (bulk), `κ_f` (fiber dispersion)

**Energy (two fiber families):**

$$
\Psi = \frac{\mu}{2}(\bar{I}_1 - 3) + \sum_{a=4,6}\frac{k_1}{2k_2}\left[\exp\left(k_2\left\langle E_a\right\rangle^2\right) - 1\right] + \frac{\kappa}{2}(J-1)^2
$$

where $E_a = \kappa_f(\bar{I}_1 - 3) + (1-3\kappa_f)(\bar{I}_a - 1)$ and $\bar{I}_a = J^{-2/3}(\mathbf{a}_0 \cdot \mathbf{C}\,\mathbf{a}_0)$ are the pseudo-invariants of the fiber directions $\mathbf{a}_0$.

The Macaulay bracket $\langle\cdot\rangle = \max(0, \cdot)$ ensures fibers only resist tension.

---

## 4  Plasticity models

### 4.1  J2 plasticity (rate-independent, isotropic + kinematic hardening)

**Elastic response:** isotropic elasticity (parameterised by `E`, `ν` or `μ`, `κ`)

**Yield function:**

$$
f(\boldsymbol{\sigma}, \boldsymbol{\alpha}, \bar{\varepsilon}_p) = \sigma_{eq}(\boldsymbol{\sigma} - \boldsymbol{\alpha}) - \sigma_y(\bar{\varepsilon}_p) \le 0
$$

where $\sigma_{eq}(\mathbf{s}) = \sqrt{(3/2)\,\mathbf{s}:\mathbf{s}}$, $\boldsymbol{\alpha}$ is the backstress tensor.

**Hardening:**

- Isotropic: $\sigma_y(\bar{\varepsilon}_p) = \sigma_{y0} + H_{iso}\,\bar{\varepsilon}_p$
- Kinematic (linear): $\dot{\boldsymbol{\alpha}} = \frac{2}{3}H_{kin}\,\dot{\boldsymbol{\varepsilon}}_p$

**Return mapping (radial return — closest-point projection):**

1. Elastic predictor: $\boldsymbol{\sigma}^{tr} = \boldsymbol{\sigma}^n + \mathbb{C}_e : \Delta\boldsymbol{\varepsilon}$
2. Deviatoric trial: $\mathbf{s}^{tr} = \mathrm{dev}(\boldsymbol{\sigma}^{tr})$, relative: $\boldsymbol{\xi}^{tr} = \mathbf{s}^{tr} - \boldsymbol{\alpha}^n$
3. Trial yield: $f^{tr} = \sqrt{(3/2)\,\boldsymbol{\xi}^{tr}:\boldsymbol{\xi}^{tr}} - \sigma_y(\bar{\varepsilon}_p^n)$
4. If $f^{tr} \le 0$: elastic step.
5. Else: solve $\Delta\lambda$ from $\sigma_{eq}^{tr} - 3\mu\Delta\lambda - \sigma_y(\bar{\varepsilon}_p^n + \Delta\lambda) = 0$
6. Update: $\mathbf{n} = \boldsymbol{\xi}^{tr}/\|\boldsymbol{\xi}^{tr}\|$, $\mathbf{s}^{n+1} = \mathbf{s}^{tr} - 2\mu\Delta\lambda\,\mathbf{n}$
7. Backstress: $\boldsymbol{\alpha}^{n+1} = \boldsymbol{\alpha}^n + (2/3)H_{kin}\Delta\lambda\,\mathbf{n}$
8. PEEQ: $\bar{\varepsilon}_p^{n+1} = \bar{\varepsilon}_p^n + \Delta\lambda$

**Algorithmic (consistent) tangent:**

$$
\mathbb{C}^{alg} = \kappa\,\boldsymbol{\delta}\otimes\boldsymbol{\delta}
  + 2\mu\theta\,\mathbb{I}^{dev}
  - 2\mu\left(\theta - \bar{\theta}\right)\mathbf{n}\otimes\mathbf{n}
$$

where $\theta = 1 - 3\mu\Delta\lambda/\sigma_{eq}^{tr}$, $\bar{\theta} = 1/(1 + (3\mu + H_{kin})/(3\mu + H_{iso}'))$, and $\mathbb{I}^{dev}_{ijkl} = (1/2)(\delta_{ik}\delta_{jl} + \delta_{il}\delta_{jk}) - (1/3)\delta_{ij}\delta_{kl}$.

### 4.2  Johnson-Cook

**Parameters:** `A`, `B`, `n`, `C`, `m`, `ε̇_0`, `T_melt`, `T_ref`

**Yield stress:**

$$
\sigma_y = \left(A + B\bar{\varepsilon}_p^n\right)\left(1 + C\ln\frac{\dot{\bar{\varepsilon}}_p}{\dot{\varepsilon}_0}\right)\left(1 - T^{*m}\right)
$$

where $T^* = (T - T_{ref})/(T_{melt} - T_{ref})$.

Return mapping uses Newton iteration on the scalar yield equation (same structure as §4.1 step 5, but with rate and temperature dependence).

### 4.3  Voce hardening

**Yield stress:**

$$
\sigma_y(\bar{\varepsilon}_p) = \sigma_{y0} + Q\left(1 - e^{-b\bar{\varepsilon}_p}\right)
$$

Substitutes directly into the radial return framework.

---

## 5  Damage models

### 5.1  Lemaitre (CDM)

**Coupling:** damage variable $D \in [0, 1)$ evolves with plasticity.

**Effective stress:** $\tilde{\boldsymbol{\sigma}} = \boldsymbol{\sigma}/(1-D)$

**Yield function (in effective stress space):**

$$
f = \tilde{\sigma}_{eq} - \sigma_y(\bar{\varepsilon}_p) \le 0
$$

**Damage evolution:**

$$
\dot{D} = \left(\frac{Y}{S}\right)^s \dot{\bar{\varepsilon}}_p \quad\text{when } \bar{\varepsilon}_p > \varepsilon_D
$$

**Energy release rate:**

$$
Y = \frac{\sigma_{eq}^2}{6\mu(1-D)^2}\left[\frac{2}{3}(1+\nu) + 3(1-2\nu)\left(\frac{p}{\sigma_{eq}}\right)^2\right]
$$

**Parameters:** `S` (damage strength), `s` (damage exponent), `ε_D` (damage threshold)

**Algorithmic tangent:** includes damage correction terms. The effective tangent is:

$$
\mathbb{C}^{alg}_{damage} = (1-D)\,\mathbb{C}^{alg}_{plastic} - \Delta D \cdot (\text{damage correction})
$$

The exact form depends on whether damage evolves in the current step.

### 5.2  Gurson-Tvergaard-Needleman (GTN)

Pressure-dependent yield surface for porous metals. Out of scope for Phase 2 but interface is defined for future implementation.

**Yield function:**

$$
f = \left(\frac{\sigma_{eq}}{\sigma_y}\right)^2 + 2q_1 f^* \cosh\left(\frac{3q_2 p}{2\sigma_y}\right) - 1 - (q_1 f^*)^2 = 0
$$

---

## 6  Internal variable storage

Each model declares its internal variables. The code generator allocates per-quadrature-point storage:

| Model | Internal variables |
|-------|-------------------|
| `IsotropicElastic` | (none) |
| `NeoHookean` | (none — purely hyperelastic) |
| `J2Plasticity` | `peeq` (scalar), `alpha_ij` (backstress tensor, Voigt) |
| `J2JohnsonCook` | `peeq`, `T` (temperature) |
| `LemaitreDamage` | `peeq`, `D` (damage), `alpha_ij` |

---

## 7  Verification requirements per model

| Model | Required tests |
|-------|---------------|
| All elastic | Patch test (constant strain → exact stress), symmetry of C |
| All hyperelastic | Zero-stress at F=I, frame indifference (rotation), uniaxial match to 1D exact |
| J2 | Elastic predictor correctness, radial return Δλ > 0, yield surface satisfied post-return, tangent symmetry |
| Johnson-Cook | Rate sensitivity (higher rate → higher yield), thermal softening monotonicity |
| Lemaitre | D=0 reduces to J2, D monotonically increases, D→1 gives vanishing stress |

AD verification (using PyTorch/Taichi autodiff) is applied to all energy-based models: define $\Psi$ numerically, compute $S = 2\partial\Psi/\partial C$ via AD, compare against the symbolic expression at random deformation states.
