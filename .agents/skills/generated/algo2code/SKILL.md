---
name: algo2code
description: "Skill for the Algo2code area of MechDSL. 57 symbols across 4 files."
---

# Algo2code

57 symbols | 4 files | Cohesion: 88%

## When to Use

- Working with code in `packages/`
- Understanding how peek, advance, expect work
- Modifying algo2code-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/algo2code/src/algo2code/algo_parser.py` | _current_line, _advance, _parse_block, _strip_comment, _extract_inline_comment (+15) |
| `packages/algo2code/src/algo2code/expr_parser.py` | peek, advance, expect, at, parse_expr (+12) |
| `packages/algo2code/src/algo2code/ast_nodes.py` | Expr, Var, Number, BinOp, UnaryOp (+9) |
| `packages/algo2code/src/algo2code/type_inference.py` | infer_algorithm, _infer_block, _infer_stmt, _infer_expr, _resolve_binop (+1) |

## Entry Points

Start here when exploring this area:

- **`peek`** (Function) — `packages/algo2code/src/algo2code/expr_parser.py:136`
- **`advance`** (Function) — `packages/algo2code/src/algo2code/expr_parser.py:141`
- **`expect`** (Function) — `packages/algo2code/src/algo2code/expr_parser.py:146`
- **`at`** (Function) — `packages/algo2code/src/algo2code/expr_parser.py:153`
- **`parse_expr`** (Function) — `packages/algo2code/src/algo2code/expr_parser.py:161`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `Expr` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 31 |
| `Var` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 38 |
| `Number` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 55 |
| `BinOp` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 65 |
| `UnaryOp` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 77 |
| `FuncCall` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 88 |
| `Return` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 146 |
| `Stmt` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 102 |
| `Assign` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 109 |
| `ForLoop` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 118 |
| `WhileLoop` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 128 |
| `Branch` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 136 |
| `Break` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 153 |
| `Algorithm` | Class | `packages/algo2code/src/algo2code/ast_nodes.py` | 163 |
| `peek` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 136 |
| `advance` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 141 |
| `expect` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 146 |
| `at` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 153 |
| `parse_expr` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 161 |
| `parse_term` | Function | `packages/algo2code/src/algo2code/expr_parser.py` | 171 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Demo_parse → _extract_brace_arg` | cross_community | 7 |
| `Demo_parse → _parse_for_range` | cross_community | 7 |
| `Demo_types → _extract_brace_arg` | cross_community | 7 |
| `Demo_types → _parse_for_range` | cross_community | 7 |
| `Demo_codegen → _current_line` | cross_community | 7 |
| `_parse_state → Advance` | cross_community | 7 |
| `Parse_base → Peek` | intra_community | 6 |
| `Demo_parse → _current_line` | cross_community | 6 |
| `Demo_parse → _strip_comment` | cross_community | 6 |
| `Demo_parse → _extract_inline_comment` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Prototypes | 4 calls |

## How to Explore

1. `gitnexus_context({name: "peek"})` — see callers and callees
2. `gitnexus_query({query: "algo2code"})` — find related execution flows
3. Read key files listed above for implementation details
