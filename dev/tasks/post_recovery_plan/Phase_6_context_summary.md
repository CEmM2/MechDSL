# Phase 6 Context Summary: Test-layer hardening

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **Test helpers location:** `packages/mechdsl-core/tests/` — shared helpers go in `_e2e_helpers.py` (single underscore prefix denotes test-internal module).
- **Family-split rule** (.claude/rules): cross-test imports allowed once a third caller exists. Phase 6 promotes only the existing two callers; the family-split policy must permit this before refactor.
- **Marker scanning** uses regex on source lines, not absolute line numbers.

## Key Principles

- **Robust matchers over fixed indices:** any test that depends on the order of a list, a hardcoded line number, or a fixed substring offset is structural debt. Replace with iteration + filter, regex + marker, or fixture-derived unique values.
- **Single source of truth for shared helpers:** duplicated `_import_generated_module` is a refactor trigger. Promote to `_e2e_helpers.py`.
- **Marker noise minimization:** in-source markers (e.g. `# intentional-cleanup-site`) stay terse; their meaning is documented in the host module's docstring.

## Pre-resolved Design Decisions

- Helper module name: `_e2e_helpers.py`.
- Marker comment text: `# intentional-cleanup-site`.
- `test_p7_4.py` notes filter: by plan-referenced filename.
- `test_phase6_exit.py` migrates from `_INTENTIONAL_CLEANUP_MATCHES` line-number whitelist to regex scan over `test_emission_verification.py`.

## Allowed Deviations

- If family-split policy forbids the cross-import, escalate to user before proceeding (plan line 305-309).

## Downstream Impact

- Establishes pattern (shared helper module, in-source markers, fixture-derived names) that future e2e tests should adopt.
- Removes structural debt that would compound as more e2e tests land.
