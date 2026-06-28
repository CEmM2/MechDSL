"""Tests for Task P1-1: Anisotropic invariants i4/i5 + closed-form derivatives.

Covers: i4(C,a)=a·C·a and i5(C,a)=a·C²·a (fiber direction a) plus their
closed-form derivatives dI4/dC=a⊗a and dI5/dC=a⊗(C·a)+(C·a)⊗a (symmetrised).
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.symbolic.invariants import (
    i4,
    i4_derivative,
    i5,
    i5_derivative,
)


class TestTaskP1_1:
    """Tests for Task P1-1: Anisotropic invariants i4/i5 + derivatives. AC covered: 1,2,3."""

    @pytest.mark.unit
    def test_i4_i5_of_identity_with_axial_fiber(self) -> None:
        """Verifies: i4 and i5 of identity C with axial fiber direction.
        AC: i4/i5 and their derivatives match component-wise sympy.diff at numeric C.
        Passes when: i4(I, e_x) == 1 and i5(I, e_x) == 1."""
        eye = sp.eye(3)
        e_x = sp.Matrix([1, 0, 0])
        e_y = sp.Matrix([0, 1, 0])

        # Axial fiber along x: C=I so I4 = e_x · I · e_x = 1, I5 = e_x · I² · e_x = 1
        assert i4(eye, e_x) == 1
        assert i5(eye, e_x) == 1

        # Non-axial fiber along y: same result for identity
        assert i4(eye, e_y) == 1
        assert i5(eye, e_y) == 1

    @pytest.mark.unit
    def test_i4_i5_derivatives_vs_sympy_diff(self) -> None:
        """Verifies: Closed-form dI4/dC and dI5/dC match component-wise sympy.diff.
        AC: i4/i5 and their derivatives match component-wise sympy.diff at numeric C.
        Passes when: all components equal to numerical tolerance after substitution."""
        # Build a generic (non-symmetric) symbolic matrix so each component is
        # independent — this is the correct oracle for the closed-form derivatives.
        c = sp.symbols("c0:9", real=True)
        C = sp.Matrix(3, 3, c)
        a = sp.Matrix([1, 0, 0])  # axial fiber keeps expressions compact

        subs = {c[k]: v for k, v in enumerate([4, 1, 2, 0, 5, 1, 3, 2, 6])}

        # --- i4 ---
        scalar_i4 = i4(C, a)
        closed_i4 = i4_derivative(C, a)
        for r in range(3):
            for c_idx in range(3):
                diffed = sp.diff(scalar_i4, C[r, c_idx])
                assert sp.simplify((closed_i4[r, c_idx] - diffed).subs(subs)) == 0, (
                    f"dI4/dC[{r},{c_idx}] mismatch"
                )

        # --- i5 ---
        scalar_i5 = i5(C, a)
        closed_i5 = i5_derivative(C, a)
        for r in range(3):
            for c_idx in range(3):
                diffed = sp.diff(scalar_i5, C[r, c_idx])
                assert sp.simplify((closed_i5[r, c_idx] - diffed).subs(subs)) == 0, (
                    f"dI5/dC[{r},{c_idx}] mismatch"
                )

    @pytest.mark.unit
    def test_uniaxial_fiber_stretch_i4_equals_lambda_squared(self) -> None:
        """Verifies: Uniaxial fiber stretch case where i4 = λ_fiber².
        AC: Known fiber-stretch case: i4 of a unit-axial fiber under stretch λ equals λ².
        Passes when: i4(diag(λ, 1, 1), e_x) == λ²."""
        lam = sp.Symbol("lambda", positive=True)
        F = sp.diag(lam, 1, 1)
        C = F.T @ F  # = diag(λ², 1, 1)
        e_x = sp.Matrix([1, 0, 0])

        result = i4(C, e_x)
        assert sp.simplify(result - lam**2) == 0
