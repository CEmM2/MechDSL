"""Tests for Task P1-2: Coordinate-system consolidation (absorb constkit into convected.py).

Covers the new additive capability absorbed from constkit `coordinates.py`:
- cylindrical_basis / spherical_basis -> metric_from_bases give the textbook metrics.
- reciprocal_bases + verify_biorthogonality (g_I . g^J = delta).
- christoffel_from_bases composes the authoritative metric-based christoffel_symbols.
- covariant_derivative_tensor2 "covariant"/"mixed" variants, plus a guarantee that the
  default "contravariant" path is byte-for-byte unchanged.
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.symbolic.convected import (
    christoffel_from_bases,
    christoffel_symbols,
    covariant_derivative_tensor2,
    cylindrical_basis,
    metric_from_bases,
    reciprocal_bases,
    spherical_basis,
    verify_biorthogonality,
)


class TestTaskP1_2:
    """Tests for Task P1-2: absorbed curvilinear constructors + tensor cov-deriv variants."""

    # --- cylindrical / spherical metric oracles ---------------------------------

    @pytest.mark.unit
    def test_cylindrical_basis_metric_is_diag_1_r2_1(self) -> None:
        """Verifies: cylindrical_basis -> metric_from_bases == diag(1, r^2, 1).
        Passes when: the computed metric equals the textbook cylindrical metric."""
        r = sp.Symbol("r", positive=True)
        phi = sp.Symbol("phi")
        g = metric_from_bases(cylindrical_basis(r, phi))
        expected = sp.diag(1, r**2, 1)
        assert sp.simplify(g - expected) == sp.zeros(3)

    @pytest.mark.unit
    def test_spherical_basis_metric_is_diag_1_R2_R2sin2(self) -> None:
        """Verifies: spherical_basis -> metric_from_bases == diag(1, R^2, R^2 sin^2 theta).
        Passes when: the computed metric equals the textbook spherical metric."""
        R = sp.Symbol("R", positive=True)
        theta = sp.Symbol("theta", positive=True)
        phi = sp.Symbol("phi")
        g = metric_from_bases(spherical_basis(R, theta, phi))
        expected = sp.diag(1, R**2, R**2 * sp.sin(theta) ** 2)
        assert sp.simplify(g - expected) == sp.zeros(3)

    # --- biorthogonality --------------------------------------------------------

    @pytest.mark.unit
    def test_biorthogonality_cylindrical_pair_true(self) -> None:
        """Verifies: reciprocal_bases of cylindrical g_I satisfies g_I . g^J = delta.
        Passes when: verify_biorthogonality returns True for the cov/contra pair."""
        r = sp.Symbol("r", positive=True)
        phi = sp.Symbol("phi")
        cov = cylindrical_basis(r, phi)
        contra = reciprocal_bases(cov)
        assert verify_biorthogonality(cov, contra) is True

    @pytest.mark.unit
    def test_biorthogonality_spherical_pair_true(self) -> None:
        """Verifies: reciprocal_bases of spherical g_I satisfies g_I . g^J = delta.
        Passes when: verify_biorthogonality returns True for the cov/contra pair."""
        R = sp.Symbol("R", positive=True)
        theta = sp.Symbol("theta", positive=True)
        phi = sp.Symbol("phi")
        cov = spherical_basis(R, theta, phi)
        contra = reciprocal_bases(cov)
        assert verify_biorthogonality(cov, contra) is True

    @pytest.mark.unit
    def test_biorthogonality_failure_raises(self) -> None:
        """Verifies: a deliberately wrong contravariant set fails the delta check.
        Passes when: verify_biorthogonality raises AssertionError."""
        r = sp.Symbol("r", positive=True)
        phi = sp.Symbol("phi")
        cov = cylindrical_basis(r, phi)
        bad_contra = cov  # covariant != contravariant for r != 1
        with pytest.raises(AssertionError, match="Biorthogonality failed"):
            verify_biorthogonality(cov, bad_contra)

    # --- christoffel_from_bases composes the authoritative implementation -------

    @pytest.mark.regression
    def test_christoffel_from_bases_matches_metric_based(self) -> None:
        """Verifies: christoffel_from_bases == christoffel_symbols(metric_from_bases(...)).
        Guards the no-duplication contract (composition, not reimplementation).
        Passes when: every component agrees."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        coords = (r, th, z)
        cov = cylindrical_basis(r, th)

        from_bases = christoffel_from_bases(cov, coords)
        from_metric = christoffel_symbols(metric_from_bases(cov), coords)

        for k in range(3):
            for i in range(3):
                for j in range(3):
                    assert sp.simplify(from_bases[k, i, j] - from_metric[k, i, j]) == 0

    @pytest.mark.unit
    def test_christoffel_from_bases_cylindrical_closed_form(self) -> None:
        """Verifies: cylindrical Christoffels from bases match the hand values.
        Gamma^r_{th,th} = -r, Gamma^th_{r,th} = Gamma^th_{th,r} = 1/r, rest 0."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        coords = (r, th, z)
        gamma = christoffel_from_bases(cylindrical_basis(r, th), coords)

        assert sp.simplify(gamma[0, 1, 1] - (-r)) == 0
        assert sp.simplify(gamma[1, 0, 1] - 1 / r) == 0
        assert sp.simplify(gamma[1, 1, 0] - 1 / r) == 0
        non_zero = {(0, 1, 1), (1, 0, 1), (1, 1, 0)}
        for k in range(3):
            for i in range(3):
                for j in range(3):
                    if (k, i, j) not in non_zero:
                        assert sp.simplify(gamma[k, i, j]) == 0

    # --- covariant_derivative_tensor2 variants ---------------------------------

    @pytest.mark.regression
    def test_tensor2_contravariant_default_unchanged(self) -> None:
        """Verifies: the default path equals an explicit variant='contravariant' call,
        and matches the legacy inline formula. Guards the load-bearing default path."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        theta = (r, th, z)
        gamma = christoffel_symbols(sp.diag(1, r**2, 1), theta)
        T = sp.Matrix([[r, 0, 0], [0, sp.S.Zero, 0], [0, 0, 0]])

        default = covariant_derivative_tensor2(T, gamma, theta)
        explicit = covariant_derivative_tensor2(T, gamma, theta, variant="contravariant")

        # default == explicit contravariant
        for I in range(3):
            for J in range(3):
                for K in range(3):
                    assert default[I, J, K] == explicit[I, J, K]

        # default matches the legacy inline contravariant formula exactly
        for I in range(3):
            for J in range(3):
                for K in range(3):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(3):
                        val = val + gamma[J, I, L] * T[L, K] + gamma[K, I, L] * T[J, L]
                    assert default[I, J, K] == val

    @pytest.mark.unit
    def test_tensor2_variants_reduce_to_partial_in_cartesian(self) -> None:
        """Verifies: in Cartesian (zero Christoffels) every variant reduces to
        the ordinary partial derivative dT[J,K]/dtheta^I."""
        x, y, z = sp.symbols("x y z")
        theta = (x, y, z)
        gamma = christoffel_symbols(sp.eye(3), theta)
        # general symbolic tensor field
        T = sp.Matrix([[sp.Function(f"T{a}{b}")(x, y, z) for b in range(3)] for a in range(3)])

        for variant in ("contravariant", "covariant", "mixed"):
            result = covariant_derivative_tensor2(T, gamma, theta, variant=variant)
            for I in range(3):
                for J in range(3):
                    for K in range(3):
                        expected = sp.diff(T[J, K], theta[I])
                        assert sp.simplify(result[I, J, K] - expected) == 0

    @pytest.mark.unit
    def test_tensor2_covariant_variant_cylindrical_sanity(self) -> None:
        """Verifies: covariant rank-2 cov-derivative in cylindrical coords matches
        the hand-derived formula nabla_I T_{JK} = dT_{JK} - Gamma^L_{IJ}T_{LK} - Gamma^L_{IK}T_{JL}.
        Uses T_{JK} = diag(r, 0, 0)."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        theta = (r, th, z)
        gamma = christoffel_symbols(sp.diag(1, r**2, 1), theta)
        T = sp.Matrix([[r, 0, 0], [0, sp.S.Zero, 0], [0, 0, 0]])

        result = covariant_derivative_tensor2(T, gamma, theta, variant="covariant")

        # Reference hand formula
        for I in range(3):
            for J in range(3):
                for K in range(3):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(3):
                        val = val - gamma[L, I, J] * T[L, K] - gamma[L, I, K] * T[J, L]
                    assert sp.simplify(result[I, J, K] - val) == 0

        # Spot-check a known component: nabla_r T_rr = dT_rr/dr = 1
        assert sp.simplify(result[0, 0, 0] - 1) == 0

    @pytest.mark.unit
    def test_tensor2_mixed_variant_cylindrical_sanity(self) -> None:
        """Verifies: mixed rank-2 cov-derivative matches the hand formula
        nabla_I T^J_K = dT^J_K + Gamma^J_{IL}T^L_K - Gamma^L_{IK}T^J_L."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        theta = (r, th, z)
        gamma = christoffel_symbols(sp.diag(1, r**2, 1), theta)
        T = sp.Matrix([[r, 0, 0], [0, sp.S.Zero, 0], [0, 0, 0]])

        result = covariant_derivative_tensor2(T, gamma, theta, variant="mixed")

        for I in range(3):
            for J in range(3):
                for K in range(3):
                    val = sp.diff(T[J, K], theta[I])
                    for L in range(3):
                        val = val + gamma[J, I, L] * T[L, K] - gamma[L, I, K] * T[J, L]
                    assert sp.simplify(result[I, J, K] - val) == 0

    @pytest.mark.unit
    def test_tensor2_invalid_variant_raises(self) -> None:
        """Verifies: an unsupported variant raises ValueError."""
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        z = sp.Symbol("z")
        theta = (r, th, z)
        gamma = christoffel_symbols(sp.diag(1, r**2, 1), theta)
        T = sp.diag(r, 0, 0)
        with pytest.raises(ValueError, match="variant must be"):
            covariant_derivative_tensor2(T, gamma, theta, variant="bogus")
