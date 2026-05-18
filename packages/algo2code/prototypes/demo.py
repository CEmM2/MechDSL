#!/usr/bin/env python3
"""
Demo: LaTeX algorithmic box → Taichi code

Reads the PCG algorithm from examples/pcg.tex and generates
a runnable Taichi solver.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from algo2code import transpile, parse_algorithm, infer_types
from algo2code.ast_nodes import ForLoop, Branch, Assign, Return, VarType


def demo_parse():
    """Show the parsed AST structure."""
    with open('examples/pcg.tex') as f:
        source = f.read()

    algo = parse_algorithm(source)
    print("=" * 70)
    print("  PARSED ALGORITHM")
    print("=" * 70)
    print(f"  Name:    {algo.name}")
    print(f"  Backend: {algo.backend}")
    print(f"  Args:    {[(n, t.name) for n, t in algo.args]}")
    print(f"  Types:   {dict((k, v.name) for k, v in algo.type_annotations.items())}")
    print()

    def show_stmt(stmt, depth=1):
        prefix = "    " * depth
        if isinstance(stmt, Assign):
            from algo2code.taichi_codegen import _var_name
            t = _var_name(stmt.target)
            print(f"{prefix}Assign: {t} = <expr>")
        elif isinstance(stmt, ForLoop):
            print(f"{prefix}For {stmt.var} = {stmt.start}..{stmt.end_expr}:")
            for s in stmt.body:
                show_stmt(s, depth + 1)
        elif isinstance(stmt, Branch):
            print(f"{prefix}If <condition>:")
            for s in stmt.if_body:
                show_stmt(s, depth + 1)
        elif isinstance(stmt, Return):
            print(f"{prefix}Return ({len(stmt.values)} values)")
        else:
            print(f"{prefix}{type(stmt).__name__}")

    print("  Body:")
    for stmt in algo.body:
        show_stmt(stmt)
    print()


def demo_types():
    """Show type inference results."""
    with open('examples/pcg.tex') as f:
        source = f.read()

    algo = parse_algorithm(source)
    infer_types(algo)

    print("=" * 70)
    print("  TYPE INFERENCE RESULTS")
    print("=" * 70)
    for name, vtype in sorted(algo.type_annotations.items()):
        print(f"    {name:20s} → {vtype.name}")
    print()


def demo_codegen():
    """Show the generated Taichi code."""
    with open('examples/pcg.tex') as f:
        source = f.read()

    code = transpile(source, backend='taichi')

    print("=" * 70)
    print("  GENERATED TAICHI CODE")
    print("=" * 70)
    for i, line in enumerate(code.split('\n'), 1):
        print(f"  {i:3d} │ {line}")
    print()

    # Verify syntax
    try:
        compile(code, '<generated>', 'exec')
        print("  ✓ Generated code is syntactically valid Python")
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
    print()


if __name__ == '__main__':
    demo_parse()
    demo_types()
    demo_codegen()
