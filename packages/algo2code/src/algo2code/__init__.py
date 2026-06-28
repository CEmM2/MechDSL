"""algo2code — Transpile LaTeX algorithm boxes (algpseudocode) to executable code.

Targets: Taichi (MVP), NumPy, C/PETSc.

Usage:
    from algo2code import transpile

    taichi_code = transpile(latex_source, backend='taichi')
"""

__version__ = "0.2.0"

from .algo_parser import parse_algorithm
from .ast_nodes import Algorithm, VarType
from .backends.taichi_codegen import (
    RUNTIME_INLINE,
    RUNTIME_TI_RUNTIME,
    generate_taichi,
)
from .errors import Algo2CodeError, UnsupportedConstructError
from .expr_parser import parse_latex_expr
from .library import PCG_ALGORITHM_LATEX, get_pcg_algorithm_latex
from .type_inference import infer_types


def transpile(source: str, backend: str = "taichi", runtime: str = "inline") -> str:
    """
    Full pipeline:  LaTeX source → parsed AST → type inference → code generation.

    Parameters
    ----------
    source : str
        LaTeX source containing \\begin{algorithmic} ... \\end{algorithmic}
        with optional % directive comments.
    backend : str
        Target backend. Currently only 'taichi' is supported.
    runtime : str
        Import mode for the Taichi backend.  ``"inline"`` (default) emits
        private ``@ti.kernel`` definitions inline.  ``"ti_runtime"`` emits
        ``from ti_runtime import vector_ops as _v`` and calls the shared
        primitives for dot/norm/copy.  algo2code itself never imports
        ti_runtime regardless of this setting.

    Returns
    -------
    str
        Generated source code.
    """
    algo = parse_algorithm(source)
    infer_types(algo)

    if backend == "taichi":
        return generate_taichi(algo, runtime=runtime)
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Supported: 'taichi'")


__all__ = [
    "PCG_ALGORITHM_LATEX",
    "RUNTIME_INLINE",
    "RUNTIME_TI_RUNTIME",
    "Algo2CodeError",
    "Algorithm",
    "UnsupportedConstructError",
    "VarType",
    "generate_taichi",
    "get_pcg_algorithm_latex",
    "infer_types",
    "parse_algorithm",
    "parse_latex_expr",
    "transpile",
]
