# Phase 6 — Taichi Code Generation (Elastic Path): Context Summary

## Must Know

### Conventions
- **Precision**: `ti.f64` everywhere. `ti.init(default_fp=ti.f64)`. Ref: `07-CONVENTIONS.md §10`.
- **JIT budget**: 512/@ti.func, 2000/@ti.kernel, 5000 absolute. Ref: `07-CONVENTIONS.md §9`.
- **Index partitioning**: Physics indices → `ti.static`, mesh indices → runtime loops. Ref: `07-CONVENTIONS.md §9`.
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` unscaled shears in emitted code.
- **Jacobian guard**: `J > 1e-15` runtime check. Ref: `07-CONVENTIONS.md §6`.

### Key Principles
- The Taichi printer is **deterministic**: same input must produce identical output (for golden comparisons).
- Code generation must respect IR discipline: printer reads from artifact bundle (ProblemIR + ElementIR + ContractionPlan), never from symbolic expressions directly.
- P6.3/P6.4/P6.5 are **parallel-safe** (separate template files), but all depend on P6.2 (printer core).
- Emitted constitutive functions (P6.3) must match the symbolic oracle (P3.5) numerically.

### Pre-resolved Design Decisions
- **Hex8 tables** (P6.1): Static constants for shape functions and quadrature — shared by all Hex8 kernels.
- **Template-based emission**: Using Jinja2 templates (.py.j2) or equivalent for code generation.
- **CSE applied**: Common subexpression elimination reduces redundant computation in emitted code.
- **Patch test is the acceptance gate**: The internal force kernel (P6.4) must pass single-element patch test against reference (P1.1).

## Should Know

### Downstream Impact
- P6.4 (internal force) and P6.5 (tangent matvec) feed P7.1 (Newton driver) — the NR loop needs both.
- P6.3 (elastic constitutive) feeds P6.4 and is also the comparison target for P9.2 (equivalence tests).
- P6.2 (printer core) is reused by P8.1/P8.2 (plastic constitutive emission) — the emission infrastructure must be extensible.
- Phase 6 is the first time generated code is **executed** — debugging generated Taichi code is harder than debugging handwritten code.
