---
name: ref
description: "Skill for the Ref area of MechDSL. 14 symbols across 6 files."
---

# Ref

14 symbols | 6 files | Cohesion: 63%

## When to Use

- Working with code in `packages/`
- Understanding how test_fd_tangent_vs_direct, tangent_mv, element_tangent_matvec work
- Modifying ref-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` | _shape_grad_reference, element_tangent_matvec, apply_tangent_matvec, matvec |
| `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | _shape_grad_reference, element_tangent_matvec_plastic, apply_tangent_matvec_plastic, matvec |
| `packages/mechdsl-core/tests/test_newton.py` | _raw_global_matvec, tangent_mv, _raw_plastic_matvec |
| `packages/mechdsl-core/tests/test_ref_elastic.py` | test_fd_tangent_vs_direct |
| `packages/mechdsl-core/tests/test_benchmarks.py` | matvec |
| `packages/mechdsl-core/tests/generate_golden.py` | matvec |

## Entry Points

Start here when exploring this area:

- **`test_fd_tangent_vs_direct`** (Function) — `packages/mechdsl-core/tests/test_ref_elastic.py:316`
- **`tangent_mv`** (Function) — `packages/mechdsl-core/tests/test_newton.py:149`
- **`element_tangent_matvec`** (Function) — `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py:191`
- **`apply_tangent_matvec`** (Function) — `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py:293`
- **`matvec`** (Function) — `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py:466`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_fd_tangent_vs_direct` | Function | `packages/mechdsl-core/tests/test_ref_elastic.py` | 316 |
| `tangent_mv` | Function | `packages/mechdsl-core/tests/test_newton.py` | 149 |
| `element_tangent_matvec` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` | 191 |
| `apply_tangent_matvec` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` | 293 |
| `matvec` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` | 466 |
| `matvec` | Function | `packages/mechdsl-core/tests/test_benchmarks.py` | 934 |
| `matvec` | Function | `packages/mechdsl-core/tests/generate_golden.py` | 373 |
| `element_tangent_matvec_plastic` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | 163 |
| `apply_tangent_matvec_plastic` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | 280 |
| `matvec` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | 460 |
| `_raw_global_matvec` | Function | `packages/mechdsl-core/tests/test_newton.py` | 36 |
| `_shape_grad_reference` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_elastic.py` | 97 |
| `_raw_plastic_matvec` | Function | `packages/mechdsl-core/tests/test_newton.py` | 322 |
| `_shape_grad_reference` | Function | `packages/mechdsl-core/tests/ref/ref_hex8_plastic.py` | 68 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Gradient` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 12 calls |

## How to Explore

1. `gitnexus_context({name: "test_fd_tangent_vs_direct"})` — see callers and callees
2. `gitnexus_query({query: "ref"})` — find related execution flows
3. Read key files listed above for implementation details
