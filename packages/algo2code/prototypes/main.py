"""
algo2code: LaTeX algpseudocode → Taichi transpiler

Usage:
    python main.py examples/pcg.tex [-o output.py]
    python main.py examples/pcg.tex --dump-ast
"""
from __future__ import annotations
import argparse
import sys
from algo_parser import parse_algorithm
from taichi_gen import generate_taichi


def transpile(latex_source: str, dump_ast: bool = False) -> str:
    """
    Full pipeline: LaTeX source → Taichi Python code.

    Steps:
      1. Parse % directives and algorithmic body into AlgorithmDef AST
      2. Generate Taichi code from AST
    """
    algo = parse_algorithm(latex_source)

    if dump_ast:
        _print_ast(algo)
        return ""

    return generate_taichi(algo)


def _print_ast(algo, indent=0):
    """Pretty-print the AST for debugging."""
    pad = "  " * indent
    print(f"{pad}AlgorithmDef(name={algo.name!r}, backend={algo.backend!r})")
    print(f"{pad}  args: {algo.args}")
    print(f"{pad}  type_env: {algo.type_env}")
    print(f"{pad}  body:")
    _print_block(algo.body, indent + 2)


def _print_block(block, indent):
    from ast_nodes import Assign, Return, Break, ForLoop, WhileLoop, Branch
    pad = "  " * indent
    for stmt in block.stmts:
        if isinstance(stmt, Assign):
            print(f"{pad}Assign({stmt.lhs} = {stmt.rhs})")
        elif isinstance(stmt, Return):
            print(f"{pad}Return({stmt.values})")
        elif isinstance(stmt, Break):
            print(f"{pad}Break")
        elif isinstance(stmt, ForLoop):
            print(f"{pad}For({stmt.var}, {stmt.start}..{stmt.end})")
            _print_block(stmt.body, indent + 1)
        elif isinstance(stmt, WhileLoop):
            print(f"{pad}While({stmt.condition})")
            _print_block(stmt.body, indent + 1)
        elif isinstance(stmt, Branch):
            print(f"{pad}If({stmt.condition})")
            _print_block(stmt.if_body, indent + 1)
        else:
            print(f"{pad}{stmt}")


def main():
    parser = argparse.ArgumentParser(
        description="Transpile LaTeX algorithmic pseudocode to Taichi code"
    )
    parser.add_argument("input", help="Input .tex file")
    parser.add_argument("-o", "--output", help="Output .py file (default: stdout)")
    parser.add_argument("--dump-ast", action="store_true",
                        help="Print AST instead of generating code")
    args = parser.parse_args()

    with open(args.input, 'r') as f:
        source = f.read()

    result = transpile(source, dump_ast=args.dump_ast)

    if result:
        if args.output:
            with open(args.output, 'w') as f:
                f.write(result)
            print(f"Written to {args.output}")
        else:
            print(result)


if __name__ == "__main__":
    main()
