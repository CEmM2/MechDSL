# Phase 2 Context Summary — Einsum String Extraction

## Conventions

- **Index convention**: `q` = quadrature point, `a,b` = node indices, `i,j` = spatial indices, `I,J,K,L` = material indices
- **Einsum notation**: Einstein summation strings consumed by opt_einsum
- **Physics indices** (range ≤ 6) → `ti.static` unrolling; **mesh indices** (range > 6) → runtime loops
- Per `.claude/rules/ir.md`: "einsum_extract.py extracts einsum strings from ElementIR for the optimiser. This is deterministic and runs once."
- Lowering step MUST NOT introduce approximations — lossless transformation

## Key Principles

- The extraction logic already exists as `_extract_hex8_tl_einsums()` in `fe_localise.py` (lines ~102-201). This phase **moves** it to its canonical location (`einsum_extract.py`), not reimplements it.
- The `EinsumSpec` dataclass stays in `fe_localise.py`. The new function imports it.
- The function signature changes from `_extract_hex8_tl_einsums(n_qp, n_nodes, dim)` to `extract_einsum_specs(element_ir: ElementIR)` — it reads dimensions from the ElementIR.
- Must validate element type: only `"hex8"` supported. Raise `LocalisationError` for unsupported types.
- Three einsum specs extracted for Hex8 TL: `strain_displacement`, `internal_force`, `tangent_matvec`

## Pre-resolved Design Decisions

- `extract_einsum_specs` returns `dict[str, EinsumSpec]` keyed by operation name (not a tuple)
- `fe_localise.localise()` delegates to `extract_einsum_specs` and converts `dict.values()` to tuple for backward compatibility
- The `_extract_hex8_tl_einsums()` private function is removed from `fe_localise.py` after the move
- `extract_einsum_specs` is exported from `mechdsl.lowering`

## Downstream Impact

- Phase 4 (`compile()`) transitively uses `extract_einsum_specs` via `localise_and_optimize()` — P4-T1 is blocked by P2-T2
- All existing tests that call `localise()` or `localise_and_optimize()` must pass unchanged (same numerical output)
- The einsum strings MUST match the existing hardcoded values — this is a regression guard (sprint plan §2.4)

## Key Files

| File | Current state | Action |
|------|--------------|--------|
| `src/mechdsl/lowering/einsum_extract.py` | 1-line stub | → ~120 lines (moved from fe_localise) |
| `src/mechdsl/lowering/fe_localise.py` | 263 lines | Remove ~100 lines, add import + delegation |
| `src/mechdsl/lowering/__init__.py` | Exports localise, localise_and_optimize | Add extract_einsum_specs |
| `tests/test_einsum_extract.py` | Does not exist | New test file |

## Existing Einsum Specs (for regression guard)

From `_extract_hex8_tl_einsums(n_qp=8, n_nodes=8, dim=3)`:
- `strain_displacement`: `"qaI,ai->qiI"` — displacement gradient at QP
- `internal_force`: `"qaI,qiI->qai"` — B^T @ stress integration
- `tangent_matvec`: `"qaI,qiIjJ,qbJ->qaibj"` — tangent stiffness
