---
name: verify-numerics
description: Run MechDSL numerical verification against analytical values, golden baselines, or handwritten reference solvers. Use after changing element kernels, constitutive models, or solver behavior.
---

# Verify Numerics

This skill is diagnostic and read-only.

Read `dev/design_docs/07-CONVENTIONS.md` and `dev/design_docs/08-VERIFICATION.md` before running checks.

## Workflow

1. Identify what needs verification from `$ARGUMENTS`.
2. Read the relevant test files, reference kernels, and baseline artifacts.
3. Run the appropriate pytest targets with `uv run pytest`.
4. When needed, compare generated output against the handwritten reference implementations in `packages/mechdsl-core/tests/ref/`.
5. Report:
   - pass or fail by check
   - absolute and relative error magnitudes
   - convergence behavior
   - likely origin of any discrepancy

## Tolerances

- displacement max diff < `1e-10`
- `J > 1e-15`
- Newton convergence `||R|| < 1e-8 * ||R_0||`
- CG convergence `||r|| < 1e-10 * ||r_0||`

