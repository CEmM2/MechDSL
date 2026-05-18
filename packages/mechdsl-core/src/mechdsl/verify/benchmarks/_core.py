"""Shared benchmark harness core - BenchmarkResult dataclass and post-processing helpers.

This module is the common substrate for all P10 benchmark tasks:
  - P10-4: thick cylinder (this module)
  - P10-6: Cook's membrane
  - P10-8: damage localisation
  - P10-9: (reserved)

Design constraints
------------------
- No Taichi in gate-C benchmarks. All computations use the NumPy ref solver.
- BenchmarkResult is frozen; post-processing helpers return new arrays.
- element_cauchy_stress evaluates SVK at the element centroid (xi=eta=zeta=0)
  and returns 3x3 Cauchy stress sigma = (1/J) F S F^T. P10-6/8/9 will import
  this directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature  # noqa: F401 (re-use in submodules)
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange

if TYPE_CHECKING:
    from numpy.typing import NDArray

_I3 = np.eye(3, dtype=np.float64)

# Centroid of the reference element in parametric space
_XI_CENTROID = (0.0, 0.0, 0.0)

# Shared basis (immutable, module-level singleton)
_BASIS = hex8_basis()


# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkResult:
    """Container for a single benchmark run.

    Attributes
    ----------
    displacements : NDArray, shape (N, 3)
        Nodal displacement field after convergence.
    newton_iters : int
        Total Newton iterations required to converge.
    wallclock_s : float
        Wall-clock time for the full solve (seconds).
    extras : dict[str, Any]
        Per-benchmark payload, e.g. ``hoop_stress_samples``,
        ``radial_displacement_samples``.  Keys are benchmark-specific.
    """

    displacements: NDArray  # (N, 3)
    newton_iters: int
    wallclock_s: float
    extras: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Element-level stress helper (reusable by P10-6/8/9)
# ---------------------------------------------------------------------------


def _shape_grad_at(X_elem: NDArray, xi: float, eta: float, zeta: float) -> tuple[NDArray, float]:
    """Shape function gradients dN/dX and |det J0| at a parametric point.

    Parameters
    ----------
    X_elem : (8, 3)
        Element nodal reference coordinates.
    xi, eta, zeta : float
        Parametric coordinates.

    Returns
    -------
    dN_dX : (8, 3)
        Shape function gradients w.r.t. reference coordinates.
    detJ0 : float
        Absolute value of the reference Jacobian determinant.
    """
    dN_dxi = _BASIS.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi  # (3, 3)
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = (
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at "
            f"xi=({xi},{eta},{zeta}) - check element connectivity."
        )
        raise ValueError(msg)
    dN_dX = dN_dxi @ np.linalg.inv(J0)  # (8, 3)
    return dN_dX, detJ0


def element_cauchy_stress(
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Cauchy stress tensor at the element centroid (SVK, TL formulation).

    Evaluates at the parametric centroid xi=eta=zeta=0, then pushes forward
    the PK2 stress to Cauchy:

        sigma = (1/J) F S F^T

    where J = det(F), S is the PK2 stress, and F is the deformation gradient.

    Parameters
    ----------
    u_elem : (8, 3)
        Element nodal displacements.
    X_elem : (8, 3)
        Element nodal reference coordinates.
    lam, mu : float
        Lame parameters.

    Returns
    -------
    sigma : (3, 3)
        Cauchy stress tensor at the element centroid.
    """
    xi, eta, zeta = _XI_CENTROID
    dN_dX, _ = _shape_grad_at(X_elem, xi, eta, zeta)

    grad_u = u_elem.T @ dN_dX  # (3, 3)
    F = deformation_gradient(grad_u)
    E = green_lagrange(F)
    tr_E = float(np.trace(E))
    S = lam * tr_E * _I3 + 2.0 * mu * E  # PK2

    J = float(np.linalg.det(F))
    sigma = (1.0 / J) * (F @ S @ F.T)
    return sigma  # (3, 3)
