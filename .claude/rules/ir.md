---
paths:
  - "packages/mechdsl-core/src/mechdsl/ir/**"
  - "packages/mechdsl-core/src/mechdsl/lowering/**"
---

# IR and Lowering Rules

## IR immutability

- `ProblemIR` and `ElementIR` are immutable dataclasses (use `@dataclass(frozen=True)` or equivalent).
- All validation runs at construction time in `__post_init__`.
- IRs are serialisable to JSON/YAML for artifact bundles.

## Supported-subset validation

- The compiler explicitly **rejects** unsupported constructs rather than silently approximating.
- Every rejection error must include:
  1. The unsupported construct.
  2. The LaTeX source line that triggered it (when available).
  3. A pointer to the plan phase that adds support (e.g. "Updated Lagrangian is planned for Plan B phase B1").
- See `dev/design_docs/00-OVERVIEW.md §8` for the full supported-subset contract.

## Lowering

- `fe_localise.py` must select element type, instantiate basis functions and quadrature, and map constitutive evaluation to quadrature-point operations.
- `einsum_extract.py` extracts einsum strings from ElementIR for the optimiser. This is deterministic and runs once.
- The lowering step must never introduce approximations — it is a lossless transformation from ProblemIR to ElementIR.

## Error classes

- `UnsupportedError` for constructs outside the supported subset.
- `BoundaryRegionError` for BC references to undeclared regions.
- `LocalisationError` for element/dimension incompatibilities.
