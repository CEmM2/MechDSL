# Phase 9 — MVP Integration, Regression, and Documentation: Context Summary

## Must Know

### Conventions
- **Benchmark tolerances** (from PLAN-A):
  - Patch test: relative error < 1e-12
  - Rigid body: force norm < 1e-12
  - Cantilever: within 5% of EB beam theory (coarse mesh)
  - Cook's membrane: tip displacement within 2% of de Souza Neto
  - Necking bar: load-displacement within 2% of Simo & Hughes (1998)
- **Test markers**: `@pytest.mark.slow` for Taichi compilation, `@pytest.mark.gpu` for GPU, `@pytest.mark.e2e` for end-to-end.

### Key Principles
- This is the **acceptance phase** — no new functionality, only verification and documentation.
- P9.1/P9.2/P9.3 are **parallel-safe** (different test scopes).
- The compiler-pass coverage closure (P9.4) is a traceability exercise, not a coding task.
- Documentation (P9.5) must be verified by walkthrough — instructions that don't work are worse than none.

### Pre-resolved Design Decisions
- **E2e test**: Single command runs LaTeX → parse → IR → lower → optimize → codegen → solve → check.
- **Equivalence test**: Generated solver output compared element-by-element against handwritten reference (P1.1/P1.2).
- **Benchmark suite**: 5 physical tests (patch, rigid body, cantilever, Cook's, necking bar).
- **Traceability**: Map compiler passes P/S/M/E/N/T/B/A/C to concrete test files.

## Should Know

### Downstream Impact
- This is the **final phase** — successful completion means MVP is done.
- MVP Definition of Done (from plan):
  1. End-to-end LaTeX-to-solution pipeline operational
  2. Generated solver matches handwritten reference within tolerances
  3. Physical benchmark suite (including necking bar) meets error bounds
  4. CI enforces lint/type/test/budget checks and remains green
- Documentation (P9.5) is the last task — it depends on everything else being complete.
- After MVP, the next milestone is PLAN-B (2D elements, updated Lagrangian, additional constitutive models).
