"""Symbolic kinematics: deformation gradient and derived kinematic quantities.

Computes F, C, E, J, F_inv, F_invT, and the convected metric g from
displacement gradient symbols. All results are SymPy symbolic matrices.

Isochoric quantities (F_bar, C_bar, Ibar1, Ibar2) and principal stretches are
exposed as lazy cached properties; they are computed on first access and memoised
for subsequent calls. The underlying math is sourced exclusively from
``mechdsl.symbolic.invariants`` — no duplication.

Convention reminders (from 07-CONVENTIONS.md):
    - Spatial indices:  lowercase i, j, k, l
    - Material indices: uppercase I, J, K, L
    - Deformation gradient: F_{iI} = delta_{iI} + du_i / dX_I  (two-point tensor)
    - Right Cauchy-Green: C_{IJ} = F_{kI} F_{kJ}
    - Green-Lagrange strain: E_{IJ} = (C_{IJ} - delta_{IJ}) / 2
    - Convected metric: g_{IJ} = C_{IJ}
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import sympy as sp

from mechdsl.symbolic.invariants import i1, i2, isochoric_split
from mechdsl.symbolic.invariants import principal_stretches as _principal_stretches

_MVP_DIM = 3


@dataclass(frozen=True)
class KinematicsResult:
    """Immutable container for all kinematic quantities derived from F.

    Core fields (always computed, stored at construction time):
        F, C, J, E, F_inv, F_invT, g

    Isochoric / spectral quantities (lazy cached properties, computed on first
    access from ``invariants.py`` — no duplicated math):
        F_bar, C_bar, Ibar1, Ibar2, principal_stretches
    """

    F: sp.Matrix  # Deformation gradient (3x3)
    C: sp.Matrix  # Right Cauchy-Green: C = F^T F
    J: sp.Expr  # Jacobian: J = det(F)
    E: sp.Matrix  # Green-Lagrange strain: E = (C - I) / 2
    F_inv: sp.Matrix  # Inverse of F
    F_invT: sp.Matrix  # Inverse transpose of F
    g: sp.Matrix  # Convected metric: g = C

    # ------------------------------------------------------------------
    # Isochoric / spectral quantities — lazy, sourced from invariants.py
    # ------------------------------------------------------------------

    @cached_property
    def _isochoric(self) -> dict[str, sp.Expr | sp.Matrix]:
        """Internal cache: calls invariants.isochoric_split once."""
        return isochoric_split(self.F)

    @cached_property
    def F_bar(self) -> sp.Matrix:
        """Isochoric deformation gradient: F_bar = J^{-1/3} F, det(F_bar) = 1."""
        return self._isochoric["F_bar"]  # type: ignore[return-value]

    @cached_property
    def C_bar(self) -> sp.Matrix:
        """Isochoric right Cauchy-Green tensor: C_bar = F_bar^T F_bar."""
        return self._isochoric["C_bar"]  # type: ignore[return-value]

    @cached_property
    def Ibar1(self) -> sp.Expr:
        """First isochoric invariant: Ibar1 = tr(C_bar) = i1(C_bar)."""
        return i1(self.C_bar)

    @cached_property
    def Ibar2(self) -> sp.Expr:
        """Second isochoric invariant: Ibar2 = i2(C_bar)."""
        return i2(self.C_bar)

    @cached_property
    def principal_stretches(self) -> list[sp.Expr]:
        """Principal stretches lambda_i = sqrt(eig_i(C)), sourced from invariants.py.

        Always three entries (one per spatial dimension, repeats included) in a
        deterministic order — the contract the spectral models (Ogden, P4-2) need.
        """
        return _principal_stretches(self.F)


def _kinematic_quantities(F: sp.Matrix) -> KinematicsResult:
    """Compute all kinematic quantities from a 3x3 deformation gradient.

    This is the shared implementation used by both public entry points.
    """
    dim = F.rows
    if dim != _MVP_DIM or F.cols != _MVP_DIM:
        msg = f"Deformation gradient must be {_MVP_DIM}x{_MVP_DIM}, got {F.rows}x{F.cols}"
        raise ValueError(msg)

    I3 = sp.eye(dim)

    C = sp.simplify(F.T @ F)
    J = sp.simplify(F.det())
    E = sp.simplify((C - I3) / 2)
    F_inv = sp.simplify(F.inv())
    F_invT = sp.simplify(F_inv.T)
    g = C  # convected metric coincides with C in Total Lagrangian

    return KinematicsResult(F=F, C=C, J=J, E=E, F_inv=F_inv, F_invT=F_invT, g=g)


def compute(
    dim: int,
    u_symbols: list[list[sp.Symbol]],
    X_symbols: list[sp.Symbol],
) -> KinematicsResult:
    """Compute kinematics from displacement gradient symbols.

    Args:
        dim: spatial dimension (must be 3 for MVP).
        u_symbols: displacement gradient components — ``u_symbols[i][J]``
            represents du_i / dX_J.
        X_symbols: material coordinate symbols ``[X, Y, Z]`` (reserved for
            future use when symbolic differentiation is needed).

    Returns:
        KinematicsResult with all kinematic quantities.

    Raises:
        ValueError: if *dim* is not 3 (MVP restriction) or if the shape of
            *u_symbols* does not match *dim*.
    """
    if dim != _MVP_DIM:
        msg = (
            f"Only dim={_MVP_DIM} is supported in the MVP. "
            "2D support is planned for Plan B phase B2."
        )
        raise ValueError(msg)

    if len(u_symbols) != dim or any(len(row) != dim for row in u_symbols):
        msg = f"u_symbols must be {dim}x{dim}, got {len(u_symbols)} rows"
        raise ValueError(msg)

    # Build F = I + grad(u)
    I3 = sp.eye(dim)
    grad_u = sp.Matrix([[u_symbols[i][J] for J in range(dim)] for i in range(dim)])
    F = I3 + grad_u

    return _kinematic_quantities(F)


def compute_from_displacement_gradient(grad_u: sp.Matrix) -> KinematicsResult:
    """Compute kinematics directly from a 3x3 displacement gradient matrix.

    This is a convenience wrapper for callers that already have grad_u assembled.

    Args:
        grad_u: 3x3 SymPy matrix of du_i / dX_J.

    Returns:
        KinematicsResult with all kinematic quantities.

    Raises:
        ValueError: if *grad_u* is not 3x3.
    """
    if grad_u.rows != _MVP_DIM or grad_u.cols != _MVP_DIM:
        msg = (
            f"grad_u must be {_MVP_DIM}x{_MVP_DIM}, "
            f"got {grad_u.rows}x{grad_u.cols}. "
            "Only dim=3 is supported in the MVP."
        )
        raise ValueError(msg)

    F = sp.eye(_MVP_DIM) + grad_u
    return _kinematic_quantities(F)
