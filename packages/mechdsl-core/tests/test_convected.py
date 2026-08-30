"""Tests for convected coordinate functions (Sprint 2, Phase 1, Tasks P1-T2 / P1-T3).

Covers test ID S9 from 08-VERIFICATION.md: g_IJ = C_IJ for Cartesian reference.
"""

import pytest
import sympy as sp

from mechdsl.symbolic.convected import (
    UnsupportedError,
    compute_convected_metric,
    compute_reference_metric,
    green_lagrange_convected,
)


class TestComputeReferenceMetric:
    """Tests for compute_reference_metric().

    Acceptance criteria covered: P1-T2 AC1, AC2
    """

    def test_cartesian_returns_identity(self):
        """
        Verifies: compute_reference_metric('cartesian') returns 3x3 identity.
        Acceptance criterion: returns δ_IJ (3x3 identity SymPy Matrix)
        Passes when: result == sp.eye(3)
        """
        result = compute_reference_metric(coords="cartesian")
        assert result == sp.eye(3)

    def test_non_cartesian_with_explicit_G_is_accepted(self):
        """
        Verifies: compute_reference_metric('curvilinear', G=...) is accepted (P2-1).
        After P2-1, curvilinear configs with an explicit G matrix must NOT raise.
        Acceptance criterion: returns the supplied G matrix unchanged.
        Passes when: the returned matrix equals the supplied G.
        """
        r = sp.Symbol("r", positive=True)
        G_cyl = sp.diag(1, r**2, 1)
        result = compute_reference_metric(coords="curvilinear", G=G_cyl)
        assert sp.simplify(result - G_cyl) == sp.zeros(3)

    def test_non_cartesian_without_G_raises_unsupported(self):
        """
        Verifies: compute_reference_metric('curvilinear') without G raises UnsupportedError.
        Named curvilinear coordinate systems still require an explicit G matrix.
        Acceptance criterion: raises UnsupportedError with Plan B phase B2 pointer.
        Passes when: UnsupportedError is raised with 'Plan B' in message.
        """
        with pytest.raises(UnsupportedError, match="Plan B"):
            compute_reference_metric(coords="curvilinear")


class TestComputeConvectedMetric:
    """Tests for compute_convected_metric().

    Acceptance criteria covered: P1-T2 AC3, AC5
    """

    def test_identity_F_returns_identity(self):
        """
        Verifies: At F=I, g = C = I (S9 identity case).
        Acceptance criterion: g = G = I, E = 0 at F=I
        Passes when: compute_convected_metric(sp.eye(3)) == sp.eye(3)
        """
        F = sp.eye(3)
        g = compute_convected_metric(F)
        assert sp.simplify(g - sp.eye(3)) == sp.zeros(3)

    def test_simple_shear_matches_hand_calc(self):
        """
        Verifies: For F = I + gamma * e1 x e2, g = F^T F matches hand calculation.
        Acceptance criterion: g = C for known simple shear
        Passes when: g[0,1] == gamma, g[1,1] == 1 + gamma^2, rest == identity entries
        """
        gamma = sp.Rational(1, 10)  # 0.1
        # F = I + gamma * e1 ⊗ e2: row 0 gets an off-diagonal entry in column 1
        F = sp.eye(3)
        F[0, 1] = gamma

        g = compute_convected_metric(F)

        # Hand-calculated: g = F^T F
        # F^T = [[1, 0, 0], [gamma, 1, 0], [0, 0, 1]]
        # F^T F = [[1, gamma, 0], [gamma, 1+gamma^2, 0], [0, 0, 1]]
        expected = sp.Matrix(
            [
                [1, gamma, 0],
                [gamma, 1 + gamma**2, 0],
                [0, 0, 1],
            ]
        )
        assert sp.simplify(g - expected) == sp.zeros(3)


class TestGreenLagrangeConvected:
    """Tests for green_lagrange_convected().

    Acceptance criteria covered: P1-T2 AC4, AC5
    """

    def test_identity_deformation_zero_strain(self):
        """
        Verifies: At F=I, E = 0.5*(g - G) = 0.
        Acceptance criterion: E = 0 when g = G = I
        Passes when: green_lagrange_convected(I, I) == zero matrix
        """
        I3 = sp.eye(3)
        E = green_lagrange_convected(g=I3, G=I3)
        assert sp.simplify(E - sp.zeros(3)) == sp.zeros(3)

    def test_known_strain(self):
        """
        Verifies: E = 0.5*(g - G) for known g and G values.
        Acceptance criterion: returns 0.5*(g - G)
        Passes when: result matches hand calculation
        """
        gamma = sp.Rational(1, 10)  # 0.1
        g = sp.Matrix(
            [
                [1, gamma, 0],
                [gamma, 1 + gamma**2, 0],
                [0, 0, 1],
            ]
        )
        G = sp.eye(3)

        E = green_lagrange_convected(g=g, G=G)

        expected = sp.Rational(1, 2) * (g - G)
        assert sp.simplify(E - expected) == sp.zeros(3)


class TestConvectedKinematicsConsistency:
    """Tests for consistency between convected.py and kinematics.py.

    Acceptance criteria covered: P1-T3 AC2 (S9 verification)
    """

    def test_convected_metric_matches_kinematics_g(self):
        """
        Verifies: compute_convected_metric(F) == kinematics.compute(F).g
        Acceptance criterion: Consistency with kinematics.py
        Passes when: both produce identical g matrix for same F
        """
        from mechdsl.symbolic.kinematics import compute_from_displacement_gradient

        gamma = sp.Rational(1, 10)  # 0.1 simple-shear displacement gradient
        # grad_u such that F = I + grad_u has a simple shear component
        grad_u = sp.zeros(3)
        grad_u[0, 1] = gamma  # du_1/dX_2 = gamma

        kin_result = compute_from_displacement_gradient(grad_u)

        # compute_convected_metric expects F directly
        g_from_convected = compute_convected_metric(kin_result.F)

        assert sp.simplify(kin_result.g - g_from_convected) == sp.zeros(3)
