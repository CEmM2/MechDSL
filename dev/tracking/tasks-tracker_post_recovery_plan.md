# Development Task Tracker — post_recovery_plan

Generated on: 2026-04-30
This tracker records execution status for the post_recovery_plan task set.

## post_recovery_plan Tracker

Plan source: `dev/plans/post_recovery_plan.md`
Task index: `dev/tasks/post_recovery_plan/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P1-1 | Extend BoundaryCondition IR slot (traction + surface tag) | done | claude-opus-4-7 | — | P1-2, P1-3 | 91-115 | post-recovery-plan_phase-1 | test_p1_1.py + 1676/1676 fast suite | 2026-04-30 |
| P1-2 | Extend Neumann directive parser | done | claude-opus-4-7 | — | P1-3 | 88-90 | post-recovery-plan_phase-1 | test_p1_2.py + 1682/1682 fast suite | 2026-04-30 |
| P1-3 | Lower Neumann BC to per-node force contributions | done | claude-opus-4-7 | — | P1-4 | 92-94 | post-recovery-plan_phase-1 | test_p1_3.py + 1691/1691 fast suite | 2026-04-30 |
| P1-4 | Emit f_ext init Taichi kernel | done | claude-opus-4-7 | — | P1-5, P1-7 | 94-96 | post-recovery-plan_phase-1 | test_p1_4.py + 1699/1699 fast suite | 2026-04-30 |
| P1-5 | Extend compile_latex façade for f_ext kernel | done | claude-opus-4-7 | — | P1-6, P3-1 | 96-117 | post-recovery-plan_phase-1 | test_p1_5.py + 1704/1704 fast suite | 2026-04-30 |
| P1-6 | Replace numeric f_ext injection with directive-only path | done | claude-opus-4-7 | — | — | 98-111 | post-recovery-plan_phase-1 | test_p1_6.py + test_p7_2.py + 1709/1709 fast suite | 2026-04-30 |
| P1-7 | New test_boundary_neumann.py golden test | done | claude-opus-4-7 | — | — | 100-111 | post-recovery-plan_phase-1 | test_p1_7.py + test_boundary_neumann.py + 1715/1715 fast suite | 2026-04-30 |
| P2-1 | Register `docs` pytest marker | done | 2026-05-01 | — | P2-2, P2-3 | 128-131 | post-recovery-plan_phase-2 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_1.py | 3/3 task + 1765/1765 fast suite |
| P2-2 | Swap @pytest.mark.integration → @pytest.mark.docs | done | 2026-05-01 | P2-1 | P2-3 | 131-135 | post-recovery-plan_phase-2 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_2.py + recovery_plan_latex_contract/test_p7_3..6.py | 2/2 task + 8/8 -m docs + 1767/1767 fast suite |
| P2-3 | Audit/update CI workflow tier:docs selector | done | 2026-05-01 | P2-1 | — | 135-138 | post-recovery-plan_phase-2 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_3.py + .github/workflows/ci.yml (docs-tests job) | 2/2 task + ci.yml YAML-valid + 1769/1769 fast suite |
| P3-1 | Add BC handoff paragraph to compile_latex docstring | done | 2026-05-01 | P1-5 | P3-2 | 165-168 | post-recovery-plan_phase-3 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_1.py | 3/3 task + ruff D clean + 1772/1772 fast suite |
| P3-2 | New docstring-presence test | done | 2026-05-01 | P3-1 | — | 168-172 | post-recovery-plan_phase-3 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_2.py + packages/mechdsl-core/tests/test_compile_latex_docstring.py | 6/6 task + 17/17 -m docs + 1778/1778 fast suite |
| P4-1 | New frontend/math_parser.py wrapping nrpylatex | done | 2026-05-01 | — | P4-3 | 195-199 | post-recovery-plan_phase-4 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_1.py | 4/4 task + 1804/1804 fast suite |
| P4-2 | symbolic/bridge.py adapter | done | 2026-05-01 | — | P4-3 | 200-202 | post-recovery-plan_phase-4 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_2.py | 6/6 task + 1804/1804 fast suite |
| P4-3 | Wire math parser into frontend pipeline | done | 2026-05-01 | P4-1, P4-2 | P4-4, P4-5 | 199-200 | post-recovery-plan_phase-4 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_3.py | 5/5 task + 56/56 existing frontend + 1804/1804 fast suite |
| P4-4 | New test_nrpylatex_round_trip.py | done | 2026-05-01 | P4-3 | — | 203-206 | post-recovery-plan_phase-4 | packages/mechdsl-core/tests/test_nrpylatex_round_trip.py + plan_tests/post_recovery_plan/test_p4_4.py | 8/8 deliverable+meta-spec; closed-form SVK/J2 deferred |
| P4-5 | Add svk_latex_math.tex example + README inventory | done | 2026-05-01 | P4-3 | — | 206-208 | post-recovery-plan_phase-4 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_5.py + dev/examples/svk_latex_math.tex | 3/3 task + 1804/1804 fast suite |
| P5-1 | Author dev/algorithms/radial_return_j2.tex | done | 2026-05-01 | — | P5-2 | 237-239 | post-recovery-plan_phase-5 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_1.py + dev/algorithms/radial_return_j2.tex | 4/4 task |
| P5-2 | algo2code radial-return codegen test | done | 2026-05-01 | P5-1 | P5-3 | 239-242 | post-recovery-plan_phase-5 | packages/algo2code/tests/test_radial_return_codegen.py + plan_tests/test_p5_2.py | 5/5 codegen + 5/5 meta-spec |
| P5-3 | Switch lib/plasticity.py default + feature flag | done | 2026-05-01 | P5-2 | P5-4, P5-5 | 242-246 | post-recovery-plan_phase-5 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_3.py + lib/plasticity.py | 5/5 task |
| P5-4 | Imported vs algo2code parity test | done | 2026-05-01 | P5-3 | — | 246-250 | post-recovery-plan_phase-5 | packages/mechdsl-core/tests/test_j2_radial_return_parity.py + plan_tests/test_p5_4.py | 4/4 parity + 5/5 meta-spec |
| P5-5 | Design-doc note on substitution + fallback | done | 2026-05-01 | P5-3 | — | 250-252 | post-recovery-plan_phase-5 | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_5.py + dev/design_docs/07-CONVENTIONS.md §11 | 3/3 task + 1835/1835 fast suite |
| P6-1 | Extract _e2e_helpers.py shared module | done | 2026-05-01 | — | P6-2 | 282-284 | post-recovery-plan_phase-6 | tests/_e2e_helpers.py + plan_tests/post_recovery_plan/test_p6_1.py | 2/2 |
| P6-2 | Update e2e tests to import shared helper | done | 2026-05-01 | P6-1 | — | 284-287 | post-recovery-plan_phase-6 | tests/test_e2e_taichi.py + recovery_plan_latex_contract/test_p7_2.py + plan_tests/test_p6_2.py | 4/4 |
| P6-3 | Robustify test_p7_4.py notes iteration | done | 2026-05-01 | — | — | 287-290 | post-recovery-plan_phase-6 | recovery_plan_latex_contract/test_p7_4.py + plan_tests/test_p6_3.py | 2/2 task + 2/2 p7_4 |
| P6-4 | Replace test_phase6_exit.py whitelist with regex/marker | done | 2026-05-01 | — | — | 290-294 | post-recovery-plan_phase-6 | tests/test_phase6_exit.py + tests/test_emission_verification.py + plan_tests/test_p6_4.py | 3/3 task + 5/5 phase6_exit + 1846/1846 fast |
| P7-1 | Restore ## Inventory anchor in README | done | 2026-05-01 | — | — | 326 | post-recovery-plan_phase-7 | dev/examples/README.md + plan_tests/test_p7_1.py | 1/1 |
| P7-2 | Robustify test_p7_3.py ordering + path matching | done | 2026-05-01 | — | — | 327-330 | post-recovery-plan_phase-7 | recovery_plan_latex_contract/test_p7_3.py + plan_tests/test_p7_2.py | 3/3 task + 2/2 p7_3 |
| P7-3 | Rename _import_generated_module constant; clear comment | done | 2026-05-01 | P1-6 | — | 330-336 | post-recovery-plan_phase-7 | recovery_plan_latex_contract/test_p7_2.py + plan_tests/test_p7_3.py | 3/3 |
| P7-4 | Trim test_p7_6.py to 100-250 lines | done | 2026-05-01 | — | — | 334-336 | post-recovery-plan_phase-7 | recovery_plan_latex_contract/test_p7_6.py + plan_tests/test_p7_4.py | 2/2 (no-op; 193 lines in budget) |
| P7-5 | Clarify _SUPERSEDED.md runtime-active vs archived | done | 2026-05-01 | — | — | 336-338 | post-recovery-plan_phase-7 | dev/tasks/PLAN-B/_SUPERSEDED.md + plan_tests/test_p7_5.py | 2/2 |
| P7-6 | Refresh GitNexus index (user-authorized) | done | 2026-05-01 | — | — | 338-340 | post-recovery-plan_phase-7 | plan_tests/test_p7_6.py | 0/0 (deferred per §Allowed Deviations; auth-required skip) |
| P7-7 | Add CI baseline-stability smoke job | done | 2026-05-01 | — | — | 340-343 | post-recovery-plan_phase-7 | .github/workflows/ci.yml + plan_tests/test_p7_7.py | 2/2 + 1859/1859 fast |

## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P1-1 | BoundaryCondition IR slot | packages/mechdsl-core/tests/ir/ |
| P1-2 | Neumann directive parser | packages/mechdsl-core/tests/frontend/ |
| P1-3 | Lower Neumann BC | packages/mechdsl-core/tests/lowering/ |
| P1-4 | Emit f_ext kernel | packages/mechdsl-core/tests/codegen/ |
| P1-5 | Façade extension | packages/mechdsl-core/tests/test_compile_latex.py |
| P1-6 | test_p7_2 directive-only | packages/mechdsl-core/tests/test_p7_2.py |
| P1-7 | Golden test | packages/mechdsl-core/tests/test_boundary_neumann.py |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/ -k "boundary or neumann or p7_2" -v` -> pass/total

