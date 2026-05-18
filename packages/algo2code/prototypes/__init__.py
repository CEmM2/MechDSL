"""
algo2code — LaTeX algorithmic environment → executable code transpiler.

Usage:
    from algo2code import transpile

    taichi_code = transpile(latex_source, backend='taichi')
"""
from .ast_nodes import Algorithm, VarType
from .algo_parser import parse_algorithm
from .expr_parser import parse_latex_expr
from .type_inference import infer_types
from .taichi_codegen import generate_taichi


def transpile(source: str, backend: str = 'taichi') -> str:
    """
    Full pipeline:  LaTeX source → parsed AST → type inference → code generation.

    Parameters
    ----------
    source : str
        LaTeX source containing \\begin{algorithmic} ... \\end{algorithmic}
        with optional % directive comments.
    backend : str
        Target backend. Currently only 'taichi' is supported.

    Returns
    -------
    str
        Generated source code.
    """
    # 1. Parse
    algo = parse_algorithm(source)

    # 2. Type inference
    infer_types(algo)

    # 3. Code generation
    if backend == 'taichi':
        return generate_taichi(algo)
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Supported: 'taichi'")


__all__ = [
    'transpile',
    'parse_algorithm',
    'parse_latex_expr',
    'infer_types',
    'generate_taichi',
    'Algorithm',
    'VarType',
]
