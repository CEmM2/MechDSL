"""Oracle tests for the vendored invariant/isochoric machinery.

Vets the constkit-derived functions in mechdsl.symbolic.invariants against
SymPy ground truth, per the 'oracle-gated' vendoring decision: nothing is
trusted until it reproduces a known result.
"""

from __future__ import annotations

import sympy as sp

from mechdsl.symbolic.invariants import (
    i1,
    i2,
    i3,
    invariant_derivative,
    isochoric_split,
    principal_stretches,
)


def _symbolic_F() -> sp.Matrix:
    f = sp.symbols("f0:9", real=True)
    return sp.Matrix(3, 3, f)


def test_invariants_of_identity():
    eye = sp.eye(3)
    assert i1(eye) == 3
    assert i2(eye) == 3
    assert i3(eye) == 1


def test_i3_of_C_equals_J_squared():
    """det(C) = det(F^T F) = (det F)^2 = J^2."""
    F = _symbolic_F()
    C = F.T @ F
    J = F.det()
    assert sp.simplify(i3(C) - J**2) == 0


def test_invariant_derivatives_match_sympy_diff():
    """Closed-form dI_n/dA must equal component-wise sympy.diff at a numeric A.

    A is a generic (non-symmetric) matrix so the closed forms (which assume
    independent components) are the correct ground truth.
    """
    a = sp.symbols("a0:9", real=True)
    A = sp.Matrix(3, 3, a)
    subs = {a[k]: v for k, v in enumerate([4, 1, 2, 0, 5, 1, 3, 2, 6])}

    for n, inv in ((1, i1), (2, i2), (3, i3)):
        closed = invariant_derivative(n, A)
        scalar = inv(A)
        for r in range(3):
            for c in range(3):
                diffed = sp.diff(scalar, A[r, c])
                assert sp.simplify((closed[r, c] - diffed).subs(subs)) == 0


def test_isochoric_split_is_volume_preserving():
    F = _symbolic_F()
    split = isochoric_split(F)
    # det(F_bar) = 1 by construction.
    assert sp.simplify(split["F_bar"].det() - 1) == 0
    # C_bar = F_bar^T F_bar.
    assert sp.simplify(split["C_bar"] - split["F_bar"].T @ split["F_bar"]) == sp.zeros(3, 3)
    # J recovered as det F.
    assert sp.simplify(split["J"] - F.det()) == 0


def test_isochoric_invariant_ibar1_at_identity():
    """For F = I: J = 1, F_bar = I, Ibar1 = tr(C_bar) = 3."""
    split = isochoric_split(sp.eye(3))
    assert split["J"] == 1
    assert i1(split["C_bar"]) == 3


def test_principal_stretches_product_equals_J():
    """Product of principal stretches equals J for a diagonal stretch."""
    l1, l2, l3 = sp.symbols("l1 l2 l3", positive=True)
    F = sp.diag(l1, l2, l3)
    stretches = principal_stretches(F)
    assert sp.simplify(sp.prod(stretches) - F.det()) == 0
