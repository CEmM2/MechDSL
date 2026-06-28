"""Tensor invariants, invariant derivatives, and isochoric/spectral kinematics.

The building blocks for invariant-based hyperelastic constitutive functions
(Neo-Hookean, Mooney-Rivlin, Ogden): principal invariants I1/I2/I3, their
closed-form derivatives, the J^{-1/3} isochoric split, and principal stretches.

Anisotropic invariants for fiber-reinforced materials are also provided:
  I4(C, a) = a·C·a  (fiber stretch squared along direction a)
  I5(C, a) = a·C²·a

with closed-form derivatives w.r.t. C (treating all components of C as
independent, the form required to match component-wise ``sympy.diff``):
  dI4/dC = a⊗a
  dI5/dC = a⊗(C·a) + (Cᵀ·a)⊗a   (reduces to a⊗(C·a) + (C·a)⊗a for symmetric C)

Adapted (sympy.Matrix-native) from the ``constkit`` toolkit
(github.com/.../Constitutive_modeling, MIT, same author). constkit's Tensor2
class hierarchy and its Voigt ``notation`` module are intentionally NOT vendored:
mechdsl's symbolic layer works on raw ``sympy.Matrix``, and ``mechdsl.symbolic.voigt``
is the authoritative Voigt implementation (constkit's ordering differs from
07-CONVENTIONS — [xx,yy,zz,yz,xz,xy] vs mechdsl's [xx,yy,zz,xy,xz,yz]).

These quantities are convention-free (scalar invariants, a standard volumetric
split), so no convention shim is needed. The closed-form ``invariant_derivative``
is preferred over component-wise ``sympy.diff`` of a symmetric tensor, which
double-counts off-diagonal components (see mechdsl.symbolic.energy for the
symmetric-strain handling used when differentiating an energy directly).
"""

from __future__ import annotations

import sympy as sp

__all__ = [
    "i1",
    "i2",
    "i3",
    "i4",
    "i4_derivative",
    "i5",
    "i5_derivative",
    "invariant_derivative",
    "isochoric_split",
    "principal_stretches",
]


def i1(A: sp.Matrix) -> sp.Expr:
    """First principal invariant: I1 = tr(A)."""
    return A.trace()


def i2(A: sp.Matrix) -> sp.Expr:
    """Second principal invariant: I2 = 1/2 [(tr A)^2 - tr(A^2)]."""
    return sp.Rational(1, 2) * (A.trace() ** 2 - (A * A).trace())


def i3(A: sp.Matrix) -> sp.Expr:
    """Third principal invariant: I3 = det(A)."""
    return A.det()


def invariant_derivative(n: int, A: sp.Matrix) -> sp.Matrix:
    """Closed-form derivative of the n-th principal invariant w.r.t. ``A``.

    ``dI1/dA = I``; ``dI2/dA = I1 I - A^T``; ``dI3/dA = det(A) A^{-T} = cof(A)``.

    Using these closed forms (rather than differentiating an invariant
    expression component-by-component) avoids the symmetric-tensor
    double-counting trap.
    """
    eye = sp.eye(A.rows)
    if n == 1:
        return eye
    if n == 2:
        return A.trace() * eye - A.T
    if n == 3:
        return A.det() * A.inv().T
    raise ValueError(f"n must be 1, 2, or 3, got {n}")


def i4(C: sp.Matrix, a: sp.Matrix) -> sp.Expr:
    """Fourth anisotropic invariant: I4 = a · C · a.

    Args:
        C: 3×3 right Cauchy-Green tensor (sympy.Matrix).
        a: 3-vector fiber direction (sympy.Matrix, column or row).

    Returns:
        Scalar sympy expression for the fiber stretch squared.
    """
    a_col = sp.Matrix(a).reshape(3, 1)
    return (a_col.T @ C @ a_col)[0, 0]


def i5(C: sp.Matrix, a: sp.Matrix) -> sp.Expr:
    """Fifth anisotropic invariant: I5 = a · C² · a.

    Args:
        C: 3×3 right Cauchy-Green tensor (sympy.Matrix).
        a: 3-vector fiber direction (sympy.Matrix, column or row).

    Returns:
        Scalar sympy expression.
    """
    a_col = sp.Matrix(a).reshape(3, 1)
    return (a_col.T @ C @ C @ a_col)[0, 0]


