# Phase 5 Context Summary: Documentation & Examples

**Plan:** `dev/plans/sprint3.md`
**Original plan phase name:** Phase 5

## Conventions
- Numpy-style docstrings for all public API functions
- Example scripts use build_context() -> ProblemIR -> compile() pattern
- CHANGELOG follows Keep a Changelog format

## Key Principles
- Documentation is an MVP exit criterion, not optional polish
- Examples must be self-contained and runnable with uv run python
- UnsupportedError messages must reference correct Plan B phase for user guidance

## Pre-resolved Design Decisions
- 5 example scripts: elastic_cantilever.py, plastic_uniaxial.py, cook_membrane.py, necking_bar.py, patch_test.py
- README covers installation (uv sync), quickstart, architecture overview
- CHANGELOG entry for [0.1.0] or [Unreleased]

## Allowed Deviations
- None

## Downstream Impact
- Documentation enables external users and contributors
- Examples serve as integration smoke tests
