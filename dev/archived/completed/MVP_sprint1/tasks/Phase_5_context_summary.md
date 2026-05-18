# Phase 5 Context Summary — TaichiPrinter Upgrades

## Conventions

- Emitted code must be a self-contained `.py` file (per `.claude/rules/codegen.md`)
- Deterministic emission: same bundle → identical source string
- `ti.f64` throughout emitted code
- Physics indices → `ti.static` in emitted code; mesh indices → runtime loops
- Per `.claude/rules/codegen.md`: "Always emit artifact bundles alongside generated code"
- Golden-file updates require explicit intent — never auto-update

## Key Principles

- The TaichiPrinter already emits 95% of the solver (~775 lines). This phase adds the remaining pieces to make the generated file runnable standalone.
- `emit_newton_driver_stub` is already a complete Newton driver (not a stub). Rename to `emit_newton_driver` for semantic clarity.
- New emitters are additive — existing emission code is not modified.
- Golden files WILL change because the emitted output now includes postprocess function and main block.
- Before regenerating golden files, verify the diff is **additive only** (new content appended after existing code).

## Pre-resolved Design Decisions

- `emit_postprocess(ctx, bundle)`: emits `save_results()` function that saves displacement as `.npz`. Optional meshio VTK behind `try/except ImportError`.
- `emit_main(ctx, bundle)`: emits `if __name__ == '__main__':` block with mesh loading, field allocation, material params, newton_solve call, convergence summary, save_results call.
- Emission order in `emit()`: preamble → constants → fields → constitutive → internal_force → tangent_matvec → newton_driver → postprocess → main
- Mesh loading uses numpy `.npz` format (no external deps required in generated code beyond numpy + taichi)

## Downstream Impact

- Phase 6 (E2E) depends on these emitters — the generated code must be executable standalone
- Golden file regeneration here will affect any test that does exact-match comparison against golden files
- `compile()` from Phase 4 will produce different output after this phase

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `src/mechdsl/codegen/taichi_printer.py` | 775 lines | Rename stub, add ~90 lines (postprocess + main) |
| `tests/golden/generated_elastic.py.golden` | 15,420 bytes | Regenerate |
| `tests/golden/generated_plastic.py.golden` | 18,240 bytes | Regenerate |
| `tests/test_taichi_printer.py` | 434 lines | Add 2+ new tests |
| `tests/generate_golden.py` | Golden file generator | Use for regeneration |

## Existing emit() chain (lines 738-774)

```python
emit_preamble(ctx, bundle)
emit_constants(ctx, bundle)
emit_field_declarations(ctx, bundle)
emit_constitutive_update(ctx, bundle)
emit_internal_force_kernel(ctx, bundle)
emit_tangent_matvec_kernel(ctx, bundle)
emit_newton_driver_stub(ctx, bundle)  # rename to emit_newton_driver
# ADD: emit_postprocess(ctx, bundle)
# ADD: emit_main(ctx, bundle)
```
