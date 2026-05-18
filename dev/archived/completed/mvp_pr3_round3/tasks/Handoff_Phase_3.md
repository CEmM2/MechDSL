# Phase 3 Handoff — Type Validation (`__post_init__`)

## Phase 2 Completion Summary

**All 6 Phase 2 tasks completed and verified.**

### Changes Made

- **R3.2.1** (`import_adapter.py`): Added `warnings.warn` on CG/PCG breakdown with iteration count and `p_dot_ap` value. Added `import warnings`.
- **R3.2.2** (`j2_power_law.py`): Fixed stall guard — stalled Newton with large residual now raises RuntimeError instead of silently breaking. Removed `# pragma: no cover`.
- **R3.2.3** (`taichi_printer.py`): Added emitted `cg_fail_count` variable: init before loop, increment on CG failure, raise RuntimeError after 3 failures.
- **R3.2.4** (`einsum_optimizer.py`): Changed FLOPS extraction fallback from `return 0.0` to `warnings.warn` + `return -1.0`. Added `import warnings`.
- **R3.2.5** (`ref_hex8_elastic.py`): Added `for...else` on Newton loop — raises RuntimeError on non-convergence, matching `ref_hex8_plastic.py` pattern.
- **R3.2.6** (`boundary_codegen.py`): Added axis validation (`x/y/z`), zero-area face guard, empty face nodes guard, and structured-mesh-only note in docstring.

### Golden files regenerated
Golden `.py.golden` files regenerated after R3.2.3 changes to emitter.

### Verification Evidence
- 652 passed, 15 skipped (Phase 2 stubs), 0 failed
- All Phase 2 target test files: 187/187 passed

### Known State for Phase 3
- `j2_power_law.py` was modified in Phase 2 (H3 stall guard) and will be modified again in Phase 3 (R3.3.1 `__post_init__`, R3.3.2 freeze + comments).
- `boundary_codegen.py` was modified in Phase 2 (guards) and will be modified again in Phase 3 (R3.3.6 `__post_init__` on DirichletBC/NeumannBC).
- All other Phase 3 targets are untouched: `svk.py`, `mesh_io.py`, `element_ir.py`, `history_fields.py`.
