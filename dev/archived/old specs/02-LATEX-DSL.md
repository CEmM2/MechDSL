# 02 — LaTeX DSL Specification

---

## 1  Design principle

The LaTeX source is a **dual-use document**: it renders correctly through pdflatex (directives are LaTeX comments) and is executable by the CompMech DSL. This means a researcher's paper source *is* their simulation input.

All DSL directives begin with `% mechanics` and appear on their own line. Standard NRPyLaTeX directives (`% declare`, `% coord`, etc.) remain available for raw tensor algebra.

---

## 2  Directive grammar

### 2.1  General syntax

```
DIRECTIVE := '%' 'mechanics' COMMAND { ARGUMENT | OPTION }*
COMMAND   := 'dim' | 'coord' | 'material' | 'formulation'
           | 'constitutive' | 'weak_form' | 'field' | 'bc'
           | 'codegen' | 'verify'
OPTION    := '--' KEY VALUE
VALUE     := SYMBOL | NUMBER | STRING
SYMBOL    := identifier matching [A-Za-z_][A-Za-z0-9_]*
             or LaTeX-escaped Greek: \mu, \kappa, \sigma_y, etc.
```

Directives are processed in order. Later directives may reference symbols defined by earlier ones.

### 2.2  Dimension

```latex
% mechanics dim 2
% mechanics dim 3
```

Sets the spatial dimension. Affects index ranges, Voigt sizes, and element type defaults. Must appear before any tensor or material definitions.

### 2.3  Coordinate systems

```latex
% mechanics coord spatial x y           % 2D spatial
% mechanics coord spatial x y z         % 3D spatial
% mechanics coord material X Y Z        % 3D material (reference)
```

For small-strain problems, only `spatial` is needed. For large-deformation (TL/UL), both `spatial` and `material` must be declared. This is the key NRPyLaTeX extension: indices from different coordinate systems live on different manifolds.

**Index convention:** lowercase Latin (`i, j, k, l`) default to spatial; uppercase Latin (`I, J, K, L`) default to material. This can be overridden:

```latex
% mechanics index spatial i j k l m n
% mechanics index material I J K L M N
```

### 2.4  Material definition

```latex
% mechanics material isotropic --E E --nu nu
% mechanics material neo_hookean --mu \mu --kappa \kappa
% mechanics material j2 --E E --nu nu --sigma_y \sigma_y --H_iso H --H_kin K_h
% mechanics material mooney_rivlin --C1 C_1 --C2 C_2 --kappa \kappa
% mechanics material ogden --N 3 --mu_list \mu_1 \mu_2 \mu_3 --alpha_list \alpha_1 \alpha_2 \alpha_3
% mechanics material lemaitre --E E --nu nu --sigma_y \sigma_y --S_d S --s_d s --eps_d \varepsilon_D
```

