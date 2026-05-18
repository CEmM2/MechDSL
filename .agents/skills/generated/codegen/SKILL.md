---
name: codegen
description: "Skill for the Codegen area of MechDSL. 21 symbols across 2 files."
---

# Codegen

21 symbols | 2 files | Cohesion: 81%

## When to Use

- Working with code in `packages/`
- Understanding how test_indent_block, test_nested_indent, emit work
- Modifying codegen-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | emit, indent_block, _IndentCtx, emit_preamble, emit_field_declarations (+14) |
| `packages/mechdsl-core/tests/test_taichi_printer.py` | test_indent_block, test_nested_indent |

## Entry Points

Start here when exploring this area:

- **`test_indent_block`** (Function) — `packages/mechdsl-core/tests/test_taichi_printer.py:337`
- **`test_nested_indent`** (Function) — `packages/mechdsl-core/tests/test_taichi_printer.py:348`
- **`emit`** (Function) — `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py:47`
- **`indent_block`** (Function) — `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py:54`
- **`emit_preamble`** (Function) — `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py:122`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_indent_block` | Function | `packages/mechdsl-core/tests/test_taichi_printer.py` | 337 |
| `test_nested_indent` | Function | `packages/mechdsl-core/tests/test_taichi_printer.py` | 348 |
| `emit` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 47 |
| `indent_block` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 54 |
| `emit_preamble` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 122 |
| `emit_field_declarations` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 178 |
| `emit_constitutive_update` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 232 |
| `emit_internal_force_kernel` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 381 |
| `emit_tangent_matvec_kernel` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 513 |
| `emit_newton_driver` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 615 |
| `emit_validate_mesh` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 780 |
| `emit_postprocess` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 821 |
| `emit` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 977 |
| `emit_constants` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 143 |
| `_IndentCtx` | Class | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 62 |
| `_emit_svk_constitutive` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 252 |
| `_emit_j2_constitutive` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 280 |
| `_fmt_float` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 79 |
| `_fmt_matrix_literal` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 86 |
| `_fmt_3d_literal` | Function | `packages/mechdsl-core/src/mechdsl/codegen/taichi_printer.py` | 97 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Emit → _fmt_float` | cross_community | 4 |
| `Emit_constitutive_update → _IndentCtx` | intra_community | 4 |
| `Emit → Emit` | intra_community | 3 |
| `Emit_constitutive_update → Emit` | intra_community | 3 |
| `Emit_field_declarations → _IndentCtx` | intra_community | 3 |
| `Emit_internal_force_kernel → _IndentCtx` | intra_community | 3 |
| `Emit_tangent_matvec_kernel → _IndentCtx` | intra_community | 3 |
| `Emit_newton_driver → _IndentCtx` | intra_community | 3 |
| `Emit_validate_mesh → _IndentCtx` | intra_community | 3 |
| `Emit_postprocess → _IndentCtx` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 7 calls |

## How to Explore

1. `gitnexus_context({name: "test_indent_block"})` — see callers and callees
2. `gitnexus_query({query: "codegen"})` — find related execution flows
3. Read key files listed above for implementation details
