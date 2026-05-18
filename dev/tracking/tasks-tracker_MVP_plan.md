# MechDSL MVP Development Task Tracker

> ⚠️ **Superseded** — the active execution source is [`tasks-tracker_recovery_plan_latex_contract.md`](tasks-tracker_recovery_plan_latex_contract.md), driven by [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md). This tracker is retained for historical reference only (Phase 7 / R6 archival, P7-5).

Generated on: 2026-04-01
This tracker records execution status for the MVP_plan task set.

> **Status vocabulary:** see [`STATUS_LEGEND.md`](STATUS_LEGEND.md) for the canonical
> four-value set (`not_started`, `done`, `deferred`, `implemented-via-substitute`).
> Rows that referenced the deferred/superseded frontend tasks (`P2.1`–`P2.5`) should
> now use `implemented-via-substitute` and cite the substitute under
> [`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md).

## MVP_plan Tracker

Plan source: `dev/plans/MVP_plan.md`
Task index: `dev/tasks/MVP_plan/all-tasks.md`

| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |
|---|---|---|---|---|---|---|---|---|---|
| P0.1 | Workspace dependency lock alignment | not_started | — | — | P0.2, P0.4, P0.5 | 9–12 | — | — | — |
| P0.2 | Core package skeleton completeness | not_started | — | P0.1 | P1.1, P1.2, P2.5, P3.1–P3.5, P4.1–P4.4 | 14–18 | — | — | — |
| P0.3 | CI workflow baseline | not_started | — | — | P5.3 | 20–24 | — | — | — |
| P0.4 | Linear solver interface contract | not_started | — | P0.1 | P1.1, P1.2, P7.1 | 26–31 | — | — | — |
| P0.5 | Tier-1 tensor ops utility | not_started | — | P0.1 | P1.1, P1.2 | 33–36 | — | — | — |
| P1.1 | Handwritten TL Hex8 elastic reference kernel | not_started | — | P0.2, P0.4, P0.5 | P1.3, P9.2 | 42–46 | — | — | — |
| P1.2 | Handwritten TL Hex8 J2 plastic reference kernel | not_started | — | P0.2, P0.4, P0.5 | P1.3, P9.2 | 48–52 | — | — | — |
| P1.3 | Golden artifact serialization fixture | not_started | — | P1.1, P1.2 | P9.2, P9.3 | 54–58 | — | — | — |
| P2.1 | NRPyLaTeX dependency fork wiring | implemented-via-substitute | — | — | P2.2, P2.3, P2.4 | 64–68 | — | recovery P2-3 (frontend split): dep is in `pyproject.toml`; full nrpylatex integration deferred to recovery Phase 2 | — |
| P2.2 | Mechanics directive tokenization | implemented-via-substitute | — | — | P2.3 | 70–74 | — | `mechdsl/frontend/parser.py::scan_directives` (bespoke parser, not nrpylatex) | — |
| P2.3 | Mechanics directive parsing handlers | implemented-via-substitute | — | — | P2.5 | 76–80 | — | `mechdsl/frontend/directives.py` HANDLERS | — |
| P2.4 | Two-manifold index typing | implemented-via-substitute | — | — | P2.5 | 82–86 | — | `mechdsl/frontend/directives.py::_mech_index` + IR layer index resolution | — |
| P2.5 | Frontend adapter in mechdsl-core | implemented-via-substitute | — | — | P4.1 | 88–92 | — | recovery P2-1: `mechdsl.compile_latex` façade (commit ca79e7b) | — |
| P3.1 | Kinematics computation module | not_started | — | P0.2 | P3.5, P4.3 | 98–102 | — | — | — |
| P3.2 | SVK constitutive model | not_started | — | P0.2 | P3.5, P6.3 | 104–108 | — | — | — |
| P3.3 | J2 power-law symbolic model | not_started | — | P0.2 | P3.5, P8.1 | 110–114 | — | — | — |
| P3.4 | Voigt/Mandel conversion utilities | not_started | — | P0.2 | P3.5, P4.3 | 116–120 | — | — | — |
| P3.5 | AD oracle verification module | not_started | — | P3.1, P3.2, P3.3, P3.4 | P9.3 | 122–126 | — | — | — |
| P4.1 | Mechanics IR schema + validation | not_started | — | P2.5, P0.2 | P4.3, P5.1 | 132–136 | — | — | — |
| P4.2 | Element IR schema for Hex8 TL | not_started | — | P0.2 | P4.3, P5.1 | 138–142 | — | — | — |
| P4.3 | FE localization pass | not_started | — | P4.1, P4.2, P3.1, P3.4 | P5.2, P6.2 | 144–148 | — | — | — |
| P4.4 | Artifact bundle model | not_started | — | P0.2 | P5.2, P6.2 | 150–154 | — | — | — |
| P5.1 | Einsum optimizer module | not_started | — | P4.1, P4.2 | P5.2, P5.3 | 160–164 | — | — | — |
| P5.2 | Element IR ↔ optimizer integration | not_started | — | P5.1, P4.3, P4.4 | P6.2 | 166–170 | — | — | — |
| P5.3 | CI budget regression fixture | not_started | — | P5.1, P0.3 | — | 172–176 | — | — | — |
| P6.1 | Hex8 static table provider | not_started | — | P0.2 | P6.2, P6.4 | 182–186 | — | — | — |
| P6.2 | Taichi printer core | not_started | — | P4.3, P4.4, P5.2 | P6.3, P6.4, P6.5 | 188–192 | — | — | — |
| P6.3 | Elastic constitutive emission | not_started | — | P6.2, P3.2 | P6.4, P9.2 | 194–198 | — | — | — |
| P6.4 | Internal force kernel emission | not_started | — | P6.1, P6.2, P6.3 | P7.1, P9.2 | 200–204 | — | — | — |
| P6.5 | Matrix-free tangent matvec emission | not_started | — | P6.2 | P7.1 | 206–210 | — | — | — |
| P7.1 | Newton-Raphson driver generation | not_started | — | P6.4, P6.5, P0.4 | P7.4, P9.1 | 218–222 | — | — | — |
| P7.2 | Boundary condition codegen | not_started | — | P0.2 | P7.1, P9.1 | 224–226 | — | — | — |
| P7.3 | Structured Hex8 mesh I/O | not_started | — | P0.2 | P9.1 | 228–232 | — | — | — |
| P7.4 | Adaptive load stepping runtime | not_started | — | P7.1 | P9.1 | 234–238 | — | — | — |
| P8.1 | Plastic constitutive emitter | not_started | — | P3.3, P6.2 | P8.2, P8.4 | 244–248 | — | — | — |
| P8.2 | Algorithmic tangent emitter | not_started | — | P8.1 | P8.4 | 250–254 | — | — | — |
| P8.3 | History field lifecycle support | not_started | — | P0.2 | P8.4 | 256–260 | — | — | — |
| P8.4 | Element kernel switch to elasto-plastic path | not_started | — | P8.1, P8.2, P8.3 | P9.1, P9.3 | 262–266 | — | — | — |
| P9.1 | Full pipeline e2e test | not_started | — | P7.1, P7.2, P7.3, P7.4, P8.4 | P9.4 | 272–276 | — | — | — |
| P9.2 | Generated vs handwritten equivalence tests | not_started | — | P1.3, P6.3, P6.4 | P9.4 | 278–280 | — | — | — |
| P9.3 | Physical benchmark suite hardening | not_started | — | P1.3, P3.5, P8.4 | P9.4 | 282–288 | — | — | — |
| P9.4 | Compiler-pass coverage closure | not_started | — | P9.1, P9.2, P9.3 | P9.5 | 290–294 | — | — | — |
| P9.5 | MVP user documentation | not_started | — | P9.4 | — | 296–300 | — | — | — |


## Update protocol

1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.
2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).
3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.

## Verification status

### Phase 0 aggregate verification:

#### Phase 0 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P0.1 | Workspace dependency lock alignment | (manual: `uv sync --frozen`) |
| P0.2 | Core package skeleton completeness | `tests/test_smoke.py` |
| P0.3 | CI workflow baseline | (manual: CI YAML validates) |
| P0.4 | Linear solver interface contract | `tests/test_smoke.py` (solver import) |
| P0.5 | Tier-1 tensor ops utility | `tests/test_smoke.py` (lib import) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_smoke.py -v` -> pass/total passed

### Phase 1 aggregate verification:

#### Phase 1 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P1.1 | Handwritten TL Hex8 elastic reference kernel | `tests/ref/ref_hex8_elastic.py` |
| P1.2 | Handwritten TL Hex8 J2 plastic reference kernel | `tests/ref/ref_hex8_plastic.py` |
| P1.3 | Golden artifact serialization fixture | `tests/test_artifacts.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_artifacts.py -v` -> pass/total passed

### Phase 2 aggregate verification:

#### Phase 2 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P2.1 | NRPyLaTeX dependency fork wiring | (manual: parser imports) |
| P2.2 | Mechanics directive tokenization | (lexer unit tests in fork) |
| P2.3 | Mechanics directive parsing handlers | (parser unit tests in fork) |
| P2.4 | Two-manifold index typing | (index validation tests in fork) |
| P2.5 | Frontend adapter in mechdsl-core | `tests/test_frontend.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_frontend.py -v` -> pass/total passed

### Phase 3 aggregate verification:

#### Phase 3 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P3.1 | Kinematics computation module | `tests/test_symbolic.py` |
| P3.2 | SVK constitutive model | `tests/test_symbolic.py` |
| P3.3 | J2 power-law symbolic model | `tests/test_symbolic.py` |
| P3.4 | Voigt/Mandel conversion utilities | `tests/test_symbolic.py` |
| P3.5 | AD oracle verification module | `tests/test_symbolic.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_symbolic.py -v` -> pass/total passed

### Phase 4 aggregate verification:

#### Phase 4 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P4.1 | Mechanics IR schema + validation | `tests/test_mechanics_ir.py` |
| P4.2 | Element IR schema for Hex8 TL | `tests/test_element_ir.py` |
| P4.3 | FE localization pass | `tests/test_mechanics_ir.py` |
| P4.4 | Artifact bundle model | `tests/test_artifacts.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_mechanics_ir.py packages/mechdsl-core/tests/test_element_ir.py -v` -> pass/total passed

### Phase 5 aggregate verification:

#### Phase 5 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P5.1 | Einsum optimizer module | `tests/test_einsum.py` |
| P5.2 | Element IR ↔ optimizer integration | `tests/test_einsum.py` |
| P5.3 | CI budget regression fixture | `tests/test_einsum.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_einsum.py -v` -> pass/total passed

### Phase 6 aggregate verification:

#### Phase 6 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P6.1 | Hex8 static table provider | `tests/test_codegen.py` |
| P6.2 | Taichi printer core | `tests/test_codegen.py` |
| P6.3 | Elastic constitutive emission | `tests/test_codegen.py` |
| P6.4 | Internal force kernel emission | `tests/test_codegen.py` |
| P6.5 | Matrix-free tangent matvec emission | `tests/test_codegen.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_codegen.py -v` -> pass/total passed

### Phase 7 aggregate verification:

#### Phase 7 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P7.1 | Newton-Raphson driver generation | `tests/test_codegen.py` |
| P7.2 | Boundary condition codegen | `tests/test_boundaries.py` |
| P7.3 | Structured Hex8 mesh I/O | `tests/test_codegen.py` |
| P7.4 | Adaptive load stepping runtime | `tests/test_codegen.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_boundaries.py -v` -> pass/total passed

### Phase 8 aggregate verification:

#### Phase 8 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P8.1 | Plastic constitutive emitter | `tests/test_codegen.py` |
| P8.2 | Algorithmic tangent emitter | `tests/test_codegen.py` |
| P8.3 | History field lifecycle support | `tests/test_codegen.py` |
| P8.4 | Element kernel switch to elasto-plastic path | `tests/test_codegen.py` |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_codegen.py -v` -> pass/total passed

### Phase 9 aggregate verification:

#### Phase 9 mapping between test and task:

| Task ID | Title | Test file |
|---|---|---|
| P9.1 | Full pipeline e2e test | `tests/test_e2e.py` |
| P9.2 | Generated vs handwritten equivalence tests | `tests/test_codegen.py` |
| P9.3 | Physical benchmark suite hardening | `tests/test_mechanics_ir.py`, `tests/test_frontend.py` |
| P9.4 | Compiler-pass coverage closure | (traceability matrix) |
| P9.5 | MVP user documentation | (manual: docs walkthrough) |

#### Verification outcomes:

    `uv run pytest packages/mechdsl-core/tests/test_e2e.py -v` -> pass/total passed
