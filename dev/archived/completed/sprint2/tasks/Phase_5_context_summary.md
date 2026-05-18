# Phase 5 Context Summary — Test Completeness Audit

## Conventions
- **08-VERIFICATION.md §2** defines 37 test IDs across 9 categories
- **Test ID format**: Category letter + number (e.g., S1, M3, C2)
- **Categories**: P (parser, 6), S (symbolic, 9), M (mechanics IR, 6), E (element IR, 6), N (einsum, 5), T (backend, 4), B (boundary, 5), A (artifact, 3), C (emission, 3)

## Key Principles
- The audit verifies *coverage*, not reimplementation — if an existing test already covers a test ID, it is sufficient
- Test IDs P3 (two-point tensor F_{iI}) and P4 (index manifold clash) require the parser which is a stub — these should be marked "deferred: parser not yet implemented"
- The verification matrix is the single source of truth for test coverage status

## Pre-resolved Design Decisions
- **P3/P4 deferral**: the LaTeX parser (frontend/) is not implemented — test IDs P3 and P4 are deferred until the parser is built. This is acceptable because build_context() (Phase 2) provides a programmatic path that bypasses the parser.
- **Existing strong coverage areas**: S1-S8 (124 tests), T1-T4 (192+ tests), E1-E6 (87 tests) are already well covered
- **C3 extended**: Sprint 1 delivered C3 for elastic; Phase 4 extends it to plastic

## Downstream Impact
- **P5-T4 (verification_matrix.md)** becomes the ongoing tracking artifact for test coverage
- Phase 5 does not create new source code — only tests and documentation
- Phase 5 completion is a prerequisite for Phase 6 exit criteria verification

## Key Files
- `dev/design_docs/08-VERIFICATION.md` — the authoritative test ID definitions
- All test files in `packages/mechdsl-core/tests/` — the 40+ existing test files
- `dev/tracking/verification_matrix.md` — the new file to be created
