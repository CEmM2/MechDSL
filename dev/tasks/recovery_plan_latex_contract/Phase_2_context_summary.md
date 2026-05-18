# Phase 2 Context Summary: Restore the frontend as the canonical entry point (R1)

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Original plan phase name:** Restore the frontend as the canonical entry point (R1)

## Goal
Re-establish LaTeX input as the primary public contract.

## Why this phase
This is the highest-leverage correction. The architecture cannot be “LaTeX-driven” if the practical front door is Python object construction.

## Code reality anchor (2026-04-26)
- `mechdsl/__init__.py:7` exports only `compile` (re-exported from `codegen`); `frontend/__init__.py` exports `build_context`, `parse`, `parse_file` but no LaTeX façade.
- `frontend/parser.py:11-17` explicitly defers nrpylatex math grammar to "Plan B"; `tests/test_frontend.py` is a stub. `nrpylatex` is wired in `pyproject.toml` but never imported under `src/`.
- The mismatch this phase corrects: no canonical `compile_latex(...)` entrypoint exists, so the LaTeX-first contract has no public surface to call.

## Required constraints
- Do **not** remove `build_context()`.
- Do **not** make the first step a large frontend rewrite.
- Do **not** block recovery on full parser completeness; a thin but canonical stable subset is sufficient at first.

## Cross-phase dependencies
This phase blocks: P3-1, P3-2, P5-4, P7-2.
This phase is blocked by: — (no upstream dependencies; Phase 1 docs are advisory).

## Exit criteria
- LaTeX input is the documented primary entry point.
- A minimal stable compiler path begins at LaTeX source.
- Frontend task ownership is no longer split across contradictory planning artifacts.

## Tasks in this phase
- **P2-1** (R1.1, tier=unit): Introduce a canonical façade, e.g. `compile_latex(source: str, profile: str = "mvp")`.
- **P2-2** (R1.2, tier=unit): Preserve `build_context()` as a convenience/testing API, but document it as secondary.
- **P2-3** (R1.3, tier=unit): Define the frontend split explicitly: NRPyLaTeX fork/integration = parser of record; local code = adapter/normalizer/validator.
- **P2-4** (R1.4, tier=docs): Reconcile or replace the old Phase 2 tasks (`P2.1`–`P2.5`) with the actual recovery tasks.
- **P2-5** (R1.5, tier=integration): Add a minimal frontend contract test suite that begins from LaTeX source.
- **P2-6** (R1.6, tier=integration): Ensure frontend failures produce contract-level errors (unsupported syntax, missing directives, invalid tensor/index semantics).
