---
paths:
  - "packages/*/tests/**"
---

# Testing Rules

## Markers

- `pytest.mark.slow`: Taichi JIT or other seconds-long tests
- `pytest.mark.gpu`: GPU-required tests
- `pytest.mark.e2e`: end-to-end pipeline tests
- Fast tests should remain the majority and stay short.

## Golden-file regression

- Artifact bundles live in `tests/golden/`.
- Golden diffs must remain visible in test output.
- Golden updates require explicit intent; never auto-update them silently.

## Reference kernels

- Handwritten reference kernels in `tests/ref/` are the baseline.
- Generated code should match reference output within the project tolerances.

## Verification tolerances

- Generated vs reference displacement: max diff < `1e-10`
- Patch test: exact reproduction of constant strain
- Cook's membrane: within 2 percent of literature values
- Necking bar: within 2 percent of Simo and Hughes (1998)

## Conventions

- Prefer `conftest.py` fixtures for shared paths and data.
- Parametrize over element types and material models where possible.
- Keep meshes and load cases minimal unless the test is explicitly benchmarking or end-to-end.

