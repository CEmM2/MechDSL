# Phase 5 — Contraction Planning & Budgets: Context Summary

## Must Know

### Conventions
- **JIT budget limits** (hard rules from `07-CONVENTIONS.md §9`):
  - Max 512 unrolled lines per `@ti.func`
  - Max 2000 total unrolled lines per `@ti.kernel`
  - Absolute ceiling: 5000 unrolled lines
- **Index partitioning**: Physics indices (range ≤ 6) → `ti.static`; mesh indices → runtime loops. Never unroll mesh indices.
- **Tier classification**: Tier 1 = library `@ti.func`, Tier 2 = generated `@ti.func`, Tier 3 = fallback.

### Key Principles
- The einsum optimizer is a **safety gate**: it must prevent over-budget code from being emitted.
- Budget counting runs on every contraction before code emission — this is mandatory, not optional.
- If a contraction exceeds budget, the optimizer must restructure or fall back to Tier 3.
- opt_einsum handles contraction path optimization; the budget counter validates the result.

### Pre-resolved Design Decisions
- **opt_einsum** is the contraction path optimizer (already a dependency in mechdsl-core).
- **Budget regression CI**: A dedicated test (P5.3) fails CI when MVP contractions exceed budget limits.
- **Integration point**: Contraction plans are attached to the artifact bundle (P4.4) during lowering.

## Should Know

### Downstream Impact
- P5.1 feeds P5.2 (integration) and P5.3 (CI tests).
- P5.2 feeds P6.2 (Taichi printer needs contraction plans to emit optimized code).
- The budget regression test (P5.3) runs in every PR — it catches budget violations early.
- Budget thresholds may need tuning as plasticity (Phase 8) adds more contractions.
