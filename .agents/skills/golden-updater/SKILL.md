---
name: golden-updater
description: Regenerate MechDSL golden files after an intentional compiler change, review the diff, and confirm tests pass again. Use when golden artifacts are expected to change.
---

# Golden Updater

Use this skill only when the code change intentionally affects emitted source or numerical baselines.

## Workflow

1. Use `$ARGUMENTS` to decide scope:
   - source or elastic or plastic for source goldens
   - numerical or npz for numerical baselines
   - all for everything
   - a specific filename for one artifact
2. Snapshot the affected golden files before changing them.
3. Run the failing golden tests first to confirm the artifacts are stale.
4. Regenerate with `packages/mechdsl-core/tests/generate_golden.py`.
5. Diff old vs new artifacts and classify each change as:
   - expected
   - indirect
   - suspicious
6. Re-run the relevant golden tests.

## Reporting

For each changed artifact, report:

- what changed
- which pipeline layer likely caused it
- whether the change is expected, indirect, or suspicious

If any change is suspicious, stop and report that prominently.

