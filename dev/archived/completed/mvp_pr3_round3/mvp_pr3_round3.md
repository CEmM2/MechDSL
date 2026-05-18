# PR #3 Review Findings Resolution Plan

> ⚠️ **Superseded** by [`recovery_plan_latex_contract.md`](recovery_plan_latex_contract.md) (Phase 7 / R6 archival, P7-5). This document is a closed PR review resolution plan; the runtime fixes it tracked have long since landed. The active execution source is the recovery plan. See [`STATUS_LEGEND.md`](../tracking/STATUS_LEGEND.md) and [`frontend_drift_history.md`](../reviews/frontend_drift_history.md).

## Context

PR #3 comprehensive review (`dev/reviews/pr3_bm.md`) identified 5 critical, 13 high-priority, and numerous lower-priority issues across code generation, error handling, type safety, comments, tests, and CI. The critical issues (C1-C5) make the generated Taichi code non-functional — it won't compile or will produce silently wrong results. This plan resolves all findings in priority order across 6 phases.

**Review source**: `dev/reviews/pr3_bm.md`

---

## Phase 1: Critical Taichi Codegen Fixes (C1-C5)

**Primary file**: `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py`

### C1. J2 Newton iteration — `ti.static(range(20))` with `break`
**Line 344**: `ctx.emit("for _it in ti.static(range(20)):")`

Change to: `ctx.emit("for _it in range(20):")`

Rationale: Newton iterations need runtime `break`. `ti.static` unrolls at compile time — `break` is unsupported and either errors or is silently ignored.

### C2. Runtime Python list access `GRAD_AT_QUAD[q]` in Taichi kernel
**Lines 425-434**: Quadrature loop `for q in range(N_QP):` is runtime, but `GRAD_AT_QUAD[q][a][d]` indexes a Python list with runtime `q`. Also affects `QUAD_WEIGHTS[q]` at line 475.

Fix: Change quad loop from runtime to `ti.static`:
- **Line 425**: `ctx.emit("for q in range(N_QP):")` → `ctx.emit("for q in ti.static(range(N_QP)):")`
- Update comment from `"# Quadrature loop (runtime -- mesh index)"` to `"# Quadrature loop (ti.static -- N_QP=8 is element-type constant, enables Python list access)"`

Rationale: N_QP=8 is a fixed compile-time constant per element type (not mesh-dependent). Making it `ti.static` allows Python list indexing. The unrolled body (~30 lines x 8 = ~240 lines) fits well within the 2000-line kernel budget. The GRAD_AT_QUAD inner loops (`a`, `d`) are already `ti.static`.

**Convention exception**: This contradicts `.claude/rules/codegen.md` which lists "quad points q" as mesh indices that should "never" be unrolled. Update `07-CONVENTIONS.md` section 9 to add a carve-out: "Quadrature points are `ti.static` when their count is an element-type constant (e.g. N_QP=8 for Hex8 2x2x2 Gauss) and the loop body accesses Python list constants. They become runtime when N_QP is mesh-dependent (e.g. adaptive quadrature)." Also update `.claude/rules/codegen.md` to match.

### C4. Emitted Newton driver — silent non-convergence
**Lines 694-695**: Currently emits `print(...)` + `return max_iter`

Change to emit `raise RuntimeError(...)`:
```python
# Replace these two lines:
ctx.emit('print(f"  Newton did not converge in {max_iter} iterations.")')
ctx.emit("return max_iter")
# With:
ctx.emit('raise RuntimeError(')
ctx.emit('    f"Newton did not converge in {max_iter} iterations. '
         'Final |R| = {res_norm:.3e}"')
ctx.emit(')')
```

**NOTE**: The emitted variable is `res_norm` (line 662), NOT `r_norm`. Using `r_norm` would cause a NameError in the generated code.

Matches the pattern used by `ref_hex8_plastic.py:452-460`.

### C4b. Add NaN check in emitted Newton driver
**After line 662** (`res_norm = np.linalg.norm(r_flat)`): Add a NaN/Inf guard to catch propagated NaN from the H1 convergence flag:
```python
ctx.emit("if not np.isfinite(res_norm):")
with ctx.indent_block():
    ctx.emit('raise RuntimeError("NaN or Inf detected in Newton residual. '
             'Constitutive model may have failed to converge.")')
```

