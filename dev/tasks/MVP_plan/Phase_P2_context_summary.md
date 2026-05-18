# Phase 2 — Frontend Parsing (`% mechanics`): Context Summary

## Must Know

### Conventions
- **Index convention**: lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed `F_{iI}` = two-point. Ref: `07-CONVENTIONS.md §1`.
- **Contraction legality**: Spatial with material indices only valid through two-point tensors. Direct mixed contraction is illegal.
- **Directive syntax**: `% mechanics <keyword> <args>` — keywords: `dim`, `coord`, `material`, `formulation`, `cell`, `boundary`.

### Key Principles
- The parser (NRPyLaTeX fork) is an **external dependency** — changes happen in the fork, not in mechdsl-core.
- P2.5 is the **boundary adapter**: it normalizes fork output into a stable schema consumed by mechdsl-core.
- The parser context schema must be stable — changes cascade to Phase 4 (IR construction).

### Pre-resolved Design Decisions
- **NRPyLaTeX fork**: mechanics branch adds `MECHANICS_KWD` token and directive handlers.
- **Supported directives** (MVP): `dim 3`, `coord spatial/material`, `material hooke_power_law`, `formulation total_lagrangian`, `cell hex8`, `boundary dirichlet/neumann`.
- **Unsupported directives**: Must raise clear errors, not silently ignore.

## Should Know

### Downstream Impact
- P2.5's output schema is consumed by P4.1 (Mechanics IR construction). Schema changes require P4.1 updates.
- Index typing (P2.4) enforces contraction legality — this catches physics errors early in the pipeline.
- The fork must not break existing NRPyLaTeX parsing — run upstream tests after every change.
- Phase 2 blocks Phase 4 entirely. No IR work can start until the frontend adapter is stable.
