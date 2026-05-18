# Phase 1 Scaffold Validation

**Phase:** 1 — Updated Lagrangian formulation (B1)
**Plan:** `dev/design_docs/PLAN-B.md`
**Scaffolded:** 2026-04-15
**Tasks in phase:** 7 (P1-1 … P1-7)

## Per-task validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P1-1 | ConfigurationIR extension (reference/current tagging) | none | no-op (all fields populated) |
| P1-2 | UL kinematics (spatial shape gradients and current Jacobian) | none | no-op |
| P1-3 | UL residual emission (Cauchy stress over current configuration) | none | no-op |
| P1-4 | UL tangent operator emission (Jaumann material + geometric stiffness) | none | no-op |
| P1-5 | Objective stress rates (Jaumann, Truesdell, Green-Naghdi) | none | no-op |
| P1-6 | Formulation switching (directive + codegen dispatch) | none | no-op |
| P1-7 | TL/UL equivalence + rigid rotation tests | none | no-op |

**Verdict:** All Phase 1 tasks are fully populated (objective, acceptance criteria, implementation steps, deliverables, risks, test_plan.tier, test_plan.cases). No auto-fill or `needs-human-review` actions are required — scaffold proceeds directly to stub generation in Step 3.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 7 |
| Test cases assessed | 28 |
| Cases covered by existing tests (full) | 0 |
| Cases partially covered by existing tests (regression hooks) | 8 |
| Cases with no existing tests (new stubs) | 28 |
| New stub files created | 6 |
| Total new stubs generated | 28 |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | none (all tasks fully populated at Plan-2-Tasks time) |

## Stub files created

| File | Task(s) | Stub count |
|------|---------|------------|
| `packages/mechdsl-core/tests/test_mechanics_ir_configuration.py` | P1-1 | 6 |
| `packages/mechdsl-core/tests/test_kinematics_ul.py` | P1-2 | 4 |
| `packages/mechdsl-core/tests/test_taichi_printer_ul.py` | P1-3, P1-4 | 7 |
| `packages/mechdsl-core/tests/test_objective_rates.py` | P1-5 | 4 |
| `packages/mechdsl-core/tests/test_formulation_switching.py` | P1-6 | 3 |
| `packages/mechdsl-core/tests/test_ul_equivalence.py` | P1-7 | 4 |

Verified collectable: 28 tests collected via pytest collect-only.

## Existing Test Coverage Found

| Task ID | Stub case | Existing test file | Function / class | Coverage |
|---------|-----------|--------------------|------------------|----------|
| P1-1 | test_supported_subset_rejection_still_fires | `tests/test_mechanics_ir.py` | regression suite | partial (regression guard) |
| P1-1 | test_problem_ir_reference_configuration_matches_baseline | `tests/test_symbolic_ir_interface.py::TestFormulationGuard` | test_total_lagrangian_is_the_only_valid_formulation, test_non_total_lagrangian_guard_mentions_plan_b1 | partial (must be UPDATED, not inverted) |
| P1-2 | test_current_jacobian_identity_at_f_eq_i | `tests/test_kinematics.py` | test_identity_via_compute, test_identity_via_convenience | partial (reference-config identity path only) |
| P1-3 | test_tl_emission_unchanged_byte_equal_to_existing_golden | `tests/test_emission_verification.py::TestInternalForceEmission` | TL structure checks | partial (TL regression — unchanged) |
| P1-3 | test_tl_emission_unchanged_byte_equal_to_existing_golden | `tests/golden/generated_elastic.py.golden`, `generated_plastic.py.golden` | byte-identical snapshots | partial (TL regression guard) |
| P1-4 | test_tl_tangent_golden_unchanged | `tests/test_emission_verification.py::TestTangentMatvecEmission` | analytical TL tangent checks | partial (TL regression — unchanged) |
| P1-6 | test_ul_directive_parses_without_raising | `tests/test_frontend_parser.py::test_updated_lagrangian_rejected_with_plan_b1` | — | partial (INVERT to success case) |
| P1-6 | test_ul_directive_parses_without_raising | `tests/test_frontend_build_context.py::test_formulation_updated_lagrangian_raises_unsupported_error` | — | partial (INVERT to success case) |
| P1-7 | handwritten UL reference | `tests/ref/ref_hex8_elastic.py` | reference solver pattern | partial (template for new `ref_hex8_ul.py`) |

## Tasks Needing Human Review Before Execute

None — every Phase 1 task has a complete JSON (objective, acceptance criteria, implementation steps, deliverables, risks, test plan). No auto-fill was needed.

## Ready for Execute

Fully scaffolded — all 7 tasks:
- P1-1: ConfigurationIR extension (reference/current tagging)
- P1-2: UL kinematics (spatial shape gradients and current Jacobian)
- P1-3: UL residual emission (Cauchy stress over current configuration)
- P1-4: UL tangent operator emission (Jaumann material + geometric stiffness)
- P1-5: Objective stress rates (Jaumann, Truesdell, Green-Naghdi)
- P1-6: Formulation switching (directive + codegen dispatch)
- P1-7: TL/UL equivalence + rigid rotation tests

Needs human review before execution: **none**.

## Dependency order for issue creation

Dependency-order task-issue creation (blockers first):

1. P1-1 (no blockers within phase) → P1-5 (blocked_by P1-1)
2. P1-2 (blocked_by P1-1) → P1-3 (blocked_by P1-2) → P1-4 (blocked_by P1-3, P1-5)
3. P1-6 (blocked_by P1-3, P1-4)
4. P1-7 (blocked_by P1-5, P1-6)

Computed order: P1-1, P1-5, P1-2, P1-3, P1-4, P1-6, P1-7.

