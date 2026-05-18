# Phase 2 Scaffold Validation

## Task JSON Field Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P2-T1 | Implement extract_einsum_specs() | `test_plan.tier`: was "fast" | auto-filled → "unit" |
| P2-T2 | Refactor fe_localise + update exports | `test_plan.tier`: was "fast" | auto-filled → "regression" |
| P2-T3 | Write einsum extraction tests | `test_plan.tier`: was "fast"; `risks`: empty | auto-filled tier → "unit"; risks: no risk (test-only task) |

All `objective`, `acceptance_criteria`, `implementation_steps`, and `deliverables` fields are populated. No `needs-human-review` flags.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 3 |
| Test cases assessed | 12 |
| Cases covered by existing tests | 3 (P2-T2 regression cases) |
| Cases partially covered (stubs generated) | 0 |
| Cases with no existing tests (stubs generated) | 9 |
| New stub files created | 1 |
| Total new stubs generated | 9 |
| Tasks fully covered by existing tests (no stub needed) | 1 (P2-T2) |
| Tasks needing human review | 0 |
| Auto-filled fields | test_plan.tier (3), test_artifacts (3), verification_commands (1) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P2-T1 | Returns 3 specs | `test_localise.py` | `test_all_three_specs_present` | partial — tests via localise(), not extract_einsum_specs() |
| P2-T1 | Correct einsum strings | `test_localise.py` | `test_einsum_string_nonempty` (×3 classes) | partial — checks non-empty, not exact values |
| P2-T1 | Correct operand shapes | `test_localise.py` | `test_operand_ranks_match_einsum_indices` | partial — rank consistency, not exact shapes |
| P2-T2 | All localise tests pass | `test_localise.py` | 28 tests | covered |
| P2-T2 | All e2e tests pass | `test_e2e.py` | e2e tests | covered |
| P2-T2 | All einsum tests pass | `test_einsum.py` | einsum tests | covered |

## New Stub Files Created

| File | Task IDs | Stubs |
|------|----------|-------|
| `packages/mechdsl-core/tests/test_einsum_extract.py` | P2-T1, P2-T3 | 9 |

### Stub functions in test_einsum_extract.py

| Class | Function | Covers task | Covers criterion |
|-------|----------|-------------|-----------------|
| `TestExtractEinsumSpecs` | `test_returns_three_specs` | P2-T1 | returns 3 keys |
| `TestExtractEinsumSpecs` | `test_strain_displacement_einsum_string` | P2-T1 | correct einsum strings |
| `TestExtractEinsumSpecs` | `test_internal_force_einsum_string` | P2-T1 | correct einsum strings |
| `TestExtractEinsumSpecs` | `test_tangent_matvec_einsum_string` | P2-T1 | correct einsum strings |
| `TestExtractEinsumSpecs` | `test_operand_shapes_hex8` | P2-T1 | correct shapes |
| `TestExtractEinsumSpecs` | `test_rejects_non_hex8_element` | P2-T1 | LocalisationError |
| `TestEinsumExtractionRegression` | `test_deterministic_output` | P2-T3 | determinism |
| `TestEinsumExtractionRegression` | `test_all_specs_are_einsum_spec_instances` | P2-T3 | type check |
| `TestEinsumExtractionRegression` | `test_spec_names_match_dict_keys` | P2-T3 | consistency |

## Tasks Needing Human Review Before execute-phase

None — all tasks are fully specified.

## Ready for execute-phase

Fully scaffolded:
- P2-T1: Implement extract_einsum_specs()
- P2-T2: Refactor fe_localise + update exports
- P2-T3: Write einsum extraction tests
