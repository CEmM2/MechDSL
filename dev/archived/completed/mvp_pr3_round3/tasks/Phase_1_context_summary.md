# Phase 1 Context Summary: Critical Taichi Codegen Fixes

## Must Know

### Primary file
`packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` (733 lines) — all 10 tasks modify this file or its convention docs.

### Conventions
- **Index partitioning** (07-CONVENTIONS.md §9): physics indices (range <= 6) → `ti.static`; mesh indices (nodes, quads, elements) → runtime. **Exception being added**: quadrature points with element-type-constant count (N_QP=8) may be `ti.static` when the loop body accesses Python list constants.
- **JIT budget**: 512 lines per `@ti.func`, 2000 per `@ti.kernel`, 5000 ceiling.
- **Emitted variable names**: The Newton driver uses `res_norm` (line 662), NOT `r_norm`. Getting this wrong causes NameError in generated code.
- **NaN propagation strategy**: H1 sets `dl = NaN` → propagates through stress → internal force → residual → `res_norm` → C4b catches with `np.isfinite()`. This chain must be complete.

### Key principles
- Generated code must be at least as safe as the handwritten reference solvers.
- `break` inside `ti.static(range(...))` does not work in Taichi — use plain `range()` for algorithmic iteration loops.
- Python lists cannot be indexed with runtime Taichi variables inside kernels — only `ti.static` loop variables can index Python lists.
- `ti.Matrix`, `ti.field`, and `ti.Vector` support runtime indexing.

### Pre-resolved design decisions
- **C2 design choice**: Make quad loop `ti.static` rather than restructuring GRAD_AT_QUAD to `ti.field`. Rationale: N_QP=8 is element-type constant, ~240 unrolled lines fits within budget, and restructuring to `ti.field` is a larger change with more risk.
- **C5 + C2 interaction**: The GRAD_AT_QUAD inner gather loop at line 429 MUST stay `ti.static(range(N_NODES))` because all three indices (q, a, d) must be compile-time for Python list access. The other three node loops at 416, 446, 476 can safely become runtime.
- **H1 NaN strategy**: Chosen over a convergence flag because Taichi `@ti.func` cannot return error codes alongside stress tensors. NaN naturally propagates through IEEE 754 arithmetic.

### Allowed deviation from specs
- **C2**: Quadrature loop changed to `ti.static` even though 07-CONVENTIONS.md classifies quad points as mesh indices. The convention docs will be updated (R3.1.10) to reflect this exception.

## Should Know

### Downstream impact
- **ALL golden files will be invalidated** by Phase 1 changes. Phase 6 (R3.6.1) regenerates them. Do NOT run golden file tests until Phase 6.
- The `emit_constitutive_stub` → `emit_constitutive_update` rename (CM3) requires updating the caller at line ~728 in the `emit()` function. Grep for `emit_constitutive_stub` to find all references.
- Phase 2 task R3.2.3 also modifies taichi_printer.py (CG failure counter). Coordinate to avoid merge conflicts.

### Task ordering within Phase 1
- R3.1.2 (C2) must complete before R3.1.5 (C5) — C5 depends on C2's quad loop being ti.static.
- R3.1.7 (H1) must complete before R3.1.8 (H2) — H2 adds dl clamp after H1's convergence check.
- R3.1.8 (H2) must complete before R3.1.4 (C4b) — C4b adds the NaN guard that catches H1's NaN flag.
- R3.1.10 (convention docs) should complete after R3.1.2 (C2) — it documents the C2 decision.
