# Phase 2 Context Summary: Error Handling Fixes

## Must Know

### Files modified
- `solver/import_adapter.py` — CG/PCG breakdown warning (C3)
- `symbolic/models/j2_power_law.py` — radial_return stall guard (H3)
- `codegen/taichi_printer.py` — CG failure counter in emitted Newton driver (H4)
- `codegen/einsum_optimizer.py` — FLOPS extraction sentinel (H5)
- `tests/ref/ref_hex8_elastic.py` — Newton non-convergence raise (H6)
- `codegen/boundary_codegen.py` — face area/axis guards (H7+H8)

### Conventions
- **Error handling pattern**: Use `warnings.warn(..., RuntimeWarning, stacklevel=2)` for non-fatal conditions (CG breakdown, FLOPS extraction failure). Use `raise RuntimeError/ValueError` for fatal conditions (Newton non-convergence, zero-area face).
- **Reference solver consistency**: Both ref_hex8_elastic.py and ref_hex8_plastic.py must use the same `for...else` pattern for Newton non-convergence.
- **FLOPS sentinel**: Use `-1.0` (not `0.0`) as the sentinel for extraction failure. Any downstream code comparing `flops >= 0` must handle this.

### Key principles
- The `for...else` pattern in Python: the `else` clause runs only if the loop completes without `break`. This is the correct pattern for Newton convergence checks.
- The H3 fix (j2_power_law.py:253) changes a `break` that currently bypasses the `for...else` RuntimeError. After the fix, a stalled Newton with large residual raises immediately rather than returning silently.

### Pre-resolved design decisions
- **C3**: Use `warnings.warn` rather than `raise` for CG breakdown. Rationale: the caller (Newton driver) should decide whether to abort or retry with a different preconditioner. A warning gives visibility without forcing a specific error policy.
- **H4**: CG failure counter threshold is 3. After 3 consecutive CG failures, the emitted Newton driver raises. This balances between tolerating transient CG issues and preventing silent divergence.
- **H5**: `-1.0` sentinel rather than `None` or raising. Rationale: the FLOPS count is informational, not correctness-critical. Budget decisions use `estimated_lines`, not FLOPS.

## Should Know

### Downstream impact
- R3.2.2 (H3) enables test T1 and T2 in Phase 5 — the stall path is now testable.
- R3.2.5 (H6) changes ref_hex8_elastic.py behavior — if existing tests have non-convergent edge cases, they will now raise instead of silently returning.
- R3.2.6 (H7+H8) enables test T4 in Phase 5 — the invalid face name path now has a descriptive error.
- R3.2.3 (H4) modifies taichi_printer.py — coordinate with Phase 1 changes to avoid conflicts.