def i4_derivative(C: sp.Matrix, a: sp.Matrix) -> sp.Matrix:
    """Closed-form derivative dI4/dC = a ⊗ a.

    Using the closed form avoids the symmetric-tensor double-counting trap
    that arises when differentiating component-by-component.

    Args:
        C: 3×3 right Cauchy-Green tensor (sympy.Matrix). Unused — dI4/dC is
           independent of C; accepted for API symmetry with ``i5_derivative``.
        a: 3-vector fiber direction (sympy.Matrix, column or row).

    Returns:
        3×3 sympy.Matrix representing dI4/dC.
    """
    a_col = sp.Matrix(a).reshape(3, 1)
    return a_col @ a_col.T


def i5_derivative(C: sp.Matrix, a: sp.Matrix) -> sp.Matrix:
    """Closed-form derivative dI5/dC = a ⊗ (C·a) + (Cᵀ·a) ⊗ a.

    Derived by index-differentiating I5 = a_i C_{ij} C_{jk} a_k w.r.t. C_{rs}:

        dI5/dC_{rs} = a_r (C·a)_s + (Cᵀ·a)_r a_s

    When C is symmetric (Cᵀ = C, as it always is for the right Cauchy-Green
    tensor in mechanics) this reduces to the standard symmetrised expression
    ``a ⊗ (C·a) + (C·a) ⊗ a``, which is symmetric in (r,s). The general form
    with Cᵀ is used here so that it also matches component-wise ``sympy.diff``
    on a non-symmetric C (e.g. oracle tests), following the same closed-form
    discipline as ``invariant_derivative``.

    Args:
        C: 3×3 right Cauchy-Green tensor (sympy.Matrix).
        a: 3-vector fiber direction (sympy.Matrix, column or row).

    Returns:
        3×3 sympy.Matrix representing dI5/dC.
    """
    a_col = sp.Matrix(a).reshape(3, 1)
    Ca = C @ a_col
    CTa = C.T @ a_col
    return a_col @ Ca.T + CTa @ a_col.T


def isochoric_split(F: sp.Matrix) -> dict[str, sp.Expr | sp.Matrix]:
    """Isochoric (volumetric/deviatoric) split ``F = J^{1/3} F_bar`` with
    ``det(F_bar) = 1``.

    Returns a dict with keys ``"F_bar"`` (isochoric deformation gradient),
    ``"J"`` (Jacobian det F), and ``"C_bar" = F_bar^T F_bar`` (isochoric right
    Cauchy-Green). ``Ibar1 = tr(C_bar)`` and ``Ibar2 = i2(C_bar)`` follow.
    """
    J = sp.simplify(F.det())
    F_bar = sp.simplify(J ** sp.Rational(-1, 3) * F)
    C_bar = sp.simplify(F_bar.T @ F_bar)
    return {"F_bar": F_bar, "J": J, "C_bar": C_bar}


def principal_stretches(F: sp.Matrix) -> list[sp.Expr]:
    """Principal stretches ``lambda_i = sqrt(eig_i(C))`` with ``C = F^T F``.

    Always returns one stretch per spatial dimension (3 for a 3×3 ``F``):
    eigenvalues are expanded by algebraic multiplicity, so a repeated stretch
    (e.g. equibiaxial or uniaxial states) appears the correct number of times
    rather than being collapsed to a single entry. Downstream spectral models
    (Ogden) rely on the full-length list.

    Eigenvalues are returned in a deterministic order (``sp.default_sort_key``)
    because ``C.eigenvals()`` does not guarantee a stable iteration order across
    SymPy versions; a stable order keeps spectral codegen and tests reproducible.
    """
    C = F.T @ F
    ordered = sorted(C.eigenvals().items(), key=lambda item: sp.default_sort_key(item[0]))
    return [
        sp.simplify(sp.sqrt(value)) for value, multiplicity in ordered for _ in range(multiplicity)
    ]
