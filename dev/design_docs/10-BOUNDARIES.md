# 10 — Boundary Mapping and Enforcement

---

## 1  Purpose

Boundary-condition handling is a **first-class compiler and runtime concern**, not incidental postprocessing. This document specifies how boundary conditions flow from the LaTeX source through the IR to generated code.

---

## 2  Boundary mapping pipeline

```
LaTeX source:
    % mechanics boundary Gamma_u --type dirichlet --field u --components 0 1 2 --value 0
    % mechanics boundary Gamma_t --type neumann --traction "t_bar"
        │
        ▼
Parser (Layer 1) ──→ raw BC declarations in context dict
        │
        ▼
Mechanics IR ──→ DirichletBCIR / NeumannBCIR referencing named BoundaryRegionIR
        │
        ▼
Runtime binding ──→ mesh tags mapped to named regions
        │
        ▼
Code generation ──→ BC enforcement routines in generated Taichi code
```

---

## 3  Boundary region model

### 3.1  Named regions

Every boundary region has a **name** declared in the LaTeX source:

```latex
% mechanics domain Omega_0
% mechanics boundary Gamma_u    % fixed face
% mechanics boundary Gamma_t    % loaded face
```

Regions are purely symbolic at compile time. They are mapped to concrete mesh tags at bind time (when the mesh is loaded).

### 3.2  Region-to-mesh mapping

The runtime driver maps named regions to mesh tags:

```python
mesh = load_mesh("bar.vtk")
bc_map = {
    "Gamma_u": mesh.tag("fixed"),      # mesh-level tag
    "Gamma_t": mesh.tag("loaded"),
}
artifact.bind_mesh(mesh).bind_bcs(bc_map)
```

The compiler validates at bind time that all declared regions have a mesh-tag binding. Missing bindings produce a `BoundaryBindingError`.

---

## 4  Essential (Dirichlet) boundary conditions

### 4.1  IR representation

```python
@dataclass
class DirichletBCIR:
    region: str                      # "Gamma_u"
    field: str                       # "u"
    components: list[int] | None     # None = all, [0] = x-only
    value: Expr | float              # 0.0, or symbolic for displacement-controlled
```

### 4.2  Enforcement strategy (MVP)

**Algebraic elimination / row-column zeroing**, compatible with the imported matrix-free linear solver.

For a fixed DOF $i$ with prescribed value $\bar{u}_i$:

1. **Residual modification:** Set $R_i = 0$ (or $R_i = u_i - \bar{u}_i$ for non-zero prescribed).
2. **Tangent modification:** In the matrix-free matvec $y = K x$:
   - Set $y_i = x_i$ (identity row).
   - In the assembly kernel, skip contribution to row $i$ and column $i$.
3. **Increment modification:** After solve, set $\delta u_i = 0$ (fixed) or $\delta u_i = \Delta\bar{u}_i$ (prescribed increment).

Implementation detail: a `bc_mask` field marks fixed DOFs. The assembly kernel checks the mask; the matvec applies identity on masked DOFs.

```python
@ti.field(dtype=ti.i32, shape=(MAX_NODES, 3))
bc_mask: ti.field  # 1 = fixed, 0 = free

@ti.func
def apply_dirichlet_residual(R: ti.template(), u: ti.template()):
    for i in range(n_nodes[None]):
        for d in ti.static(range(3)):
            if bc_mask[i, d] == 1:
                R[i][d] = 0.0

@ti.func
def apply_dirichlet_increment(du: ti.template()):
    for i in range(n_nodes[None]):
        for d in ti.static(range(3)):
            if bc_mask[i, d] == 1:
                du[i][d] = 0.0
```

### 4.3  Symmetry preservation

The algebraic elimination preserves symmetry of the tangent operator. This is important for the CG/PCG linear solver (which requires SPD). The identity-row/identity-column approach maintains the symmetric structure.

### 4.4  Component-wise BCs

The `components` field allows fixing individual displacement components:

