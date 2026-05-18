# Phase 2 Context Summary: TL/UL J2 Benchmark Solver Layer

**Plan:** `dev/plans/ph10_preq.md`
**Original plan phase name:** E4 TL/UL J2 Benchmark Solver Layer

## Must Know

- This phase is internal solver enablement only; Cook and necking public APIs are intentionally left unchanged until Phase 3.
- Use existing J2 return-mapping behavior as the material contract.
- Do not change J2 constitutive semantics, Johnson-Cook behavior, or Taylor impact code.
- Validate TL against the existing plastic reference before adding UL and Tet10 coverage.

## Should Know

- Required checks include history updates, TL reference agreement, UL objectivity, monotonic plastic work, and stable Tet10 history updates.
- The solver should stay benchmark-local and additive under `mechdsl.verify.*`.

## Allowed Deviations

- None. Any proposed constitutive change requires fresh GitNexus impact and a gate-history blocker entry.

## Downstream Impact

- Completion unlocks Cook original matrix closure and necking UL closure.