Each `--KEY VALUE` pair maps a material parameter name to a SymPy symbol. The symbol can use LaTeX Greek (prefixed with `\`), subscripted names, or plain ASCII.

**Supported material types (Phase 1–2):**

| Type | Parameters | Category |
|------|-----------|----------|
| `isotropic` | `E`, `nu` | Linear elastic |
| `orthotropic` | `E1`, `E2`, `E3`, `G12`, `G13`, `G23`, `nu12`, `nu13`, `nu23` | Linear elastic |
| `neo_hookean` | `mu`, `kappa` | Hyperelastic |
| `mooney_rivlin` | `C1`, `C2`, `kappa` | Hyperelastic |
| `ogden` | `N`, `mu_list`, `alpha_list`, `kappa` | Hyperelastic |
| `hgo` | `mu`, `k1`, `k2`, `kappa`, `kappa_f` | Hyperelastic (anisotropic) |
| `j2` | `E`, `nu`, `sigma_y`, `H_iso`, `H_kin` | Elasto-plastic |
| `j2_jc` | `A`, `B`, `n`, `C`, `m`, `eps0_dot`, `T_melt`, `T_ref` | Johnson-Cook plasticity |
| `lemaitre` | `E`, `nu`, `sigma_y`, `S_d`, `s_d`, `eps_d` | Damage |

### 2.5  Formulation

```latex
% mechanics formulation plane_stress
% mechanics formulation plane_strain
% mechanics formulation 3d
% mechanics formulation total_lagrangian
% mechanics formulation updated_lagrangian
```

For `total_lagrangian` and `updated_lagrangian`, both coordinate systems must be declared. The parser automatically generates the deformation gradient as a two-point tensor.

### 2.6  Field declarations

```latex
% mechanics field u --type vector --space V --order 1
% mechanics field p --type scalar --space Q --order 0
```

Declares solution fields. `--type` is `scalar` or `vector`. `--space` names the function space (used in SymPDE). `--order` sets the polynomial order for code generation defaults.

### 2.7  Constitutive assignment

```latex
% mechanics constitutive Psi --strain_energy
% mechanics constitutive sigma --cauchy
% mechanics constitutive S --pk2
```

Instructs the engine to auto-generate the assigned quantity from the material definition. For energy-based models:

- `--strain_energy` → auto-diff produces PK2 stress and material tangent
- `--cauchy` → push-forward from PK2
- `--pk2` → direct from energy

### 2.8  Weak form

```latex
% mechanics weak_form momentum --test v --trial u --domain Omega
% mechanics weak_form momentum --residual  % nonlinear: generate R(u), not a(u,v)
```

Instructs the engine to construct the SymPDE variational form. For linear problems, generates `BilinearForm((v,u), ...)` and `LinearForm(v, ...)`. For nonlinear, generates the residual `R(u; v)` and its Gâteaux derivative for Newton.

### 2.9  Boundary conditions

```latex
% mechanics bc dirichlet --field u --boundary left --value 0
% mechanics bc neumann --field u --boundary right --traction "0, -P/A"
% mechanics bc body_force --field u --value "0, -rho*g"
```

BC directives are metadata for code generation. The symbolic engine doesn't enforce BCs; the code generator inserts them into the solver.

### 2.10  Code generation

```latex
% mechanics codegen --target taichi --output cantilever.py
% mechanics codegen --target mfem --output cantilever_mfem.cpp
% mechanics codegen --target moose --output CantileverMaterial.C
```

### 2.11  Verification

```latex
% mechanics verify --benchmark cantilever_beam --E 200e9 --nu 0.3 --P 1e6
% mechanics verify --method mms --order 2
% mechanics verify --patch_test
```

---

## 3  NRPyLaTeX fork: required parser modifications

### 3.1  Two-point tensor support

**Problem:** NRPyLaTeX assumes all indices live on the same manifold with the same dimension. The deformation gradient `F_{iI}` has spatial index `i` (range 1..d) and material index `I` (range 1..D). With `d = D`, the dimension is the same, but the index *sets* are semantically distinct.

**Solution:** Extend `IndexedSymbol` with a `manifold` attribute:

```python
class IndexedSymbol:
    # existing fields...
    manifold: str | None   # NEW: 'spatial', 'material', or None (universal)
```

The parser tracks which index belongs to which manifold via the `% mechanics index` directives. When building contractions (Einstein summation), the parser verifies that contracted indices share the same manifold — contracting a spatial index with a material index is an error unless it's through a two-point tensor.

**Grammar change in `_operator`:**

```
# Existing: subscript indices all use same dimension
# Extended: each index checks its manifold → dimension mapping

_property['manifold'] = {
    'spatial': {'indices': set(), 'dim': 3},
    'material': {'indices': set(), 'dim': 3},
}
```

### 3.2  New token types

Add to `scanner.py`:

```python
('MECHANICS_KWD',    r'mechanics'),
('MATERIAL_KWD',     r'material'),
('FORMULATION_KWD',  r'formulation'),
('FIELD_KWD',        r'field'),
('CONSTITUTIVE_KWD', r'constitutive'),
('WEAK_FORM_KWD',    r'weak_form'),
('BC_KWD',           r'bc'),
('CODEGEN_KWD',      r'codegen'),
('VERIFY_KWD',       r'verify'),
```

### 3.3  New config handler

In `parser.py`, extend `_config()`:

```python
def _config(self):
    ...
    elif self.accept('MECHANICS_KWD'):
        self._mechanics_directive()
```

The `_mechanics_directive()` method dispatches to sub-handlers based on the command token.

### 3.4  Backward compatibility

All existing NRPyLaTeX syntax remains valid. The `% mechanics` namespace is disjoint from `% declare`, `% coord`, `% ignore`, `% replace`. A file can mix both:

```latex
% declare coord x y z          % NRPyLaTeX native
% declare gDD --dim 3 --zeros  % NRPyLaTeX native
% mechanics material neo_hookean --mu mu --kappa kappa  % CompMech DSL
```

---

## 4  User-defined equations

Beyond directives, the user can write standard LaTeX equations that the parser interprets:

```latex
\Psi = \frac{\mu}{2}\left(\bar{I}_1 - 3\right) + \frac{\kappa}{2}\left(J - 1\right)^2
```

When a `% mechanics constitutive Psi --strain_energy` directive is present, the parser locates the equation defining `\Psi`, parses it to SymPy via NRPyLaTeX, and hands it to Layer 2 for auto-differentiation.

This enables **user-defined constitutive models** without touching the DSL source code.

---

## 5  Complete example

```latex
\documentclass{article}
\begin{document}

% mechanics dim 2
% mechanics coord spatial x y
% mechanics material isotropic --E E --nu nu
% mechanics formulation plane_stress
% mechanics field u --type vector --space V --order 1

%% The weak form for linear elasticity
% mechanics weak_form momentum --test v --trial u --domain Omega

%% Boundary conditions
% mechanics bc dirichlet --field u --boundary left --value 0
% mechanics bc neumann --field u --boundary right --traction "0, -1e6/9"

%% Generate Taichi solver
% mechanics codegen --target taichi --output beam_solver.py

%% Verify against analytical solution
% mechanics verify --benchmark cantilever_beam --E 200e9 --nu 0.3 --P 1e6

The displacement field satisfies
\begin{equation}
    \nabla \cdot \boldsymbol{\sigma} + \mathbf{b} = \mathbf{0}
\end{equation}
where $\sigma_{ij} = C_{ijkl} \varepsilon_{kl}$ and
$\varepsilon_{ij} = \frac{1}{2}\left(\frac{\partial u_i}{\partial x_j}
    + \frac{\partial u_j}{\partial x_i}\right)$.

\end{document}
```

When processed by `compmech.frontend.parse()`, this produces a complete context dictionary. When processed by the full pipeline, it emits `beam_solver.py` and runs the verification benchmark.

When processed by `pdflatex`, it renders a normal document with the equation displayed. The `% mechanics` lines are invisible.
