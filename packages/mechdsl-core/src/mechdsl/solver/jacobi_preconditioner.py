"""Generated Jacobi (point-diagonal) preconditioner adapter (PlanJune14 P4-1).

This module provides :class:`GeneratedJacobiPreconditioner`, which realises
the Jacobi ``M^{-1} r`` algorithm authored in ``dev/algorithms/jacobi.tex``
and injects it through the ``ti_runtime`` ``set_preconditioner`` seam.

Algorithm (from ``dev/algorithms/jacobi.tex``)
----------------------------------------------
Given:
  r   — residual vector (numerator, ti.Vector.field)
  d   — diagonal vector (denominator, ti.Vector.field, same layout as r)
  eps — small positive guard (default 1e-12)

Compute:
  z_I = r_I / max(d_I, eps)   for all DOF indices I

This is the point-Jacobi preconditioner:  M = diag(d),  M^{-1} r = r / d.

Grammar gap and body realisation
---------------------------------
algo2code's current grammar lowers ``z = r / d`` (vector / vector) to the
Python expression ``z = (r / d)``, which is not runnable for
``ti.Vector.field`` operands (Taichi raises TypeError at field-division time).
The grammar covers scalar arithmetic and vector +/-/scale/callable-matvec but
has no ``vec_ediv`` (elementwise divide) primitive.

The body is therefore realised as a structured adapter that:
  1. Calls ``ti_runtime.vector_ops.ediv(z, r, d, eps)`` — the minimal new
     primitive added to ``ti_runtime`` for this purpose.
  2. Subclasses ``PreconditionerBase`` so it is injectable via
     ``LinearSolveContext.set_preconditioner(...)`` without modifying seams.py.

When algo2code gains a ``vec_ediv`` primitive, the adapter body can be fully
auto-generated from the ``.tex`` source.

Seam contract
-------------
``PreconditionerBase.apply(z, r)`` sets ``z = M^{-1} r``.
:class:`GeneratedJacobiPreconditioner` satisfies this: ``apply(z, r)``
delegates to ``ti_runtime.vector_ops.ediv`` with no NumPy in the hot path.
"""

# NOTE: no ``from __future__ import annotations`` — this module is imported
# by tests that define ``@ti.kernel`` bodies, and Taichi requires *eager*
# annotation evaluation (PEP 563 would stringify ti.template() and break JIT).

import taichi as ti

from ti_runtime import vector_ops as vops
from ti_runtime.seams import PreconditionerBase


@ti.data_oriented
class GeneratedJacobiPreconditioner(PreconditionerBase):
    """Point-Jacobi preconditioner: ``z_I = r_I / max(d_I, eps)``.

    Realises the algorithm in ``dev/algorithms/jacobi.tex`` through the
    ``ti_runtime`` ``PreconditionerBase`` seam.  The hot-path apply calls
    ``ti_runtime.vector_ops.ediv`` — a ``@ti.kernel`` with no NumPy.

    Parameters
    ----------
    diag:
        A ``ti.Vector.field`` (or any Taichi field with the same layout as
        the DOF vectors) holding the diagonal entries ``d``.  For point-Jacobi
        over FEM DOFs this is one value per node (3-component for 3-D).
    eps:
        Guard for near-zero diagonal entries (default ``1e-12``).  The apply
        computes ``r[I] / max(d[I], eps)`` so the output is always finite.

    Usage
    -----
    Inject via :class:`ti_runtime.seams.LinearSolveContext`::

        precond = GeneratedJacobiPreconditioner(diag=d_field, eps=1e-12)
        ctx.set_preconditioner(precond)
        # ctx.apply_preconditioner(z, r) now calls the generated apply body.
    """

    def __init__(self, diag: ti.template(), eps: float = 1e-12) -> None:  # type: ignore[valid-type]  # Taichi runtime marker, not a static type (see module note re: eager annotations)
        self.diag = diag
        self.eps = eps

    def apply(self, z, r) -> None:
        """Set ``z = M^{-1} r`` via the elementwise Jacobi kernel.

        Calls ``ti_runtime.vector_ops.ediv(z, r, self.diag, self.eps)``
        — a single ``@ti.kernel`` with no NumPy in the hot path.
        """
        vops.ediv(z, r, self.diag, self.eps)
