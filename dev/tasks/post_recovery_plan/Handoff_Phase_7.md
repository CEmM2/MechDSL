# Phase 7 Handoff

> **From**: Phase 6 agent
> **To**: Phase 7 agent
> **Date**: 2026-05-01
> **Branch**: `post-recovery-plan_phase-6`

## Phase 6 Completion Summary

| Task | Title | Tests | Notes |
|------|-------|-------|-------|
| P6-1 | Extract `_e2e_helpers.py` | 2/2 | shared helper exposes `_import_generated_module(source, tmp_path, name='gen_e2e')` |
| P6-2 | Swap helper consumers | 4/4 | `test_e2e_taichi.py` + `test_p7_2.py` import from `tests._e2e_helpers`; call sites pin `name=` where needed |
| P6-3 | Robustify `test_p7_4.py:92` | 2/2 + 2/2 | `notes[0]` replaced by filter on plan-referenced filename |
| P6-4 | Replace `_INTENTIONAL_CLEANUP_MATCHES` whitelist | 3/3 + 5/5 | marker scan with ±3-line window survives ruff multi-line statement reformatting |

**Overall**: 11 task tests + 9 target-file tests pass; 1846/1846 fast suite green.

## Architecture After Phase 6

- New file `packages/mechdsl-core/tests/_e2e_helpers.py` — shared `_import_generated_module` helper.
- `test_phase6_exit.py` constants: `_INTENTIONAL_CLEANUP_MARKER = "intentional-cleanup-site"` + `_CLEANUP_MARKER_WINDOW = 3`.
- `test_emission_verification.py` carries `# intentional-cleanup-site` markers next to its SVK-no-TODO assertion.

## Remaining `_import_generated_module` duplicates

Plan scope only swapped 2 of 4 callers. Two duplicate definitions remain:

- `packages/mechdsl-core/tests/test_e2e_plastic.py`
- `packages/mechdsl-core/tests/test_explicit_dynamics_acceptance.py`

Future cleanup may consolidate; not in Phase 7 plan scope.

## Phase 7 Direction (Documentation polish + governance reconciliation)

Plan §lines 320+:

- P7-1: restore `## Inventory` anchor in `dev/examples/README.md`.
- P7-2: replace `text.find()` ordering in `test_p7_3.py` with first-runnable-code-block detector; loosen path matching.
- P7-3: rename `_import_generated_module` constant `gen_p7_2`; clear forward-pointer comment.
- P7-4: trim `test_p7_6.py` to 100–250 lines.
- P7-5: clarify `_SUPERSEDED.md` runtime-active vs archived semantics.
- P7-6: refresh GitNexus index (user-authorized).
- P7-7: add CI baseline-stability smoke job.

Mostly low-risk doc/test polish; main-thread direct execution is fine.

## Recurring P2-2 docs allowlist pattern

Three widenings on record (P3-1, P4-5, P5-5). Phase 7 can introduce a registry-based replacement if scope permits — flagged but not blocking.
