# Phase 5 Context Summary: Algo2code radial-return substitution

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **algpseudocode source** lives in `dev/algorithms/`. algo2code consumes algpseudocode environments.
- **JIT budget** (.claude/CLAUDE.md): ≤ 512 unrolled lines per `@ti.func`. Generated radial-return must stay under.
- **Feature flag:** `MECHDSL_USE_IMPORTED_RR=1` env var reverts to imported path. No recompilation needed.
- **Voigt ordering** for stress/strain in radial-return: tensorial Voigt unscaled shears `[xx, yy, zz, xy, xz, yz]` (07-CONVENTIONS).

## Key Principles

- **Reuse, don't rewrite:** consume `algo2code` Taichi backend (`packages/algo2code/src/algo2code/backends/taichi_codegen`). Do not re-implement codegen.
- **Parity over identity:** algo2code-generated path matches imported within tolerance derived from imported-path baseline; not absolute zero (plan line 267-268).
- **R2/R3 closed:** the substitution gate is open — R2/R3 deferral that originally blocked this work has cleared.

## Pre-resolved Design Decisions

- Power-law hardening included in algorithm (plan line 237-239).
- Three load-step parity cases: elastic, elastoplastic, unloading.
- Default solver path = algo2code generated; imported retained as fallback.
- Design-doc note lands in `06-PLASTICITY.md` or `07-CONVENTIONS.md` (P5-5 chooses based on existing structure).

## Allowed Deviations

- If algo2code lacks a construct needed for the algorithm (e.g. exponentiation for power-law), in-scope minor extension is allowed, or split into a sub-phase (plan line 261-263).

## Downstream Impact

- Imported radial-return becomes "fallback for incident response" only. After a stability soak, a future plan may delete the imported path entirely.
- Validates the algo2code → mechdsl-core consumption pattern for future algorithm substitutions (e.g. PCG variants, line search).
