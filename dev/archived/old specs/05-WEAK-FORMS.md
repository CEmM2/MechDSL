# 05 — Weak Forms and Variational Formulations

---

## 1  Overview

This document specifies how the strong-form balance equations are converted to weak (variational) forms suitable for finite element discretisation, and how these are represented in SymPDE.

---

## 2  Strong forms

### 2.1  Quasi-static momentum balance (spatial)

$$
\nabla \cdot \boldsymbol{\sigma} + \mathbf{b} = \mathbf{0} \quad\text{in } \Omega
$$

with boundary conditions:

$$
\mathbf{u} = \bar{\mathbf{u}} \quad\text{on } \Gamma_D, \qquad
\boldsymbol{\sigma}\cdot\mathbf{n} = \bar{\mathbf{t}} \quad\text{on } \Gamma_N
$$

### 2.2  Dynamic momentum balance

$$
\nabla \cdot \boldsymbol{\sigma} + \mathbf{b} = \rho\ddot{\mathbf{u}} \quad\text{in } \Omega
$$

### 2.3  Total Lagrangian form (material)

$$
\nabla_0 \cdot \mathbf{P} + \mathbf{b}_0 = \rho_0\ddot{\mathbf{u}} \quad\text{in } \Omega_0
$$

where $\mathbf{P} = \mathbf{F}\mathbf{S}$ is the first Piola-Kirchhoff stress and $\nabla_0$ is the gradient with respect to material coordinates.

---

## 3  Weak forms

### 3.1  Small-strain linear elasticity

**Bilinear form:**

$$
a(\mathbf{u}, \mathbf{v}) = \int_\Omega \boldsymbol{\varepsilon}(\mathbf{v}) : \mathbb{C} : \boldsymbol{\varepsilon}(\mathbf{u})\,d\Omega
$$

**Linear form:**

$$
L(\mathbf{v}) = \int_\Omega \mathbf{b} \cdot \mathbf{v}\,d\Omega + \int_{\Gamma_N} \bar{\mathbf{t}} \cdot \mathbf{v}\,d\Gamma
$$

**Problem:** Find $\mathbf{u} \in V$ such that $a(\mathbf{u}, \mathbf{v}) = L(\mathbf{v})$ for all $\mathbf{v} \in V_0$.

**SymPDE representation:**

```python
domain = Domain('Omega', dim=2)
V = VectorFunctionSpace('V', domain)
u, v = elements_of(V, names='u,v')

# Expand ε:C:ε using component-wise construction
integrand = sum(
    eps_v[I] * C_voigt[I, J] * eps_u[J]
    for I in range(n_voigt) for J in range(n_voigt)
)
a = BilinearForm((u, v), integral(domain, integrand))
```

### 3.2  Nonlinear elasticity (Total Lagrangian)

**Residual form:**

$$
R(\mathbf{u}; \mathbf{v}) = \int_{\Omega_0} \mathbf{P}(\mathbf{u}) : \nabla_0 \mathbf{v}\,d\Omega_0 - \int_{\Omega_0}\mathbf{b}_0\cdot\mathbf{v}\,d\Omega_0 - \int_{\Gamma_{N,0}}\bar{\mathbf{t}}_0\cdot\mathbf{v}\,d\Gamma_0 = 0
$$

Equivalently in index notation:

$$
R_i(\mathbf{u}; \mathbf{v}) = \int_{\Omega_0} P_{iI}\frac{\partial v_i}{\partial X_I}\,d\Omega_0 - \int_{\Omega_0} b_{0i}\,v_i\,d\Omega_0 = 0
$$

Or using PK2:

$$
R_i(\mathbf{u}; \mathbf{v}) = \int_{\Omega_0} S_{IJ}\frac{\partial v_i}{\partial X_I}F_{iJ}\,d\Omega_0 - (\text{external}) = 0
$$

### 3.3  Linearisation for Newton-Raphson

The tangent bilinear form is the Gâteaux derivative of the residual:

$$
D R(\mathbf{u}; \mathbf{v})[\Delta\mathbf{u}] = \int_{\Omega_0} \left[\nabla_0\mathbf{v} : \mathbb{A} : \nabla_0\Delta\mathbf{u}\right] d\Omega_0
$$

This splits into a **material tangent** and a **geometric stiffness**:

$$
D R = \underbrace{\int_{\Omega_0} \frac{\partial v_i}{\partial X_I}\,\mathcal{A}_{iIjJ}\,\frac{\partial \Delta u_j}{\partial X_J}\,d\Omega_0}_{\text{material stiffness}}
$$

where the effective tangent $\mathcal{A}_{iIjJ}$ incorporates both the constitutive tangent and geometric terms:

$$
\mathcal{A}_{iIjJ} = \delta_{ij}\,S_{IJ} + F_{iK}\,\mathbb{C}_{KILJ}\,F_{jL}
$$

