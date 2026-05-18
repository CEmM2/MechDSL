# Phase 3 Context Summary: compile_latex boundary-condition handoff docstring

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **Docstring style** follows the rest of `packages/mechdsl-core/src/mechdsl/__init__.py` (NumPy or Google style, whichever is in use).
- The docstring presence test lives in `packages/mechdsl-core/tests/test_compile_latex_docstring.py` and is marked `@pytest.mark.docs`.

## Key Principles

- **Docs-as-contract:** the docstring documents the BC handoff contract. Removing it is a regression detected by P3-2.
- **Sequence-after-Phase-1:** the contract being documented is the post-Phase-1 reality (façade may surface `f_ext_kernel`). Writing the docstring before Phase 1 lands risks describing a contract that never ships.

## Pre-resolved Design Decisions

- Docstring paragraph mentions: `BoundaryCondition`, current Dirichlet/Neumann support level, the caller's `f_ext` provisioning expectation, and that emitted `f_ext_kernel` (when present) overrides manual provisioning.
- Test asserts on substring presence rather than exact wording so minor copy-edits do not flake the test.

## Allowed Deviations

- None.

## Downstream Impact

- Establishes a regression guard for the BC handoff contract that any future façade refactor must respect.
