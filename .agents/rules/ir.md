---
paths:
  - "packages/mechdsl-core/src/mechdsl/ir/**"
  - "packages/mechdsl-core/src/mechdsl/lowering/**"
---

# IR and Lowering Rules

## IR immutability

- `ProblemIR` and `ElementIR` are immutable dataclasses.
- Validation happens at construction time in `__post_init__`.
- IR objects must stay serializable to JSON or YAML for artifact bundles.

## Supported-subset validation

Unsupported constructs must be rejected explicitly. Every rejection should identify:

1. The unsupported construct
2. The LaTeX source line when available
3. The plan phase that adds support

See `dev/design_docs/00-OVERVIEW.md` for the supported-subset contract.

## Lowering expectations

- `fe_localise.py` chooses the element type, basis functions, quadrature, and quadrature-point constitutive work.
- `einsum_extract.py` deterministically extracts einsum strings from `ElementIR`.
- Lowering must be lossless. Do not introduce approximations between Mechanics IR and Element IR.

## Error classes

- `UnsupportedError` for unsupported constructs
- `BoundaryRegionError` for undeclared boundary regions
- `LocalisationError` for element or dimension incompatibilities

