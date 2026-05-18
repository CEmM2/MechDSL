# Phase 2 Context Summary: Full convected coordinate framework

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B2 Full convected coordinate framework

## Conventions

- Convected indices follow the NRPyLaTeX convention: `gDD` for covariant metric, `gUU` for contravariant, `gammaUDD` for Christoffel symbols with upper-lower-lower index positions.
- The reference metric is `G_{IJ}(θ)` (capital G, material indices). The current metric is `g_{IJ}(θ,t) = F^T G F` — note this is *still* indexed by convected material coordinates even though its values depend on the deformation.
- Raise / lower indices with the metric that matches the point's configuration: material index → reference metric, spatial index → current metric.

## Key Principles

- **Cartesian fast path is mandatory.** When `G_{IJ} = δ_{IJ}`, every new code path must either short-circuit to the Cartesian implementation or produce bit-identical output. Never silently invoke SymPy simplification on the Cartesian case.
- **Symbolic metric inversion is expensive.** Cache `g^{IJ}` after the first computation and invalidate only when the metric changes. Never re-derive inside a Newton iteration.
- **Christoffel symbols vanish for Cartesian G.** This is a regression guard: if Christoffels are non-zero on a Cartesian mesh, something in the metric pipeline is broken.
- **Covariant derivatives reduce to partials on Cartesian.** Another sanity invariant that every test must uphold.
- **NRPyLaTeX is the math parser** for user-defined metrics. MVP Plan A uses a bespoke line-based parser for `% mechanics` directives — Phase 2 does NOT change that. NRPyLaTeX is consulted only for the right-hand side of `% mechanics assign gDD = <sympy_expression>`.

## Pre-resolved Design Decisions

- User supplies the reference metric `G_{IJ}(θ)` as a SymPy expression via the `% mechanics assign GDD --metric_reference` directive. The parser stashes the string; the symbolic layer evaluates it.
- The current metric `g_{IJ}` is derived automatically from `G` and the deformation gradient — users do not assign it directly. (The `--metric_current` directive exists for completeness but is rarely used.)
- Christoffel symbols are computed once per simulation (not per Newton step) because the reference metric is time-invariant in the Lagrangian framework.
- Curvilinear patch test uses a quarter-annulus in cylindrical coordinates — the simplest non-trivial curvilinear geometry.

## Allowed Deviations

- For the MVP curvilinear patch test, numerical metric inversion is acceptable even if the symbolic inverse would be cleaner. The symbolic path is a nice-to-have, not a requirement.

## Downstream Impact

- **Phase 10 P10-1 (MMS convergence)** uses the curvilinear patch test as one of the MMS reference solutions.
- Phases 3-8 do **not** depend on Phase 2 — they run in parallel on Cartesian meshes and will keep working because of the Cartesian fast path.
- Phase 2's metric field abstraction is the foundation for any future anisotropic-material extension that needs a per-element reference orientation.
