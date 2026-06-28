"""Tier-1 tensor / kinematics ``@ti.func`` helpers (PlanJune14 PJ-0).

The building blocks generated constitutive / element code calls — kept as
``@ti.func`` so they inline cheaply and don't burn JIT budget. Conventions follow
MechDSL ``dev/design_docs/07-CONVENTIONS.md``: spatial/material 3×3 tensors, Voigt
order ``[xx, yy, zz, xy, xz, yz]``, **tensorial** (unscaled shears), metric
``G = diag(1,1,1,2,2,2)``. Harvested/adapted from NumerixWeave ``ticonstit``.

These are ``@ti.func`` — call them from inside a ``@ti.kernel``.
"""

import taichi as ti

mat3 = ti.types.matrix(3, 3, ti.f64)
vec6 = ti.types.vector(6, ti.f64)


@ti.func
def identity3() -> mat3:
    return ti.Matrix.identity(ti.f64, 3)


@ti.func
def det3(A) -> ti.f64:
    """Determinant of a 3×3 matrix."""
    return A.determinant()


@ti.func
def inv3(A) -> mat3:
    """Inverse of a 3×3 matrix."""
    return A.inverse()


@ti.func
def deformation_gradient(grad_u) -> mat3:
    """``F = I + ∂u_i/∂X_J`` from the material displacement gradient (3×3)."""
    return ti.Matrix.identity(ti.f64, 3) + grad_u


@ti.func
def jacobian(F) -> ti.f64:
    """``J = det(F)``."""
    return F.determinant()


@ti.func
def right_cauchy_green(F) -> mat3:
    """``C = F^T F``."""
    return F.transpose() @ F


@ti.func
def green_lagrange(F) -> mat3:
    """``E = ½(F^T F − I)``."""
    return 0.5 * (F.transpose() @ F - ti.Matrix.identity(ti.f64, 3))


@ti.func
def trace3(A) -> ti.f64:
    return A[0, 0] + A[1, 1] + A[2, 2]


@ti.func
def deviatoric(A) -> mat3:
    """Deviatoric part ``A − (tr A / 3) I``."""
    p = (A[0, 0] + A[1, 1] + A[2, 2]) / 3.0
    return A - p * ti.Matrix.identity(ti.f64, 3)


@ti.func
def von_mises(S) -> ti.f64:
    """von Mises equivalent stress ``sqrt(3/2 · s:s)`` of a symmetric 3×3 ``S``."""
    s = deviatoric(S)
    return ti.sqrt(1.5 * (s * s).sum())


@ti.func
def to_voigt(S) -> vec6:
    """Symmetric 3×3 → Voigt-6 ``[xx, yy, zz, xy, xz, yz]`` (unscaled shears)."""
    return ti.Vector([S[0, 0], S[1, 1], S[2, 2], S[0, 1], S[0, 2], S[1, 2]], dt=ti.f64)


@ti.func
def from_voigt(v) -> mat3:
    """Voigt-6 → symmetric 3×3 (off-diagonals not doubled — tensorial)."""
    return ti.Matrix([[v[0], v[3], v[4]], [v[3], v[1], v[5]], [v[4], v[5], v[2]]], dt=ti.f64)


@ti.func
def double_contract(A, B) -> ti.f64:
    """Full tensor double contraction ``A:B`` of two 3×3 tensors."""
    return (A * B).sum()