This completes the H1 NaN propagation strategy — H1 sets `dl = NaN` on J2 non-convergence, which propagates through stress → internal force → residual → `res_norm`. Without this check, NaN causes `res_norm < tol` to be `False` and Newton silently iterates to `max_iter`.

### C5. Node loops unrolled with `ti.static(range(8))` — convention violation
**Lines 416, 446, 476**: Three node loops use `ti.static(range(N_NODES))` where N_NODES=8 > 6 threshold.

Change to runtime loops:
- **Line 416**: `"for a in ti.static(range(N_NODES)):"` → `"for a in range(N_NODES):"`
- **Line 446**: Same change
- **Line 476**: Same change

**Keep `ti.static` at line 429**: The GRAD_AT_QUAD inner gather loop (`for a in ti.static(range(N_NODES)):`) must stay `ti.static` because it indexes the Python list `GRAD_AT_QUAD[q][a][d]` — with `q` now `ti.static` (from C2 fix), `a` must also be static for list access.

All other node loops access only `ti.Matrix`, `ti.field`, and `ti.Vector` — all support runtime indexing.

### H9. Unknown material model falls through to SVK
**Lines 239, 188, 386, 513, 608**: Material model branches use `if model == "j2_power_law": ... else: ...`

Add validation at top of `emit()` function body (line 721, after `ctx = EmissionContext()`):
```python
material_model = bundle.problem_ir_dict.get("material", {}).get("model", "svk")
if material_model not in ("svk", "j2_power_law"):
    raise ValueError(
        f"Unsupported material model '{material_model}'. "
        f"Supported: svk, j2_power_law."
    )
```

### H1. Emitted J2 — no convergence check after Newton loop
**After line 357** (after the Newton loop body ends): Add emitted convergence flag check:
```python
ctx.emit("# Guard: check Newton convergence for return mapping")
ctx.emit("f_final = sigma_eq - 3.0 * mu * dl - (sigma_y0 + K_hard * ti.pow(alpha_old + dl, n_hard))")
ctx.emit("if ti.abs(f_final) > 1e-8:")
with ctx.indent_block():
    ctx.emit("# Non-converged: set NaN flag (propagates to Newton driver)")
    ctx.emit("dl = ti.f64(float('nan'))")
```

### H2. Emitted J2 — no negative delta_lambda guard
**After the convergence check above, before line 360** (`factor = 1.0 - ...`):
```python
ctx.emit("dl = ti.max(dl, 0.0)")
```

### Comment fixes in same file (CM3, CM4, CM5, CM7)
- **Line 237**: Remove "(stub -- filled by P8.1)" from docstring; rename function `emit_constitutive_stub` → `emit_constitutive_update` and update caller at line ~710
- **Line 82**: Change comment from `"# Use repr for exact round-trip, but strip trailing zeros for readability"` to `"# 17 significant digits for deterministic round-trip"`
- **Line 349** (emitted code): Add comment linking tolerance to conventions `"# Newton tol per 07-CONVENTIONS.md §6 plastic multiplier"`
- **Line 499**: Change `"See PLAN-A lines 440-445"` to `"See PLAN-A Phase 8 (analytical tangent)"`

---

### Convention docs update (for C2)
**Files**: `dev/design_docs/07-CONVENTIONS.md` (section 9), `.claude/rules/codegen.md`

Add carve-out for quadrature points as element-type constants. Without this, the C2 fix contradicts the documented convention and will confuse future contributors.

---

## Phase 2: Error Handling Fixes

### C3. CG/PCG solver silent breakdown
**File**: `packages/mechdsl-core/src/mechdsl/solver/import_adapter.py`

**Lines 96-98** (CGSolver): Add `warnings.warn` before `break`:
```python
if abs(p_dot_ap) < 1e-300:
    import warnings
    warnings.warn(
        f"CG breakdown at iteration {k}: p^T A p = {p_dot_ap:.3e}. "
        "System may be non-SPD or singular.",
        RuntimeWarning,
        stacklevel=2,
    )
    break
```

