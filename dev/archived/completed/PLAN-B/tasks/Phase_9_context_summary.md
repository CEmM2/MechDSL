# Phase 9 Context Summary: Contraction template tuning

**Plan:** `dev/design_docs/PLAN-B.md`
**Original plan phase name:** B8b Contraction template tuning

## Conventions

- **Tier vs family separation:** a contraction's *tier* (1/2/3) is the scheduling decision (how it fits in the JIT budget). Its *family* is the realisation decision (what shape the emitted code takes per backend). These are orthogonal and must not be merged.
- Family identifiers use `UPPER_SNAKE_CASE` enum values (e.g. `MATERIAL_TANGENT_CONTRACTION`, `GEOMETRIC_STIFFNESS`, `PUSH_FORWARD_TO_SPATIAL`).
- Per-backend emitters live at `mechdsl.codegen.<backend>_printer.family_emitters: dict[Family, EmitterFunc]`.

## Key Principles

- **One family per contraction, one emitter per (family × backend).** No ad hoc branching inside the printer body; every shape choice is a table lookup.
- **The refactor must not change semantics.** Emitted Taichi source may differ in whitespace or helper-function structure but must produce identical numerical results. Golden files and cross-backend equivalence tests are the regression guards.
- **Feature-flag the refactor.** Keep the old tier-only emission path reachable via a config flag during the rollout. After Phase 9 stabilises, the old path can be removed.
- **Budget regression is non-negotiable.** Adding a template layer must not push any existing contraction over budget. If it does, the template is wrong, not the budget.
- **Performance is not a regression.** Family emission must be within 1.2× of tier-only wall-clock emission time. Families that make emission slower are rejected.

## Pre-resolved Design Decisions

- Phase 9 blocks on Phase 5 (multiple elements) AND Phase 8 (multiple backends) — per the plan's explicit note at lines 244-247. Without both, there's not enough variety to motivate families.
- The spec document lives in `09-EINSUM-OPTIMISER.md §9` (section to extend, not a new file).
- Refactor scope: the three backend printers (Taichi, MFEM, MOOSE) and the einsum optimiser. No IR changes.

## Allowed Deviations

- The initial family taxonomy only needs to cover contractions that currently exist in the codebase. Forward-looking families for hypothetical future backends are over-engineering.

## Downstream Impact

- **P10-1 MMS convergence matrix** depends on Phase 9's budget regression because MMS runs the full element × material matrix and any budget violation would block it.
- No Phase beyond 10 depends on Phase 9. This is the last architectural change in Plan B.
