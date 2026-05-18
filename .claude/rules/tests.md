---
paths:
  - "packages/*/tests/**"
---

# Testing Rules

## Markers

- `@pytest.mark.slow` — anything involving Taichi JIT compilation (seconds-long).
- `@pytest.mark.gpu` — requires a GPU to run.
- `@pytest.mark.e2e` — end-to-end pipeline tests (LaTeX source → generated solver → verification).
- `@pytest.mark.docs` — documentation-anchor / doc-tier tests (pin externally observable behaviour and contracts).
- Fast tests (no markers) should be the majority. Target < 1 second per test.

## Golden-file regression

- Artifact bundles are serialised and stored in `tests/golden/`.
- Tests compare current output against stored golden files.
- If a golden file changes, the diff must be visible in test output.
- Golden-file updates require explicit intent — never auto-update.

## Reference kernels

- Handwritten reference kernels in `tests/ref/` are the ground truth.
- `ref_hex8_elastic.py` and `ref_hex8_plastic.py` are the MVP baselines.
- Generated code must match reference output to within numerical tolerance (see 07-CONVENTIONS.md §6).

## Verification tolerances (from spec)

- Generated vs reference displacement: max diff < 1e-10.
- Patch test (constant strain): exact reproduction.
- Cook's membrane: within 2% of literature values.
- Necking bar: load-displacement curve within 2% of Simo & Hughes (1998).

## Conventions

- Use `conftest.py` fixtures for common paths (`golden_dir`, `ref_dir`).
- Parametrise tests over element types / material models where possible.
- Keep test data minimal — small meshes, few load steps.