- `components: [0, 1, 2]` — fully fixed node (all DOFs)
- `components: [0]` — roller in x (only x-displacement fixed)
- `components: [1, 2]` — symmetry plane (y and z fixed, x free)

---

## 5  Natural (Neumann) boundary conditions

### 5.1  IR representation

```python
@dataclass
class NeumannBCIR:
    region: str                      # "Gamma_t"
    value: Expr | list[Expr]         # traction vector [t_x, t_y, t_z]
```

### 5.2  Implementation

Traction BCs contribute to the external force vector:

$$
f^{ext}_a = \int_{\Gamma_t} N_a \, \bar{t}_i \, dA
$$

For the MVP, traction is **constant** over each boundary face. The integration requires:

1. Identify boundary faces belonging to the named region.
2. Compute face area and outward normal.
3. Integrate $N_a \, \bar{t}_i$ over the face using surface quadrature.
4. Scatter to nodal external forces.

Generated code:

```python
@ti.kernel
def compute_traction_forces():
    for f in range(n_boundary_faces[None]):
        if face_tag[f] == GAMMA_T_TAG:
            area = face_area[f]
            # 4-point face quadrature for hex8 face (quad4)
            for q in ti.static(range(4)):
                for a in ti.static(range(4)):  # 4 face nodes
                    node = face_conn[f, a]
                    for d in ti.static(range(3)):
                        contrib = face_N[a, q] * traction[d] * face_detJ[f, q] * face_w[q]
                        ti.atomic_add(f_ext[node][d], contrib)
```

### 5.3  Follower loads (future)

For large-deformation problems, traction direction may follow the deformed surface (pressure loads). This is a Plan B extension. The MVP assumes dead loads (traction direction fixed in reference configuration), consistent with the TL formulation.

---

## 6  Displacement-controlled loading

For the MVP Newton-Raphson driver, displacement-controlled loading is implemented as incremental Dirichlet BCs:

```python
for step in range(n_steps):
    # Increment prescribed displacement
    u_prescribed += delta_u_prescribed
    # Apply as Dirichlet BC
    for node in fixed_nodes:
        u[node] = u_prescribed
    # Newton iterations with du = 0 on fixed DOFs
    newton_solve(...)
```

The BC value in the IR can be a symbolic expression involving a load parameter $\lambda$:

```python
DirichletBCIR(region="Gamma_t", field="u", components=[0], value=lambda_sym * u_max)
```

---

## 7  Validation

### 7.1  Compile-time checks

- All BC regions reference declared boundary regions in the domain
- No region has both Dirichlet and Neumann BCs on the same field component
- At least one Dirichlet BC exists (otherwise the problem is singular)

### 7.2  Bind-time checks

- All declared boundary regions have mesh-tag bindings
- Mesh tags are valid (exist in the mesh file)
- Boundary faces are correctly oriented (outward normal consistent)

### 7.3  Runtime checks

- Zero-pivot detection if Dirichlet BCs are insufficient (degenerate system)
- Warning if no Neumann BCs and no body forces (trivial problem)

---

## 8  Future extensions (Plan B)

| Extension | Phase | Description |
|-----------|-------|-------------|
| Penalty method | B5 | Alternative to algebraic elimination for some solver configurations |
| Lagrange multipliers | B5 | For constrained problems |
| Nonlinear BCs | B1 | BC update in current configuration for UL formulation |
| Contact | Future | Normal/tangential contact constraints |
| Periodic BCs | Future | For RVE homogenisation problems |
| Follower pressure | B1 | Pressure loads that follow deformed surface normal |

---

## 9  Relationship to other specs

| Spec | Relationship |
|------|-------------|
| `04-MECHANICS-IR.md` | Boundary entities (DirichletBCIR, NeumannBCIR) are part of ProblemIR |
| `05-ELEMENT-IR.md` | Element IR handles volume integrals; boundary integration is separate |
| `06-CODEGEN.md` | Generated BC routines are emitted alongside element kernels |
| `07-CONVENTIONS.md` | Outward normal convention (§4.5), tension-positive sign (§4.1) |
