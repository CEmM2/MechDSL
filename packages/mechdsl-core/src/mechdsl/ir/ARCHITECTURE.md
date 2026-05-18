# `mechdsl.ir` — IR architecture and stability contract

`mechdsl.ir` is the **semantic center** of the FEM compiler pipeline. Every information flow — from frontend parse to codegen emit — passes through `ProblemIR` and `ElementIR` defined here. This file documents the stability contract that those IRs expose. The authoritative design-doc home for IR design philosophy is `dev/design_docs/04-MECHANICS-IR.md`; this file is the in-code mirror that ships next to the implementation and is updated in the same PR as the code it describes.

## MVP-stable subset

The set of `ProblemIR` configurations covered by the canonical compile path on the Taichi backend (i.e. `compile_latex(profile="mvp")`) is encoded as the module-level constant `MVP_STABLE_SUBSET` in `mechanics_ir.py`. Configurations outside this subset may still construct successfully (the IR keeps experimental enum values valid for in-tree research code), but stability-promised entry points reject them at the IR boundary so the failure points at the IR rather than surfacing deep inside codegen / runtime.

| Axis | MVP-stable values | Reject path → Plan B phase |
|------|-------------------|----------------------------|
| `dim` | `3` | 2D / non-3D — Plan B B2 |
| `formulation` | `total_lagrangian` | `updated_lagrangian` — Plan B B1 |
| `element_type` | `hex8` | `tet4`, `tet10`, `hex20` — Plan B B5 |
| `material.model` | `svk`, `j2_power_law` | hyperelastic / damage — Plan B B4, B6 |
| `dynamics_mode` | `static` | `explicit` — Plan B B7 |
| `configuration` | `reference` | `current` — Plan B B1 |

### Helpers on `ProblemIR`

- `assert_mvp_stable() -> None` raises `MvpSubsetViolation` (a subclass of `UnsupportedError` per `.claude/rules/ir.md`) when any axis lies outside the table above. The exception message names the offending field, the actual value, the allowed values, and the Plan-B phase that adds support.
- `is_mvp_stable() -> bool` is the non-throwing variant, useful when callers want to branch on the contract without catching exceptions.

### Lock-step requirement

Adding an MVP-stable value is a contract change. Edits to the table above must be paired with:

1. The `MVP_STABLE_SUBSET` constant in `mechanics_ir.py`.
2. The `ALLOWED_PROFILES` set in `packages/mechdsl-core/src/mechdsl/__init__.py` (if a new compile profile is also being introduced).
3. The test cases in `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p3_4.py`.
4. The README support-tier table.

A regression test in `test_p3_4.py` asserts that this file contains the heading `MVP-stable subset` so silent drift is impossible.

## Optional semantic enrichment (recovery-plan Phase 3)

`ProblemIR` carries four optional semantic-enrichment fields (`fields`, `domain`, `mesh_contract`, `residual_contract`) added in P3-1. They default to safe empty / `None` values so legacy callers continue working without source changes. Their full schema lives in the dataclass docstrings; the round-trip and immutability invariants are exercised by `test_p3_1.py`.

## Recovery context

This `ARCHITECTURE.md` was added under recovery-plan task **P3-4** (R2.4) — see `dev/plans/recovery_plan_latex_contract.md` Phase 3. The recovery plan deliberately puts the stability contract in code-adjacent form because `dev/design_docs/04-MECHANICS-IR.md` is hook-protected against agent edits and the contract must move in lock-step with code changes.
