# 03 — Symbolic Engine

---

## 1  Purpose

The symbolic engine sits between the parser (Layer 1) and the weak form builder (Layer 3). It takes the parsed context dictionary and produces fully expanded symbolic expressions for stress, tangent, and kinematic quantities. Everything in this layer is SymPy — no numerics.

---

## 2  Kinematics module

### 2.1  Small strain

For `formulation` in `{plane_stress, plane_strain, 3d}` with linear material models:

```python
ε_ij = (1/2) * (∂u_i/∂x_j + ∂u_j/∂x_i)
```

No kinematics object is produced — the strain-displacement relation is handled directly in the Voigt B-matrix at code generation time.

### 2.2  Finite deformation

For `formulation` in `{total_lagrangian, updated_lagrangian}`:

**Input:** displacement field `u_i(X_J)`, dimension `d`

**Outputs (KinematicsResult):**

| Symbol | Expression | Name |
|--------|------------|------|
| `F_iI` | `δ_iI + ∂u_i/∂X_I` | Deformation gradient |
| `J` | `det(F)` | Jacobian |
| `C_IJ` | `F_kI F_kJ` | Right Cauchy-Green |
| `b_ij` | `F_iK F_jK` | Left Cauchy-Green |
| `E_IJ` | `(1/2)(C_IJ - δ_IJ)` | Green-Lagrange strain |
| `e_ij` | `(1/2)(δ_ij - b^{-1}_ij)` | Euler-Almansi strain |
| `Finv_Ii` | `F^{-1}` | Inverse deformation gradient |
| `FinvT_iI` | `F^{-T}` | Inverse transpose |

**Invariants** (for isotropic hyperelasticity):

| Symbol | Expression |
|--------|------------|
| `I1` | `tr(C)` |
| `I2` | `(1/2)(tr(C)² - tr(C²))` |
| `I3` | `det(C) = J²` |
| `Ibar1` | `J^{-2/3} I1` (deviatoric) |
| `Ibar2` | `J^{-4/3} I2` (deviatoric) |

### 2.3  Implementation

All expressions are SymPy `MatrixSymbol` or explicit `Matrix` objects. The deformation gradient is constructed symbolically:

```python
from sympy import symbols, Matrix, eye, sqrt, det, diff

def build_kinematics(u_components, X_coords, dim):
    """
    u_components: list of SymPy Function objects [u1(X1,X2,X3), ...]
    X_coords: list of Symbol [X1, X2, X3]
    dim: int
    """
    F = eye(dim)
    for i in range(dim):
        for I in range(dim):
            F[i, I] += diff(u_components[i], X_coords[I])

    J = det(F)
    C = F.T * F
    E = (C - eye(dim)) / 2
    b = F * F.T
    Finv = F.inv()
    FinvT = Finv.T

    return KinematicsResult(F=F, J=J, C=C, E=E, b=b, Finv=Finv, FinvT=FinvT)
```

---

## 3  Constitutive module

### 3.1  Energy-based models (hyperelasticity)

For hyperelastic materials, the constitutive response is derived entirely from the strain energy function `Ψ(C)` (or equivalently `Ψ(I1, I2, J)`).

**Auto-differentiation chain:**

```
Ψ(C)  ──sympy.diff──→  S_IJ = 2 ∂Ψ/∂C_IJ  ──sympy.diff──→  ℂ_IJKL = 2 ∂S_IJ/∂C_KL
```

The engine uses SymPy's symbolic differentiation. For invariant-based models, the chain rule applies:

```
S_IJ = 2 (∂Ψ/∂I1 · ∂I1/∂C_IJ + ∂Ψ/∂I2 · ∂I2/∂C_IJ + ∂Ψ/∂J · ∂J/∂C_IJ)
```

**Push-forward to Cauchy stress:**

```
σ_ij = (1/J) F_iI S_IJ F_jJ
```

Or equivalently via PK1:

```
P_iI = F_iJ S_JI
σ_ij = (1/J) P_iI F_jI
```

### 3.2  Rate models (plasticity, damage)

Rate-dependent models cannot be expressed as a single energy function. Instead, the engine stores:

- **Elastic tangent** `ℂ_e` (from the elastic part of the model)
- **Yield function** `f(σ, α)` where `α` is a set of internal variables
- **Flow rule** `∂f/∂σ` (associated or non-associated)
- **Hardening law** `H(α)` — relates internal variable evolution to plastic multiplier
- **Algorithmic tangent** `ℂ_alg` — the consistent tangent after return mapping

For J2 plasticity, the algorithmic tangent is derived symbolically:

```
ℂ^alg_ijkl = ℂ^e_ijkl - (6μ² Δλ / σ_eq^tr) P_ijkl
             - (6μ²/(3μ + H')) n_ij n_kl
             + (6μ² Δλ / σ_eq^tr) (1/3) δ_ij δ_kl
```

where `P_ijkl = I^{dev}_ijkl - (1/3)δ_ij δ_kl` is the deviatoric projection, `n_ij = s^tr_ij / ||s^tr||`, and `Δλ` is the plastic multiplier.

The engine provides these expressions symbolically. Numerical evaluation happens in generated code.

### 3.3  Damage models

Lemaitre-type damage introduces a damage variable `D ∈ [0, 1)` coupled to the plasticity:

```
σ̃_ij = σ_ij / (1 - D)        (effective stress)
Ḋ = (Y/S)^s · ε̇_p            (damage evolution)
Y = σ_eq²/(6μ(1-D)²) + p²/(2κ(1-D)²)   (energy release rate)
```