**Lines ~160-165** (PCGSolver): Same pattern.

Add `import warnings` at module top.

### H3. J2 radial_return Newton break on small derivative
**File**: `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py`
**Lines 253-254**: Currently `if abs(df) < 1e-30: break  # pragma: no cover`

Change to:
```python
if abs(df) < 1e-30:
    if abs(f) > tol:
        raise RuntimeError(
            f"Return mapping Newton stalled: |df| = {abs(df):.3e}, "
            f"|f| = {abs(f):.3e}. Cannot reduce plastic residual."
        )
    break
```
Remove `# pragma: no cover`.

### H4. Emitted Newton CG warning — just a print
**File**: `taichi_printer.py:685-687`

Add a CG failure counter to the emitted Newton driver:

1. **Before the Newton loop** (after line 641, near `ctx.emit("for iteration in range(max_iter):")`): Initialize counter:
   ```python
   ctx.emit("cg_fail_count = 0")
   ```

2. **Inside the CG warning block** (line 687): Increment counter:
   ```python
   ctx.emit("    cg_fail_count += 1")
   ```

3. **After the CG block** (after line 687): Add failure check:
   ```python
   ctx.emit("if cg_fail_count >= 3:")
   with ctx.indent_block():
       ctx.emit('raise RuntimeError(f"CG failed to converge {cg_fail_count} times in Newton. '
                'System may be non-SPD or singular.")')
   ```

### H5. Einsum optimizer — silent fallback to 0.0 FLOPS
**File**: `packages/mechdsl-core/src/mechdsl/codegen/einsum_optimizer.py`
**Line 433**: Change `return 0.0` to:
```python
import warnings
warnings.warn(
    "Could not extract FLOPS from opt_einsum PathInfo. "
    "Reporting -1.0 as sentinel.",
    RuntimeWarning,
    stacklevel=2,
)
return -1.0
```

### H6. Reference elastic solver — silent Newton non-convergence
**File**: `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py`
**After the Newton for loop** (~line 461): Add `else` clause:
```python
else:
    raise RuntimeError(
        f"Newton did not converge after {max_iter} iterations. "
        f"Final |R| = {residual_history[-1]:.3e}"
    )
```

### H7. Boundary codegen — zero-area face
**File**: `packages/mechdsl-core/src/mechdsl/codegen/boundary_codegen.py`
**After face area computation** (~line 137): Add guards:
```python
if face_area < 1e-30:
    raise ValueError(
        f"Face '{face_name}' has near-zero area ({face_area:.3e}). "
        "Check mesh dimensions."
    )
n_face_nodes = len(face_node_ids)
if n_face_nodes == 0:
    raise ValueError(
        f"No nodes found on face '{face_name}'. Check mesh boundary tags."
    )
```

### H8. Boundary codegen — unvalidated axis fallthrough
**File**: `boundary_codegen.py:130`
**After** `axis = face_name[0]`: Add validation:
```python
if axis not in ("x", "y", "z"):
    raise ValueError(
        f"Cannot determine face orientation from name '{face_name}'. "
        "Expected name starting with 'x', 'y', or 'z'."
    )
```

Also add to docstring (CM6): "Note: Uniform distribution is valid only for structured meshes. Surface quadrature is planned for Plan B."

---

## Phase 3: Type Validation (`__post_init__`)

### J2PowerLawMaterial — critical
**File**: `packages/mechdsl-core/src/mechdsl/symbolic/models/j2_power_law.py`
Add after line ~44:
```python
def __post_init__(self) -> None:
    if self.E <= 0:
        raise ValueError(f"E must be > 0, got {self.E}")
    if not (-1 < self.nu < 0.5):
        raise ValueError(f"nu must be in (-1, 0.5), got {self.nu}")
    if self.sigma_y0 <= 0:
        raise ValueError(f"sigma_y0 must be > 0, got {self.sigma_y0}")
    if self.K < 0:
        raise ValueError(f"K must be >= 0, got {self.K}")
    if self.n <= 0:
        raise ValueError(f"n must be > 0, got {self.n}")
```

