---
name: verify
description: "Skill for the Verify area of MechDSL. 15 symbols across 3 files."
---

# Verify

15 symbols | 3 files | Cohesion: 71%

## When to Use

- Working with code in `packages/`
- Understanding how test_mms_body_force_substitution, mms_body_force, mms_exact_displacement work
- Modifying verify-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | _compute_mms_body_force_lambdas, _get_mms_lambdas, mms_body_force, mms_exact_displacement, mms_exact_displacement_gradient (+2) |
| `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | _shape_grad_reference, element_internal_force, element_tangent_matvec, assemble_internal_force, _assemble_tangent_matvec (+2) |
| `packages/mechdsl-core/tests/test_convergence.py` | test_mms_body_force_substitution |

## Entry Points

Start here when exploring this area:

- **`test_mms_body_force_substitution`** (Function) — `packages/mechdsl-core/tests/test_convergence.py:302`
- **`mms_body_force`** (Function) — `packages/mechdsl-core/src/mechdsl/verify/convergence.py:246`
- **`mms_exact_displacement`** (Function) — `packages/mechdsl-core/src/mechdsl/verify/convergence.py:265`
- **`mms_exact_displacement_gradient`** (Function) — `packages/mechdsl-core/src/mechdsl/verify/convergence.py:282`
- **`verify_mms_body_force_substitution`** (Function) — `packages/mechdsl-core/src/mechdsl/verify/convergence.py:549`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_mms_body_force_substitution` | Function | `packages/mechdsl-core/tests/test_convergence.py` | 302 |
| `mms_body_force` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 246 |
| `mms_exact_displacement` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 265 |
| `mms_exact_displacement_gradient` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 282 |
| `verify_mms_body_force_substitution` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 549 |
| `element_internal_force` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 58 |
| `element_tangent_matvec` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 98 |
| `assemble_internal_force` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 145 |
| `residual_fn` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 250 |
| `tangent_fn` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 253 |
| `_compute_mms_body_force_lambdas` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 131 |
| `_get_mms_lambdas` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 238 |
| `_P` | Function | `packages/mechdsl-core/src/mechdsl/verify/convergence.py` | 566 |
| `_shape_grad_reference` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 35 |
| `_assemble_tangent_matvec` | Function | `packages/mechdsl-core/src/mechdsl/verify/_assembly.py` | 182 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Residual_fn → Gradient` | cross_community | 5 |
| `Residual_fn → Right_cauchy_green` | cross_community | 5 |
| `Tangent_fn → Gradient` | cross_community | 5 |
| `Run_mms_convergence → _compute_mms_body_force_lambdas` | cross_community | 4 |
| `Residual_fn → Deformation_gradient` | cross_community | 4 |
| `Tangent_fn → Material_tangent_4th` | cross_community | 4 |
| `Tangent_fn → SVKMaterial` | cross_community | 4 |
| `Tangent_fn → Deformation_gradient` | cross_community | 4 |
| `Mms_body_force → _compute_mms_body_force_lambdas` | intra_community | 3 |
| `Mms_exact_displacement → _compute_mms_body_force_lambdas` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 7 calls |

## How to Explore

1. `gitnexus_context({name: "test_mms_body_force_substitution"})` — see callers and callees
2. `gitnexus_query({query: "verify"})` — find related execution flows
3. Read key files listed above for implementation details
