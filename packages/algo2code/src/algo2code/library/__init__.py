"""Curated library of canonical algorithm sources shipped with ``algo2code``.

Each module in this subpackage exposes a single LaTeX algorithm text plus a
small helper that returns it (and, where the parser supports it, the parsed
:class:`~algo2code.ast_nodes.Algorithm`).  Downstream packages import from
here instead of re-typing or re-inventing the algorithm text — this is the
canonical hand-off seam between ``algo2code`` and any consumer that wants a
reference implementation of a textbook iterative solver.
"""

from algo2code.library.pcg import (
    PCG_ALGORITHM_LATEX,
    get_pcg_algorithm_latex,
)

__all__ = [
    "PCG_ALGORITHM_LATEX",
    "get_pcg_algorithm_latex",
]