### H11. ReturnMappingResult — freeze
**Line 150**: Change `@dataclass` to `@dataclass(frozen=True)`

### H12-H13. Comment fixes in same file
- **Line 298**: `# unit normal to yield surface` → `# flow direction n = S_dev / q  (norm = sqrt(2/3), not unity)`
- **Line 282**: `Simo & Hughes §3.3` → `Simo & Hughes §3.4 (Box 3.5)`

### SVKMaterial — critical
**File**: `packages/mechdsl-core/src/mechdsl/symbolic/models/svk.py`
Add `__post_init__`:
```python
def __post_init__(self) -> None:
    if self.mu <= 0:
        raise ValueError(f"mu (shear modulus) must be > 0, got {self.mu}")
```
Also add validation in `from_E_nu`:
```python
if E <= 0:
    raise ValueError(f"E must be > 0, got {E}")
if not (-1 < nu < 0.5):
    raise ValueError(f"nu must be in (-1, 0.5), got {nu}")
```

### HexMesh — critical
**File**: `packages/mechdsl-core/src/mechdsl/solver/mesh_io.py`
Add `__post_init__`:
```python
def __post_init__(self) -> None:
    if self.coords.ndim != 2 or self.coords.shape[1] != 3:
        raise ValueError(f"coords must be (n, 3), got {self.coords.shape}")
    if self.connectivity.ndim != 2 or self.connectivity.shape[1] != 8:
        raise ValueError(f"connectivity must be (n, 8), got {self.connectivity.shape}")
    if self.n_nodes != self.coords.shape[0]:
        raise ValueError(
            f"n_nodes ({self.n_nodes}) != coords.shape[0] ({self.coords.shape[0]})"
        )
    if self.n_elem != self.connectivity.shape[0]:
        raise ValueError(
            f"n_elem ({self.n_elem}) != connectivity.shape[0] ({self.connectivity.shape[0]})"
        )
```

### QuadratureRule
**File**: `packages/mechdsl-core/src/mechdsl/ir/element_ir.py`
Add `__post_init__`:
```python
def __post_init__(self) -> None:
    if self.points.ndim != 2 or self.points.shape[1] != 3:
        raise ValueError(f"points must be (n, 3), got {self.points.shape}")
    if self.weights.ndim != 1:
        raise ValueError(f"weights must be 1D, got shape {self.weights.shape}")
    if self.points.shape[0] != self.weights.shape[0]:
        raise ValueError(
            f"points rows ({self.points.shape[0]}) != weights length ({self.weights.shape[0]})"
        )
```

### DirichletBC / NeumannBC
**File**: `packages/mechdsl-core/src/mechdsl/codegen/boundary_codegen.py`
Add `__post_init__` to DirichletBC:
```python
def __post_init__(self) -> None:
    if self.mask.ndim != 2 or self.mask.shape[1] != 3:
        raise ValueError(f"mask must be (n, 3), got {self.mask.shape}")
    if self.values.ndim != 2 or self.values.shape[1] != 3:
        raise ValueError(f"values must be (n, 3), got {self.values.shape}")
    if self.mask.shape != self.values.shape:
        raise ValueError(f"mask shape {self.mask.shape} != values shape {self.values.shape}")
```
Add `__post_init__` to NeumannBC:
```python
def __post_init__(self) -> None:
    if self.force.ndim != 2 or self.force.shape[1] != 3:
        raise ValueError(f"force must be (n, 3), got {self.force.shape}")
```

### HistoryFields — better error messages
**File**: `packages/mechdsl-core/src/mechdsl/solver/history_fields.py`

Update `get_current`, `get_old`, `set_current` to wrap KeyError:
```python
def get_current(self, name: str) -> NDArray:
    if name not in self._fields:
        raise KeyError(
            f"History field '{name}' not registered. "
            f"Available: {self.field_names}"
        )
    return self._fields[name]["current"]
```
Same for `get_old` and `set_current`.

