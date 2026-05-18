---
name: spec-sync
description: Compare current code structure against the design docs and report drift — missing modules, mismatched interfaces, unimplemented validation. A spec coverage report.
allowed-tools: Read, Grep, Glob
model: sonnet
---

# Spec Sync — Coverage Report

Compare the current codebase against the design docs to identify drift, gaps, and mismatches.

## Process

### 1. Package structure check

Compare the actual `packages/mechdsl-core/src/mechdsl/` tree against the package structure defined in `dev/design_docs/01-ARCHITECTURE.md §5`. Report:
- ✅ Files that exist and match the spec
- ❌ Files specified in the spec but missing from the codebase
- ➕ Files in the codebase not mentioned in the spec (may be fine — just flag for awareness)

### 2. Interface check

For each layer, compare the function signatures in the code against the interfaces defined in `dev/design_docs/01-ARCHITECTURE.md §2`. Check:
- Function names match
- Parameter names and types match
- Return types match
- Required fields on dataclasses/named tuples match

### 3. Supported-subset check

Compare the validation logic in `mechdsl.ir.mechanics_ir` against the supported-subset contract in `dev/design_docs/00-OVERVIEW.md §8`. Check:
- Every "Explicitly unsupported" construct from the spec has a corresponding rejection check
- Error messages match the spec's prescribed messages
- Plan phase references are correct

### 4. Convention check

Grep the codebase for potential convention violations:
- Voigt ordering: search for hardcoded index arrays that might use wrong ordering
- Sign conventions: search for pressure/stress definitions
- Tolerance values: compare against `dev/design_docs/07-CONVENTIONS.md §6`

### 5. Plan A phase status

For each phase in `dev/design_docs/PLAN-A.md`, assess implementation status:
- **Done**: code exists, tests pass
- **Partial**: code exists but incomplete or untested
- **Not started**: no code yet

## Output

A structured report with:
1. Package structure coverage table
2. Interface conformance table
3. Supported-subset validation coverage
4. Convention violation warnings (if any)
5. Plan A progress summary
