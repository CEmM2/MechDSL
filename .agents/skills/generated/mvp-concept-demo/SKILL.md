---
name: mvp-concept-demo
description: "Skill for the Mvp_concept_demo area of MechDSL. 3 symbols across 1 files."
---

# Mvp_concept_demo

3 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `mvp_concept_demo/`
- Understanding how emit_optimized_taichi_einsum, flat_idx, demonstrate_compiler work
- Modifying mvp_concept_demo-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `mvp_concept_demo/mechdsl_compiler_mvp.py` | emit_optimized_taichi_einsum, flat_idx, demonstrate_compiler |

## Entry Points

Start here when exploring this area:

- **`emit_optimized_taichi_einsum`** (Function) — `mvp_concept_demo/mechdsl_compiler_mvp.py:59`
- **`flat_idx`** (Function) — `mvp_concept_demo/mechdsl_compiler_mvp.py:113`
- **`demonstrate_compiler`** (Function) — `mvp_concept_demo/mechdsl_compiler_mvp.py:141`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `emit_optimized_taichi_einsum` | Function | `mvp_concept_demo/mechdsl_compiler_mvp.py` | 59 |
| `flat_idx` | Function | `mvp_concept_demo/mechdsl_compiler_mvp.py` | 113 |
| `demonstrate_compiler` | Function | `mvp_concept_demo/mechdsl_compiler_mvp.py` | 141 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Demonstrate_compiler → Flat_idx` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "emit_optimized_taichi_einsum"})` — see callers and callees
2. `gitnexus_query({query: "mvp_concept_demo"})` — find related execution flows
3. Read key files listed above for implementation details