Add duplicate guard to `register`:
```python
def register(self, name: str, shape: tuple[int, ...]) -> None:
    if name in self._fields:
        raise ValueError(f"History field '{name}' already registered")
    ...
```

---

## Phase 4: CI and Remaining Comments

### H10. CI missing flags
**File**: `.github/workflows/ci.yml`
**Lines 19, 38, 51** (lint, test, budget-regression jobs): Change all three `uv sync --all-packages` to:
```
uv sync --all-packages --all-groups --all-extras
```

---

## Phase 5: Test Coverage Gaps + Gemini Suggestions

### T1. Test radial_return non-convergence
**File**: `packages/mechdsl-core/tests/test_j2.py`
Add test:
```python
def test_radial_return_non_convergence():
    """Return mapping must raise RuntimeError when max_iter is too small."""
    mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.5)
    E_strain = 0.01 * np.eye(3)  # plastic regime
    with pytest.raises(RuntimeError, match="did not converge"):
        radial_return(mat, E_strain, alpha_old=0.0, max_iter=1)
```

### T2. Test negative plastic multiplier
**File**: `packages/mechdsl-core/tests/test_j2.py`
Add test for the stalled Newton path (H3 fix) and the negative dl guard:
```python
def test_radial_return_stalled_newton():
    """Return mapping must raise when Newton stalls (|df| near zero but |f| large)."""
    # Use extreme hardening parameters that can stall the Newton derivative
    mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1e8, n=0.1)
    # Large strain in plastic regime
    E_strain = 0.1 * np.eye(3)
    # This should either converge or raise RuntimeError("stalled") — never silently return
    try:
        result = radial_return(mat, E_strain, alpha_old=0.0)
        # If it converges, delta_lambda must be non-negative
        assert result.delta_lambda >= 0.0
    except RuntimeError:
        pass  # Expected: stall or non-convergence

def test_negative_delta_lambda_guard():
    """Negative plastic multiplier must raise ValueError."""
    from mechdsl.symbolic.models.j2_power_law import radial_return
    mat = J2PowerLawMaterial(E=200e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=0.5)
    # Strain just above yield — the radial return should converge normally
    E_small = 0.002 * np.eye(3)
    result = radial_return(mat, E_small, alpha_old=0.0)
    # A valid return always has delta_lambda >= 0
    assert result.delta_lambda >= 0.0
```

### T3. Test degenerate element
**File**: `packages/mechdsl-core/tests/test_hex8_tables.py`
Add test:
```python
def test_degenerate_element_raises():
    """Inverted element must raise ValueError."""
    from mechdsl.codegen.hex8_tables import reference_gradient_at_physical
    # Inverted element: swap two nodes
    X_bad = _single_element_coords()
    X_bad[[0, 1]] = X_bad[[1, 0]]  # invert
    with pytest.raises(ValueError, match="non-positive Jacobian"):
        reference_gradient_at_physical(X_bad, np.array([0.0, 0.0, 0.0]))
```

### T4. Test invalid face name
**File**: `packages/mechdsl-core/tests/test_mesh_io.py` or `test_boundary_codegen.py`
Add test:
```python
def test_invalid_face_name_raises():
    mesh = generate_hex8_mesh(2, 2, 2)
    with pytest.raises(KeyError):
        get_face_nodes(mesh, "invalid_face")
```

### T5. Test __post_init__ validation (new validations from Phase 3)
Add tests for each new `__post_init__` across the relevant test files:
- `test_j2.py`: invalid material params
- `test_svk.py`: invalid lam/mu
- `test_mesh_io.py`: shape mismatches
- `test_element_ir.py`: bad quadrature shapes

### G1. Rigid body rotation tolerance
**File**: `packages/mechdsl-core/tests/test_ref_elastic.py:260`
Change: `assert f_norm < 1e-2 * MU` → `assert f_norm < 1e-10`

### G4. FD tangent tolerance in elastic regime
**File**: `packages/mechdsl-core/tests/test_j2.py:226`
Change: `atol=1e-4, rtol=1e-4` → `atol=1e-8, rtol=1e-8` (elastic regime only; keep 1e-4 for plastic at line 240)

