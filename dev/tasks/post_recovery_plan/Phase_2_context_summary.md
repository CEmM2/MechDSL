# Phase 2 Context Summary: Test marker tier reconciliation (`docs`)

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **Pytest markers** are declared in `[tool.pytest.ini_options].markers` in pyproject.toml (root or per-package). The `.claude/rules/tests.md` file mirrors the registered tier set.
- **Tier set:** today `slow`, `gpu`, `e2e`. After Phase 2: add `docs`.
- **CI selector mapping:** `tier:<name>` GitHub label → workflow job running `uv run pytest -m <name>`.

## Key Principles

- **Single source of truth:** `tests.md` and `pyproject.toml` must agree on the marker set. If they disagree, the marker is "unregistered" and pytest emits warnings.
- **Plan adopts add-marker route, not remap.** The plan considered remapping `tier: docs` task-JSON values to the integration marker (lines 152-155) and rejected it because tests.md lists tiers explicitly. Reversal is possible if marker proliferation becomes a concern.
- **No silent integration substitute:** doc-tier tests are currently decorated `@pytest.mark.integration` as a stand-in. The fix is to register `docs` and swap the decorators.

## Pre-resolved Design Decisions

- Marker name: `docs` (lowercase, matches existing tier-name style).
- Marker description: "documentation-anchor / doc-tier tests".
- Affected tests: `test_p7_3.py`, `test_p7_4.py`, `test_p7_5.py` (if present), `test_p7_6.py`.

## Allowed Deviations

- None beyond the description text.

## Downstream Impact

- Future docs-tier tests use `@pytest.mark.docs` directly without integration substitute.
- CI tier:docs label-routed selector becomes the canonical doc-tier runner.
