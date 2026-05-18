---
name: prototypes
description: "Skill for the Prototypes area of MechDSL. 214 symbols across 19 files."
---

# Prototypes

214 symbols | 19 files | Cohesion: 86%

## When to Use

- Working with code in `packages/`
- Understanding how test_number, test_variable, test_greek_var work
- Modifying prototypes-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/algo2code/prototypes/test_algo2code.py` | test_number, test_variable, test_greek_var, test_addition, test_subtraction (+37) |
| `packages/algo2code/prototypes/taichi_codegen.py` | _var_name, _emit_assign, _emit_expr, _emit_unary, _emit_binop (+31) |
| `packages/algo2code/tests/test_expr_parser.py` | test_number, test_variable, test_greek_var, test_addition, test_subtraction (+18) |
| `packages/algo2code/prototypes/expr_parser.py` | peek, advance, expect, at, parse_expr (+18) |
| `packages/algo2code/prototypes/algo_parser.py` | _current_line, _advance, _parse_block, _strip_comment, _extract_inline_comment (+17) |
| `packages/algo2code/prototypes/ast_nodes.py` | Expr, Var, Number, BinOp, UnaryOp (+9) |
| `packages/algo2code/tests/test_algo_parser.py` | test_parses_name, test_parses_backend, test_parses_args, test_parses_type_directives, test_body_structure (+3) |
| `packages/algo2code/prototypes/type_inference.py` | infer_algorithm, _infer_block, _infer_stmt, _infer_expr, _resolve_binop (+3) |
| `packages/algo2code/src/algo2code/expr_parser.py` | ExprParser, parse, parse_latex_expr, Token, tokenize (+1) |
| `packages/algo2code/tests/test_taichi_codegen.py` | test_code_has_imports, test_code_has_kernels, test_code_has_driver, test_code_has_matvec, test_code_has_convergence_check (+1) |

## Entry Points

Start here when exploring this area:

- **`test_number`** (Function) — `packages/algo2code/prototypes/test_algo2code.py:56`
- **`test_variable`** (Function) — `packages/algo2code/prototypes/test_algo2code.py:61`
- **`test_greek_var`** (Function) — `packages/algo2code/prototypes/test_algo2code.py:66`
- **`test_addition`** (Function) — `packages/algo2code/prototypes/test_algo2code.py:71`
- **`test_subtraction`** (Function) — `packages/algo2code/prototypes/test_algo2code.py:76`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `ExprParser` | Class | `packages/algo2code/src/algo2code/expr_parser.py` | 113 |
| `Expr` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 29 |
| `Var` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 35 |
| `Number` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 51 |
| `BinOp` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 60 |
| `UnaryOp` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 71 |
| `FuncCall` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 81 |
| `AlgPseudocodeParser` | Class | `packages/algo2code/src/algo2code/algo_parser.py` | 96 |
| `Return` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 132 |
| `Token` | Class | `packages/algo2code/src/algo2code/expr_parser.py` | 73 |
| `KernelCollector` | Class | `packages/algo2code/prototypes/taichi_codegen.py` | 56 |
| `TypeInferrer` | Class | `packages/algo2code/src/algo2code/type_inference.py` | 34 |
| `Token` | Class | `packages/algo2code/prototypes/expr_parser.py` | 72 |
| `ExprParser` | Class | `packages/algo2code/prototypes/expr_parser.py` | 108 |
| `AlgPseudocodeParser` | Class | `packages/algo2code/prototypes/algo_parser.py` | 85 |
| `Stmt` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 93 |
| `Assign` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 99 |
| `ForLoop` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 107 |
| `WhileLoop` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 116 |
| `Branch` | Class | `packages/algo2code/prototypes/ast_nodes.py` | 123 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _extract_brace_arg` | cross_community | 8 |
| `Main → _parse_for_range` | cross_community | 8 |
| `Infer_types → _resolve_multiply` | cross_community | 7 |
| `Demo_parse → _extract_brace_arg` | cross_community | 7 |
| `Demo_parse → _parse_for_range` | cross_community | 7 |
| `Demo_types → _extract_brace_arg` | cross_community | 7 |
| `Demo_types → _parse_for_range` | cross_community | 7 |
| `Main → _current_line` | cross_community | 7 |
| `Main → _strip_comment` | cross_community | 7 |
| `Main → _extract_inline_comment` | cross_community | 7 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Algo2code | 3 calls |
| Backends | 1 calls |

## How to Explore

1. `gitnexus_context({name: "test_number"})` — see callers and callees
2. `gitnexus_query({query: "prototypes"})` — find related execution flows
3. Read key files listed above for implementation details
