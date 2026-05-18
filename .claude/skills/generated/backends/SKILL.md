---
name: backends
description: "Skill for the Backends area of MechDSL. 36 symbols across 1 files."
---

# Backends

36 symbols | 1 files | Cohesion: 82%

## When to Use

- Working with code in `packages/`
- Understanding how scan, emit_kernels, emit work
- Modifying backends-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | _sanitize, KernelCollector, scan, _scan_stmt, _scan_expr (+31) |

## Entry Points

Start here when exploring this area:

- **`scan`** (Function) — `packages/algo2code/src/algo2code/backends/taichi_codegen.py:95`
- **`emit_kernels`** (Function) — `packages/algo2code/src/algo2code/backends/taichi_codegen.py:144`
- **`emit`** (Function) — `packages/algo2code/src/algo2code/backends/taichi_codegen.py:227`
- **`generate_taichi`** (Function) — `packages/algo2code/src/algo2code/backends/taichi_codegen.py:564`
- **`KernelCollector`** (Class) — `packages/algo2code/src/algo2code/backends/taichi_codegen.py:89`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `KernelCollector` | Class | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 89 |
| `TaichiEmitter` | Class | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 215 |
| `scan` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 95 |
| `emit_kernels` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 144 |
| `emit` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 227 |
| `generate_taichi` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 564 |
| `_sanitize` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 66 |
| `_scan_stmt` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 99 |
| `_scan_expr` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 124 |
| `_collect_vector_vars` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 199 |
| `_collect_arg_names` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 208 |
| `_pre_scan_temps` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 253 |
| `_count_temps` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 266 |
| `_var_name` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 77 |
| `_emit_assign` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 348 |
| `_emit_expr` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 375 |
| `_emit_unary` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 389 |
| `_emit_binop` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 399 |
| `_emit_dot` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 428 |
| `_emit_matvec` | Function | `packages/algo2code/src/algo2code/backends/taichi_codegen.py` | 434 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Demo_codegen → _sanitize` | cross_community | 6 |
| `Generate_taichi → _scan_expr` | intra_community | 5 |
| `Demo_codegen → _collect_arg_names` | cross_community | 5 |
| `Demo_codegen → KernelCollector` | cross_community | 5 |
| `_emit_binop → _sanitize` | cross_community | 5 |
| `Demo_codegen → TaichiEmitter` | cross_community | 4 |
| `_emit_stmt → _sanitize` | cross_community | 4 |
| `_emit_stmt → _emit_unary` | cross_community | 4 |
| `_emit_binop → _emit_unary` | intra_community | 4 |

## How to Explore

1. `gitnexus_context({name: "scan"})` — see callers and callees
2. `gitnexus_query({query: "backends"})` — find related execution flows
3. Read key files listed above for implementation details
