---
name: test-coverage-mapper
description: Map MechDSL test coverage from spec IDs to test files to source modules, then identify gaps and rank them by risk. Use during planning, auditing, or before releases.
---

# Test Coverage Mapper

This skill is read-only.

Read `dev/design_docs/08-VERIFICATION.md` first.

## Workflow

1. Extract all verification IDs and descriptions from the spec.
2. Collect test files and test functions from both packages.
3. Map spec IDs to tests using explicit references first, then carefully labeled inferred matches.
4. Map test files to the source modules they exercise.
5. Map source modules to the design-doc sections they implement.
6. Identify gaps:
   - spec IDs without tests
   - source modules without test coverage
   - design-doc requirements without verification
7. Rank the gaps by risk.

## Output

Produce:

- a spec-ID coverage table
- a module-to-test matrix
- prioritized gap lists
- recommended next tests to add

