---
name: spec-checker
description: Compare current MechDSL implementation code against the design docs and report drift, mismatches, and missing validation. Use after writing or modifying a module.
---

# Spec Checker

This skill is read-only.

## Workflow

1. Identify the relevant design docs for the files in scope.
2. Read the implementation and the matching spec sections.
3. Check for:
   - interface mismatches
   - missing fields
   - missing rejection logic
   - convention violations
   - missing JIT-budget enforcement in codegen
4. Report findings using:
   - conformant
   - deviation
   - violation

If `$ARGUMENTS` is empty, review all `packages/mechdsl-core/src/mechdsl/` modules against their corresponding specs.