### Phase 2 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P2-1 | Register docs marker | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_1.py |
| P2-2 | Marker swap | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_2.py + recovery_plan_latex_contract/test_p7_3..6.py |
| P2-3 | CI tier:docs selector | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_3.py + .github/workflows/*.yml |

#### Verification outcomes:

    `uv run pytest --markers | grep -E '^docs:|^@?pytest\.mark\.docs'` -> registered/missing
    `uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_1.py packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_2.py packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_3.py -v` -> pass/total
    `uv run pytest -m docs` -> pass/total
    `grep -nE '\-m\s+"?docs' .github/workflows/*.yml` -> match/no-match

### Phase 3 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P3-1 | Docstring paragraph | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_1.py + (lint) uv run ruff check --select D packages/mechdsl-core/src/mechdsl/__init__.py |
| P3-2 | Docstring presence test | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_2.py + packages/mechdsl-core/tests/test_compile_latex_docstring.py |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_1.py packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p3_2.py -v` -> pass/total
    `uv run pytest packages/mechdsl-core/tests/test_compile_latex_docstring.py -v` -> pass/total
    `uv run pytest -m docs -k "compile_latex_docstring or p3_"` -> pass/total
    `uv run ruff check --select D packages/mechdsl-core/src/mechdsl/__init__.py` -> clean/violations

### Phase 4 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P4-1 | math_parser | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_1.py |
| P4-2 | bridge | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_2.py |
| P4-3 | wiring | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_3.py + existing test_directives.py / test_two_point.py |
| P4-4 | round-trip | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_4.py + packages/mechdsl-core/tests/test_nrpylatex_round_trip.py |
| P4-5 | example | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_5.py + dev/examples/svk_latex_math.tex + dev/examples/README.md |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p4_*.py -v` -> pass/total
    `uv run pytest packages/mechdsl-core/tests/test_nrpylatex_round_trip.py -v` -> pass/total
    `uv run pytest -k "math_parser or bridge or nrpylatex" -v` -> pass/total
    `uv run pytest -m "not slow and not gpu" --tb=line -q` -> pass/total

### Phase 5 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P5-1 | algpseudocode source | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_1.py + dev/algorithms/radial_return_j2.tex |
| P5-2 | codegen test | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_2.py + packages/algo2code/tests/test_radial_return_codegen.py |
| P5-3 | dispatch switch | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_3.py + packages/mechdsl-core/src/mechdsl/lib/plasticity.py |
| P5-4 | parity test | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_4.py + packages/mechdsl-core/tests/test_j2_radial_return_parity.py |
| P5-5 | design doc | packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_5.py + dev/design_docs/06-PLASTICITY.md (or 07-CONVENTIONS.md) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p5_*.py -v` -> pass/total
    `uv run pytest packages/algo2code/tests/test_radial_return_codegen.py packages/mechdsl-core/tests/test_j2_radial_return_parity.py -v` -> pass/total
    `MECHDSL_USE_IMPORTED_RR=1 uv run pytest -m "not slow and not gpu" --tb=line -q` -> pass/total
    `uv run pytest -k "radial_return or plasticity"` -> pass/total

### Phase 6 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P6-1 | _e2e_helpers extract | packages/mechdsl-core/tests/_e2e_helpers.py |
| P6-2 | helper consumers | tests/test_p7_2.py, tests/test_e2e_taichi.py |
| P6-3 | notes iteration | tests/test_p7_4.py |
| P6-4 | regex/marker whitelist | tests/test_phase6_exit.py, tests/test_emission_verification.py |

    `uv run pytest -m "not slow and not gpu" -k "p7_4 or phase6_exit or e2e"` -> pass/total

### Phase 7 aggregate verification:

| Task ID | Title | Test file |
|---|---|---|
| P7-1 | README inventory anchor | dev/examples/README.md |
| P7-2 | test_p7_3 robustness | tests/test_p7_3.py |
| P7-3 | gen_p7_2 rename | tests/test_p7_2.py |
| P7-4 | test_p7_6 trim | tests/test_p7_6.py |
| P7-5 | _SUPERSEDED.md | dev/tasks/PLAN-B/_SUPERSEDED.md |
| P7-6 | GitNexus refresh | .gitnexus/meta.json |
| P7-7 | CI baseline-stability | .github/workflows/ci.yml |

    `uv run pytest -m docs -k "p7_3 or p7_6 or p7_2"` -> pass/total