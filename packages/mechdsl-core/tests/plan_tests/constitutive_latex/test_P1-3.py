"""Tests for Task P1-3: Kinematics expansion (isochoric quantities + principal stretches first-class).

These tests verify that KinematicsResult exposes isochoric quantities (F_bar, C_bar,
Ibar1, Ibar2, J) and principal stretches as first-class accessors, sourced from
invariants.py (isochoric_split, principal_stretches).

Acceptance criteria covered:
- AC1: Isochoric quantities and stretches sourced from invariants.py (no re-implementation)
- AC2: Existing kinematics tests pass unchanged
- AC3: det(F_bar)==1, Ibar1(I)==3, prod(stretches)==J verified
"""

import functools

import pytest
import sympy as sp

from mechdsl.symbolic.kinematics import compute_from_displacement_gradient


class TestTaskP1_3:
    """Tests for Task P1-3: Kinematics expansion (isochoric + stretches first-class).

    AC covered: 1, 3.
    """

    @pytest.mark.unit
    def test_ibar1_at_identity_equals_3(self):
        """Verifies: Ibar1 (first isochoric invariant of C_bar) equals 3 at identity.

        AC: det(F_bar)==1, Ibar1(I)==3, prod(stretches)==J verified.

        Passes when: KinematicsResult.ibar1 returns 3 for identity deformation.
        """
        result = compute_from_displacement_gradient(sp.zeros(3))
        assert sp.simplify(result.Ibar1 - 3) == 0

    @pytest.mark.unit
    def test_det_fbar_equals_1(self):
        """Verifies: det(F_bar) = 1 for any deformation (volume-preserving).

        AC: det(F_bar)==1, Ibar1(I)==3, prod(stretches)==J verified.

        Passes when: KinematicsResult.F_bar has unit determinant.
        """
        # Test at identity
        result_id = compute_from_displacement_gradient(sp.zeros(3))
        assert sp.simplify(result_id.F_bar.det() - 1) == 0

        # Test at a non-trivial deformation: uniaxial stretch with lambda > 0
        lam = sp.Symbol("lambda", positive=True)
        grad_u = sp.Matrix([[lam - 1, 0, 0], [0, 0, 0], [0, 0, 0]])
        result_stretch = compute_from_displacement_gradient(grad_u)
        assert sp.simplify(result_stretch.F_bar.det() - 1) == 0

    @pytest.mark.unit
    def test_product_of_principal_stretches_equals_J(self):
        """Verifies: Product of principal stretches equals J (determinant of F).

        AC: det(F_bar)==1, Ibar1(I)==3, prod(stretches)==J verified.

        Passes when: prod(KinematicsResult.principal_stretches) == KinematicsResult.J.
        """
        # Use uniaxial stretch: principal stretches are lambda, 1, 1 => product = lambda = J
        lam = sp.Symbol("lambda", positive=True)
        grad_u = sp.Matrix([[lam - 1, 0, 0], [0, 0, 0], [0, 0, 0]])
        result = compute_from_displacement_gradient(grad_u)

        product = functools.reduce(lambda a, b: a * b, result.principal_stretches)
        diff = sp.simplify(sp.expand(product - result.J))
        assert diff == 0, f"prod(stretches) - J = {diff}"

    @pytest.mark.unit
    def test_principal_stretches_preserve_multiplicity(self):
        """Verifies: principal_stretches returns one entry per spatial dimension.

        AC: stretches sourced from invariants.py without dropping eigenvalue
        multiplicity. A uniaxial state has the repeated stretch 1 with
        multiplicity 2, so the list must have length 3 (not 2). Guards the
        spectral-model (Ogden, P4-2) contract that needs exactly 3 stretches.

        Passes when: len == 3 for both a repeated-eigenvalue (uniaxial) and a
        distinct-eigenvalue (triaxial) deformation, and the product equals J in
        both cases.
        """
        l1, l2, l3 = sp.symbols("l1 l2 l3", positive=True)

        # Repeated eigenvalues: uniaxial -> stretches {lambda, 1, 1}.
        uni = compute_from_displacement_gradient(sp.Matrix([[l1 - 1, 0, 0], [0, 0, 0], [0, 0, 0]]))
        assert len(uni.principal_stretches) == 3

        # Distinct eigenvalues: triaxial.
        tri = compute_from_displacement_gradient(sp.diag(l1 - 1, l2 - 1, l3 - 1))
        assert len(tri.principal_stretches) == 3
        product = functools.reduce(lambda a, b: a * b, tri.principal_stretches)
        assert sp.simplify(sp.expand(product - tri.J)) == 0