The engine stores the damage evolution law and modifies the effective tangent accordingly.

### 3.4  Constitutive interface

```python
class ConstitutiveModel:
    """Base class for all constitutive models."""

    name: str
    params: dict[str, Symbol]
    dim: int

    def strain_energy(self, kin: KinematicsResult) -> Expr | None:
        """Return Ψ(C) or None for rate models."""
        ...

    def pk2_stress(self, kin: KinematicsResult) -> Matrix:
        """Return S_IJ (material frame, 2nd Piola-Kirchhoff)."""
        ...

    def cauchy_stress(self, kin: KinematicsResult) -> Matrix:
        """Return σ_ij (spatial frame)."""
        ...

    def material_tangent(self, kin: KinematicsResult) -> Array:
        """Return ℂ_IJKL (4th order, material frame)."""
        ...

    def voigt_tangent(self, kin: KinematicsResult) -> Matrix:
        """Return C_IJ (Voigt, material frame)."""
        ...

    def internal_variables(self) -> list[str]:
        """Return names of internal state variables."""
        ...

    def evolution_equations(self) -> dict[str, Expr]:
        """Return symbolic evolution equations for internal variables."""
        ...
```

---

## 4  Voigt module

### 4.1  Ordering convention (hard rule)

Tensorial Voigt, unscaled shears.

**3D (6 components):**

| Voigt index | Tensor indices |
|-------------|---------------|
| 0 | (0,0) = xx |
| 1 | (1,1) = yy |
| 2 | (2,2) = zz |
| 3 | (0,1) = (1,0) = xy |
| 4 | (0,2) = (2,0) = xz |
| 5 | (1,2) = (2,1) = yz |

**2D (3 components):**

| Voigt index | Tensor indices |
|-------------|---------------|
| 0 | (0,0) = xx |
| 1 | (1,1) = yy |
| 2 | (0,1) = (1,0) = xy |

### 4.2  Conversion functions

```python
def tensor_to_voigt_2(A: Matrix) -> Matrix:
    """Symmetric 2×2 tensor → 3-vector (tensorial Voigt)."""
    return Matrix([A[0,0], A[1,1], A[0,1]])

def tensor_to_voigt_3(A: Matrix) -> Matrix:
    """Symmetric 3×3 tensor → 6-vector (tensorial Voigt)."""
    return Matrix([A[0,0], A[1,1], A[2,2], A[0,1], A[0,2], A[1,2]])

def voigt_to_tensor_2(v: Matrix) -> Matrix:
    """3-vector → symmetric 2×2."""
    return Matrix([[v[0], v[2]], [v[2], v[1]]])

def voigt_to_tensor_3(v: Matrix) -> Matrix:
    """6-vector → symmetric 3×3."""
    return Matrix([[v[0], v[3], v[4]],
                   [v[3], v[1], v[5]],
                   [v[4], v[5], v[2]]])

def tangent_4to_voigt(C_ijkl, dim: int) -> Matrix:
    """4th-order tensor C_ijkl → Voigt matrix C_IJ."""
    ...
```

### 4.3  Mandel conversion (for tangent rotation)

```python
P = diag([1, 1, 1, sqrt(2), sqrt(2), sqrt(2)])     # 3D

C_mandel = P * C_voigt * P.inv()
C_voigt  = P.inv() * C_mandel * P
```

Tangent rotation in Mandel space is a similarity transform: `C'_M = T C_M T^T` where `T` is built from the rotation matrix `R`. See `07-CONVENTIONS.md` for the exact `T(R)` construction.

---

## 5  SymPDE integration layer

### 5.1  Adapter: symbolic engine → SymPDE

The adapter translates from the symbolic engine's tensor notation to SymPDE's operator notation:

| Symbolic engine | SymPDE equivalent |
|-----------------|-------------------|
| `∂u_i/∂x_j` | `grad(u)[i,j]` (via TerminalExpr: `dx_j(u[i])`) |
| `ε_ij(u)` | `(1/2)(grad(u) + grad(u)^T)` — manual sym since SymPDE lacks `sym_grad` |
| `C_ijkl ε_kl` | Explicit double contraction expanded in components |
| `σ_ij n_j` | Used in Neumann BC via SymPDE surface integral |
| `∫_Ω f dΩ` | `integral(domain, f)` |

### 5.2  Missing SymPDE feature: `sym_grad`

SymPDE (v0.19) does not have a symmetric gradient operator. The adapter constructs it manually:

```python
def sym_grad(u, domain):
    """Build symmetric gradient as (1/2)(grad(u) + grad(u)^T) in SymPDE."""
    from sympde.calculus import grad, Transpose
    G = grad(u)
    return (G + Transpose(G)) / 2
```

If SymPDE adds `sym_grad` upstream, the adapter should delegate to it.

### 5.3  Form construction

For linear elasticity:

```python
def build_linear_elastic_form(domain, V, C_voigt, dim):
    u, v = elements_of(V, names='u,v')
    # Expand ε(v) : C : ε(u) component-wise
    integrand = expand_constitutive_integrand(v, u, C_voigt, dim)
    a = BilinearForm((u, v), integral(domain, integrand))
    return a
```

The `expand_constitutive_integrand` function builds the full double contraction `ε_ij(v) C_ijkl ε_kl(u)` using SymPDE's `dx1`, `dx2`, etc. operators — matching what `TerminalExpr` would produce.

For nonlinear problems, the adapter constructs the residual form `R(u; v)` and uses SymPy differentiation (not SymPDE's `derivative`) to produce the tangent bilinear form.