The first term is the **geometric (initial stress) stiffness**. The second is the **material stiffness** pushed to the mixed configuration.

### 3.4  Updated Lagrangian form

Same structure as TL, but integrals evaluated over the current configuration $\Omega$, using spatial gradients $\nabla$ instead of $\nabla_0$:

$$
R(\mathbf{u}; \mathbf{v}) = \int_\Omega \boldsymbol{\sigma} : \nabla\mathbf{v}\,d\Omega - (\text{external}) = 0
$$

Linearisation:

$$
DR[\Delta\mathbf{u}] = \int_\Omega \nabla\mathbf{v} : \left[\mathbf{c}^{Jau} + \boldsymbol{\sigma}\otimes\mathbf{I}\right] : \nabla\Delta\mathbf{u}\,d\Omega
$$

where $\mathbf{c}^{Jau}$ is the Jaumann rate tangent (spatial, symmetric).

---

## 4  SymPDE mapping details

### 4.1  Component expansion of ε:C:ε

For 2D plane stress, the integrand expands to:

```
a_integrand = C[0,0]*dx(v[0])*dx(u[0])
            + C[0,1]*dx(v[0])*dy(u[1])
            + C[1,0]*dy(v[1])*dx(u[0])
            + C[1,1]*dy(v[1])*dy(u[1])
            + C[2,2]*(dy(v[0]) + dx(v[1]))*(dy(u[0]) + dx(u[1]))
            + ... (cross terms)
```

This is what `TerminalExpr` produces when given the abstract form. The code generator walks this expression tree.

### 4.2  Handling TerminalExpr output

`TerminalExpr` returns a tuple of `DomainExpression` objects. Each contains a matrix of component-wise derivative expressions using SymPDE's internal `dx1`, `dx2`, `dx3` operators.

The code generator must:

1. Extract the scalar integrand from each `DomainExpression`
2. Identify which derivatives appear (these determine which shape function gradients are needed)
3. Map `dx1(u[0])` to `dN/dx * u_local[0]` in element code
4. Sum contributions across the matrix (for vector-valued problems)

### 4.3  Surface integrals (Neumann BCs)

SymPDE supports boundary integrals:

```python
from sympde.topology import Boundary
boundary = Boundary('Gamma_N', domain)
l_neumann = LinearForm(v, integral(boundary, dot(t_bar, v)))
```

The code generator translates these to face/edge integration in the element routine.

---

## 5  Mass matrix (dynamics)

For explicit dynamics:

$$
M(\ddot{\mathbf{u}}, \mathbf{v}) = \int_\Omega \rho\,\ddot{\mathbf{u}} \cdot \mathbf{v}\,d\Omega
$$

SymPDE representation:

```python
rho = Constant('rho')
m = BilinearForm((u, v), integral(domain, rho * dot(u, v)))
```

For explicit solvers, the lumped mass matrix is used (row-sum lumping). This is handled at the code generation level, not in the symbolic form.

---

## 6  Element types and quadrature

The weak form is element-agnostic. Element-specific details (shape functions, quadrature rules) are injected at code generation. The symbolic form only specifies:

- Domain dimension
- Function space polynomial order
- Whether the problem is linear or nonlinear

**Supported elements (Phase 1):**

| Element | Nodes | Order | Quadrature | Notes |
|---------|-------|-------|------------|-------|
| CST (Tri3) | 3 | 1 | 1 point | PoC, stiff in bending |
| LST (Tri6) | 6 | 2 | 3 points | Recommended for accuracy |
| Q4 (Quad4) | 4 | 1 (bilinear) | 2×2 | Standard workhorse |
| Q8 (Quad8) | 8 | 2 (serendipity) | 3×3 | Higher accuracy |
| Tet4 | 4 | 1 | 1 point | 3D linear |
| Tet10 | 10 | 2 | 4 points | 3D quadratic |
| Hex8 | 8 | 1 (trilinear) | 2×2×2 | 3D workhorse |
| Hex20 | 20 | 2 (serendipity) | 3×3×3 | 3D higher-order |

---

## 7  Stabilisation

### 7.1  Incompressibility

Near-incompressible materials ($\nu \to 0.5$) cause volumetric locking with standard displacement elements. Options:

- **B-bar method:** modify the B-matrix to use mean volumetric strain
- **Mixed u/p formulation:** separate displacement and pressure fields (requires stable element pair, e.g. Q2/Q1 Taylor-Hood)
- **Selective reduced integration:** under-integrate volumetric terms

The DSL supports these via directives:

```latex
% mechanics stabilisation b_bar
% mechanics stabilisation mixed_up --pressure_order 0
```

### 7.2  Hourglass control

Reduced-integration elements (1-point Hex8, 1-point Quad4) require hourglass stabilisation. The code generator adds Flanagan-Belytschko hourglass viscosity when reduced integration is selected.

```latex
% mechanics integration reduced --hourglass flanagan_belytschko
```