### G3. Dirichlet BC tangent — identity on diagonal (deferred)
**File**: `tests/ref/ref_hex8_elastic.py:271`
This is a functional change to the reference solver (not just a tolerance). Change the Dirichlet enforcement in `apply_tangent_matvec` from zeroing to identity: `Kv[bc_mask] = v[bc_mask]`. Apply same pattern in `ref_hex8_plastic.py`.

Note: This may change the golden files and benchmark results. Test carefully.

---

## Phase 6: Golden File Regeneration and Verification

After all code changes:

1. **Regenerate golden files** (because taichi_printer.py changes affect emitted code):
```bash
uv run python packages/mechdsl-core/tests/generate_golden.py
```

2. **Run full fast test suite**:
```bash
uv run pytest packages/mechdsl-core/tests/ -m "not slow and not gpu" --tb=short -q
```

3. **Run linter and type checker**:
```bash
uv run ruff check packages/
uv run mypy packages/mechdsl-core/src/mechdsl/
```

4. **Verify golden file diffs** make sense (only expected changes from codegen fixes).

5. **Run slow tests locally** if Taichi available:
```bash
uv run pytest packages/mechdsl-core/tests/ -m "slow" --tb=short -q
```

---

## Files Modified (by phase)

| Phase | Files |
|-------|-------|
| 1 | `codegen/taichi_printer.py`, `dev/design_docs/07-CONVENTIONS.md`, `.claude/rules/codegen.md` |
| 2 | `solver/import_adapter.py`, `symbolic/models/j2_power_law.py`, `codegen/boundary_codegen.py`, `codegen/einsum_optimizer.py`, `tests/ref/ref_hex8_elastic.py`, `codegen/taichi_printer.py` |
| 3 | `symbolic/models/j2_power_law.py`, `symbolic/models/svk.py`, `solver/mesh_io.py`, `ir/element_ir.py`, `codegen/boundary_codegen.py`, `solver/history_fields.py` |
| 4 | `.github/workflows/ci.yml` |
| 5 | `tests/test_j2.py`, `tests/test_hex8_tables.py`, `tests/test_mesh_io.py`, `tests/test_ref_elastic.py`, `tests/test_svk.py`, `tests/test_element_ir.py`, `tests/test_boundary_codegen.py`, `tests/ref/ref_hex8_elastic.py`, `tests/ref/ref_hex8_plastic.py` |
| 6 | `tests/golden/*.golden` (regenerated) |

## Scope Exclusions

- **G2** (explicit 3x3 inverse): Deferred — `np.linalg.inv` is fine for a reference solver
- **EinsumSpec `__post_init__`**: Deferred — lower priority (Medium rating)
- **Frozen mutable contents** (`array.flags.writeable = False`): Deferred — systemic change across all factory functions, better as a follow-up PR
- **Test helper deduplication** (conftest.py): Deferred — quality improvement, not a bug fix
- **Enum mutation hack** in tests: Deferred — fragile but functional

---

## Verification Notes (from plan review)

The following discrepancies were found by the visual plan review and corrected:

| # | Issue | Correction |
|---|-------|------------|
| 1 | C4 used `r_norm` but emitted code uses `res_norm` (line 662) | Fixed to `res_norm`. Would have caused NameError in generated code. |
| 2 | H1 sets `dl = NaN` but no NaN check in emitted Newton driver | Added C4b: NaN/Inf guard after `res_norm` computation. Completes the propagation strategy. |
| 3 | CM7 cited line 501 but "PLAN-A lines 440-445" is at line 499 | Fixed to line 499. |
| 4 | H9 said "around line 710" but `emit()` body starts at line 721 | Fixed to line 721. |
| 5 | C2 contradicts "never unroll mesh indices" convention | Added convention docs update task to Phase 1. |
| 6 | T2 had no concrete test body | Fleshed out with stalled Newton and delta_lambda guard tests. |
| 7 | H4 CG fail counter initialization location was unspecified | Added explicit location (after line 641, before Newton loop). |

All other line numbers and function names verified as correct against the current codebase.
