"""Tests for analytical solution functions — Sprint 2 Phase 2.

These tests verify hand-calculated analytical solutions for canonical problems:
- Patch test (constant strain recovery)
- Rigid body modes (zero-strain zero-stress)
- Cantilever beam (Euler-Bernoulli comparison)
- Uniaxial tension with hardening (stress-strain curve)

All tests derive from P2-T1, P2-T2, P2-T3, P2-T4 (implemented) and P2-T5 (combined).
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.verify.analytical import (
    cantilever_euler_bernoulli,
    patch_test_reference,
    rigid_body_reference,
    uniaxial_tension_hardening,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_cube_coords() -> np.ndarray:
    """8 nodes of the unit cube [0,1]^3."""
    verts = []
    for k in range(2):
        for j in range(2):
            for i in range(2):
                verts.append([float(i), float(j), float(k)])
    return np.array(verts)  # shape (8, 3)


def _rot_z(theta: float) -> np.ndarray:
    """Rotation matrix about the z-axis by angle theta (radians)."""
    c, s = np.cos(theta), np.sin(theta)
    return np.array(
        [
            [c, -s, 0.0],
            [s, c, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


# ---------------------------------------------------------------------------
# P2-T1: patch_test_reference
# ---------------------------------------------------------------------------


class TestPatchTestReference:
    """Tests for P2-T1: patch_test_reference(coords, strain) → displacement

    Acceptance criteria:
    - Zero strain → zero displacement
    - Known strain → hand-calculated displacement
    - Symmetric strain validation
    """

    def test_patch_zero_strain_gives_zero_displacement(self) -> None:
        """
        Verifies: zero Green-Lagrange strain produces zero displacement.

        Given a unit cube [0,1]^3 and zero strain E_ij = 0,
        the displacement at every node must be zero.

        Acceptance criterion: all displacement components are exactly zero.
        """
        coords = _unit_cube_coords()
        strain = np.zeros((3, 3))
        u = patch_test_reference(coords, strain)
        assert u.shape == (8, 3)
        np.testing.assert_array_equal(u, np.zeros((8, 3)))

    def test_patch_known_constant_strain(self) -> None:
        """
        Verifies: known constant strain produces analytically correct displacement.

        Given a unit cube and constant uniaxial strain E_xx = 0.01,
        displacement u = E · X is analytically u_x = 0.01 * x, u_y = 0, u_z = 0.

        Hand calculation for node at X = (1, 1, 1):
            u = [[0.01, 0, 0], [0, 0, 0], [0, 0, 0]] @ [1, 1, 1]^T = [0.01, 0, 0]

        Acceptance criterion: displacement matches u = E · X to machine precision.
        """
        coords = _unit_cube_coords()
        E_xx = 0.01
        strain = np.diag([E_xx, 0.0, 0.0])
        u = patch_test_reference(coords, strain)

        # u_x = E_xx * X_x for each node; u_y = u_z = 0
        expected = np.zeros((8, 3))
        expected[:, 0] = E_xx * coords[:, 0]
        np.testing.assert_allclose(u, expected, atol=0.0)

    def test_patch_triaxial_strain(self) -> None:
        """
        Verifies: triaxial strain with all diagonal components non-zero.

        strain = diag([e1, e2, e3]).
        For node at X=(1,1,1): u = [e1, e2, e3].
        """
        coords = np.array([[1.0, 2.0, 3.0], [0.5, 0.5, 0.5]])
        strain = np.diag([0.01, 0.02, 0.03])
        u = patch_test_reference(coords, strain)
        # u_i = E_ij * X_j (no off-diagonal, so u_i = E_ii * X_i)
        expected = coords * np.array([0.01, 0.02, 0.03])
        np.testing.assert_allclose(u, expected, atol=1e-15)

    def test_patch_symmetric_strain_validation(self) -> None:
        """
        Verifies: symmetric shear strain produces correct off-diagonal displacement.

        E = [[0, e12, 0], [e12, 0, 0], [0, 0, 0]]  with e12 = 0.005.

        For node at X = (2, 3, 0):
            u_x = E_xx*X_x + E_xy*X_y + E_xz*X_z = 0*2 + 0.005*3 + 0*0 = 0.015
            u_y = E_yx*X_x + E_yy*X_y + E_yz*X_z = 0.005*2 + 0*3 + 0*0 = 0.010
            u_z = 0

        Acceptance criterion: displacement symmetry matches strain symmetry.
        """
        e12 = 0.005
        strain = np.array(
            [
                [0.0, e12, 0.0],
                [e12, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        )
        coords = np.array([[2.0, 3.0, 0.0]])
        u = patch_test_reference(coords, strain)
        expected = np.array([[e12 * 3.0, e12 * 2.0, 0.0]])
        np.testing.assert_allclose(u, expected, atol=1e-15)

    def test_patch_rejects_asymmetric_strain(self) -> None:
        """Verifies: non-symmetric strain raises ValueError."""
        strain = np.array(
            [
                [0.01, 0.02, 0.0],
                [0.00, 0.00, 0.0],  # E_yx != E_xy
                [0.00, 0.00, 0.0],
            ]
        )
        coords = _unit_cube_coords()
        with pytest.raises(ValueError, match="symmetric"):
            patch_test_reference(coords, strain)

    def test_patch_rejects_wrong_strain_shape(self) -> None:
        """Verifies: strain with wrong shape raises ValueError."""
        coords = _unit_cube_coords()
        bad_strain = np.zeros((2, 2))
        with pytest.raises(ValueError, match="shape"):
            patch_test_reference(coords, bad_strain)

    def test_patch_rejects_wrong_coord_shape(self) -> None:
        """Verifies: coords with wrong column count raises ValueError."""
        strain = np.zeros((3, 3))
        bad_coords = np.zeros((5, 2))  # should be (N, 3)
        with pytest.raises(ValueError, match="shape"):
            patch_test_reference(bad_coords, strain)


# ---------------------------------------------------------------------------
# P2-T2: rigid_body_reference
# ---------------------------------------------------------------------------


class TestRigidBodyReference:
    """Tests for P2-T2: rigid_body_reference(coords, R, t) → displacement

    Acceptance criteria:
    - Identity rotation + zero translation → zero displacement
    - Known rotation (e.g., 45° about z) → correct rotation matrix applied
    """

    def test_rigid_body_identity_zero_displacement(self) -> None:
        """
        Verifies: identity rotation and zero translation produce zero displacement.

        Given a unit cube and R = I, t = 0,
        every node must remain at its original position.

        Acceptance criterion: all displacement components are exactly zero.
        """
        coords = _unit_cube_coords()
        R = np.eye(3)
        t = np.zeros(3)
        u = rigid_body_reference(coords, R, t)
        assert u.shape == (8, 3)
        np.testing.assert_array_equal(u, np.zeros((8, 3)))

    def test_rigid_body_pure_translation(self) -> None:
        """
        Verifies: pure translation (R=I, t≠0) gives constant displacement = t.

        Every node is displaced by exactly t regardless of its position.
        """
        coords = _unit_cube_coords()
        R = np.eye(3)
        t = np.array([1.5, -0.3, 2.0])
        u = rigid_body_reference(coords, R, t)
        expected = np.tile(t, (8, 1))
        np.testing.assert_allclose(u, expected, atol=1e-15)

    def test_rigid_body_known_rotation(self) -> None:
        """
        Verifies: known rotation (45° about z-axis) produces correct displacement.

        Given a unit cube and R = Rot_z(45°), t = 0,
        displacement u = (R - I) · X is analytically known.

        For node at X = (1, 0, 0):
            x_def = R @ X = [cos45, sin45, 0] = [√2/2, √2/2, 0]
            u = x_def - X = [√2/2 - 1, √2/2, 0]

        Acceptance criterion: displacement matches rotation matrix formula to ~1e-10.
        """
        coords = _unit_cube_coords()
        theta = np.pi / 4  # 45 degrees
        R = _rot_z(theta)
        t = np.zeros(3)
        u = rigid_body_reference(coords, R, t)

        # Compute expected analytically: u = (R - I) @ X
        expected = coords @ (R - np.eye(3)).T
        np.testing.assert_allclose(u, expected, atol=1e-12)

        # Spot check node (1, 0, 0): X = [1, 0, 0]
        node_idx = next(i for i, c in enumerate(coords) if np.allclose(c, [1, 0, 0]))
        u_node = u[node_idx]
        np.testing.assert_allclose(u_node[0], np.cos(theta) - 1.0, atol=1e-12)
        np.testing.assert_allclose(u_node[1], np.sin(theta), atol=1e-12)
        np.testing.assert_allclose(u_node[2], 0.0, atol=1e-12)

    def test_rigid_body_90deg_rotation_about_z(self) -> None:
        """
        Verifies: 90° rotation about z maps (1,0,0) → (0,1,0).

        u = (R-I) @ X → u = [-1, 1, 0] for X = (1, 0, 0).
        """
        coords = np.array([[1.0, 0.0, 0.0]])
        R = _rot_z(np.pi / 2)
        t = np.zeros(3)
        u = rigid_body_reference(coords, R, t)
        np.testing.assert_allclose(u[0], [-1.0, 1.0, 0.0], atol=1e-14)

    def test_rigid_body_rejects_non_orthogonal(self) -> None:
        """Verifies: non-orthogonal matrix raises ValueError."""
        coords = _unit_cube_coords()
        bad_R = np.array(
            [
                [2.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        )  # det = 2, not orthogonal
        t = np.zeros(3)
        with pytest.raises(ValueError, match="orthogonal"):
            rigid_body_reference(coords, bad_R, t)

    def test_rigid_body_rejects_improper_rotation(self) -> None:
        """Verifies: reflection matrix (det = -1) raises ValueError."""
        coords = _unit_cube_coords()
        # Reflection about x: det = -1
        bad_R = np.diag([-1.0, 1.0, 1.0])
        t = np.zeros(3)
        with pytest.raises(ValueError, match="det"):
            rigid_body_reference(coords, bad_R, t)


# ---------------------------------------------------------------------------
# P2-T3: cantilever_euler_bernoulli
# ---------------------------------------------------------------------------


class TestCantileverEulerBernoulli:
    """Tests for P2-T3: cantilever_euler_bernoulli(L, I, E, P) → tip_displacement

    Acceptance criteria:
    - Correct tip deflection formula delta = P*L^3 / (3*E*I)
    - Deflection monotonic along beam
    - Boundary conditions: zero at fixed end
    """

    def test_cantilever_known_beam_params(self) -> None:
        """
        Verifies: known cantilever parameters produce analytically correct tip deflection.

        Given:
        - Length L = 4.0
        - Second moment I = 0.0667 (for ~2x1 cross-section)
        - Young's modulus E = 200e3
        - End load P = 100

        Hand calculation:
            delta = P * L^3 / (3 * E * I)
                  = 100 * 64 / (3 * 200000 * 0.0667)
                  = 6400 / 40020
                  ≈ 0.159920...

        Acceptance criterion: computed tip_displacement matches analytical formula.
        """
        L, I_val, E_val, P = 4.0, 0.0667, 200e3, 100.0
        delta = cantilever_euler_bernoulli(L, I_val, E_val, P)
        expected = P * L**3 / (3.0 * E_val * I_val)
        np.testing.assert_allclose(delta, expected, rtol=1e-14)

    def test_cantilever_unit_beam(self) -> None:
        """
        Verifies: unit beam (L=I=E=P=1) gives delta = 1/3.

        delta = 1 * 1^3 / (3 * 1 * 1) = 1/3
        """
        delta = cantilever_euler_bernoulli(1.0, 1.0, 1.0, 1.0)
        np.testing.assert_allclose(delta, 1.0 / 3.0, rtol=1e-14)

    def test_cantilever_negative_load(self) -> None:
        """Verifies: negative load gives negative (upward) deflection."""
        delta = cantilever_euler_bernoulli(1.0, 1.0, 1.0, -1.0)
        assert delta == pytest.approx(-1.0 / 3.0)

    def test_cantilever_zero_load(self) -> None:
        """Verifies: zero load gives zero deflection."""
        delta = cantilever_euler_bernoulli(2.0, 0.5, 100.0, 0.0)
        assert delta == 0.0

    def test_cantilever_deflection_scales_cubically_with_L(self) -> None:
        """Verifies: doubling beam length increases deflection by factor 8 (L^3 scaling)."""
        L, I_val, E_val, P = 2.0, 1.0, 1.0, 1.0
        d1 = cantilever_euler_bernoulli(L, I_val, E_val, P)
        d2 = cantilever_euler_bernoulli(2 * L, I_val, E_val, P)
        np.testing.assert_allclose(d2 / d1, 8.0, rtol=1e-14)

    def test_cantilever_rejects_non_positive_L(self) -> None:
        """Verifies: L <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ll]ength"):
            cantilever_euler_bernoulli(0.0, 1.0, 1.0, 1.0)
        with pytest.raises(ValueError, match=r"[Ll]ength"):
            cantilever_euler_bernoulli(-1.0, 1.0, 1.0, 1.0)

    def test_cantilever_rejects_non_positive_I(self) -> None:
        """Verifies: I <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ii]"):
            cantilever_euler_bernoulli(1.0, 0.0, 1.0, 1.0)

    def test_cantilever_rejects_non_positive_E(self) -> None:
        """Verifies: E <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Mm]odulus|[Ee]"):
            cantilever_euler_bernoulli(1.0, 1.0, 0.0, 1.0)


# ---------------------------------------------------------------------------
# P2-T4: uniaxial_tension_hardening
# ---------------------------------------------------------------------------


class TestUniaxialTensionHardening:
    """Tests for P2-T4: uniaxial_tension_hardening(E, nu, sigma_y0, K, n, eps_total) → (stress, eps_p)

    Acceptance criteria:
    - Below yield: stress = E * eps_total (elastic)
    - Above yield: stress-strain follows hardening law
    - Continuity at yield point
    - Large monotonic strain: hardening law holds
    """

    # Typical steel-like material
    _E = 200_000.0  # MPa
    _nu = 0.3
    _sy0 = 250.0  # MPa
    _K = 500.0  # MPa
    _n = 1.0  # linear hardening

    def test_uniaxial_below_yield_elastic(self) -> None:
        """
        Verifies: strain below yield produces purely elastic response.

        Given material parameters:
        - E = 200e3, nu = 0.3, sigma_y0 = 250, K = 500, n = 1.0
        - eps_total = 0.001 (below yield at eps_y = sigma_y0/E = 250/200000 = 0.00125)

        The stress must be exactly sigma = E * eps_total = 200.
        The plastic strain must be zero: eps_p = 0.

        Acceptance criterion: elastic slope and zero plastic strain.
        """
        eps_total = 0.001  # < eps_y = 0.00125
        stress, eps_p = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, eps_total
        )
        assert stress == pytest.approx(self._E * eps_total, rel=1e-14)
        assert eps_p == 0.0

    def test_uniaxial_at_yield_elastic(self) -> None:
        """
        Verifies: strain exactly at yield is still elastic (boundary case).

        eps_y = sigma_y0 / E = 250 / 200000 = 0.00125.
        stress = E * eps_y = sigma_y0 = 250.
        """
        eps_y = self._sy0 / self._E
        stress, eps_p = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, eps_y
        )
        assert stress == pytest.approx(self._sy0, rel=1e-14)
        assert eps_p == 0.0

    def test_uniaxial_above_yield_hardening_law(self) -> None:
        """
        Verifies: strain above yield follows hardening law stress = sigma_y(eps_p).

        Given the same material and eps_total = 0.005 (well above yield):

        Consistency condition (linear hardening n=1):
            sigma_y0 + K * eps_p + E * eps_p = E * eps_total
            250 + (500 + 200000) * eps_p = 200000 * 0.005
            250 + 200500 * eps_p = 1000
            eps_p = 750 / 200500 ≈ 0.003740648...

        stress = E * (eps_total - eps_p) = 200000 * (0.005 - 0.003740648) ≈ 251.869...

        This must also equal sigma_y0 + K * eps_p ≈ 250 + 500 * 0.003740648 ≈ 251.870.

        Acceptance criterion: computed stress matches hardening law to ~2% tolerance
        (spec test tolerance), but we can achieve much better analytically.
        """
        eps_total = 0.005
        stress, eps_p = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, eps_total
        )

        # Analytical solution for linear hardening (n=1):
        # eps_p = (E * eps_total - sigma_y0) / (E + K)
        eps_p_exact = (self._E * eps_total - self._sy0) / (self._E + self._K)
        stress_exact = self._sy0 + self._K * eps_p_exact

        assert eps_p == pytest.approx(eps_p_exact, rel=1e-8)
        assert stress == pytest.approx(stress_exact, rel=1e-8)

        # Check that stress satisfies the hardening law sigma = sigma_y0 + K * eps_p^n
        yield_stress = self._sy0 + self._K * eps_p**self._n
        assert stress == pytest.approx(yield_stress, rel=1e-8)

        # Verify strain decomposition: eps_total = sigma/E + eps_p
        assert eps_total == pytest.approx(stress / self._E + eps_p, rel=1e-8)

    def test_uniaxial_continuity_at_yield_point(self) -> None:
        """
        Verifies: no jump in stress or plastic strain at the yield surface.

        Evaluate stress and eps_p at eps_total values bracketing the yield point.
        The stress-strain curve and plastic strain must be continuous.

        Acceptance criterion: no discontinuity in (stress, eps_p) at yield.
        """
        eps_y = self._sy0 / self._E  # 0.00125

        # Just below yield
        eps_below = eps_y - 1e-8
        stress_below, eps_p_below = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, eps_below
        )

        # Just above yield
        eps_above = eps_y + 1e-8
        stress_above, eps_p_above = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, eps_above
        )

        # Stress must be nearly equal at both sides (continuity).
        # With eps_delta = 1e-8, the elastic stress difference is E * 2*eps_delta = 0.004,
        # so we allow abs=0.01 to confirm continuity without a jump of order sigma_y0.
        assert stress_below == pytest.approx(stress_above, abs=0.01)

        # Both stresses must be near sigma_y0 (250 MPa)
        assert stress_below == pytest.approx(self._sy0, rel=1e-4)
        assert stress_above == pytest.approx(self._sy0, rel=1e-4)

        # Plastic strain transitions from 0 to near-zero
        assert eps_p_below == 0.0
        assert eps_p_above >= 0.0
        assert eps_p_above < 1e-6  # tiny

    def test_uniaxial_large_strain_monotonic(self) -> None:
        """
        Verifies: monotonic hardening law holds under large plastic strain.

        Given eps_total ranging from 0 to 0.1 in small increments,
        verify that stress increases monotonically and eps_p increases monotonically.

        Acceptance criterion: both stress and eps_p are strictly increasing
        (once above yield).
        """
        eps_values = np.linspace(0.0, 0.1, 200)
        stresses = []
        eps_ps = []
        for eps in eps_values:
            s, ep = uniaxial_tension_hardening(self._E, self._nu, self._sy0, self._K, self._n, eps)
            stresses.append(s)
            eps_ps.append(ep)

        stresses = np.array(stresses)
        eps_ps = np.array(eps_ps)

        # Both must be non-decreasing across all values
        assert np.all(np.diff(stresses) >= -1e-10), "stress is not monotonically non-decreasing"
        assert np.all(np.diff(eps_ps) >= -1e-14), "eps_p is not monotonically non-decreasing"

        # Once plastic: stresses must be strictly increasing
        yield_idx = next(i for i, s in enumerate(stresses) if s >= self._sy0)
        plastic_stresses = stresses[yield_idx:]
        assert np.all(np.diff(plastic_stresses) > 0), "plastic stress not strictly increasing"

    def test_uniaxial_power_law_hardening(self) -> None:
        """
        Verifies: power-law exponent n ≠ 1 satisfies the hardening consistency condition.

        For n = 0.5 (strain-rate independent power law), the result must satisfy:
            sigma = sigma_y0 + K * eps_p^n
            sigma = E * (eps_total - eps_p)
            eps_total = sigma/E + eps_p  (strain decomposition)
        """
        E, nu, sy0, K, n = 200_000.0, 0.3, 250.0, 500.0, 0.5
        eps_total = 0.01

        stress, eps_p = uniaxial_tension_hardening(E, nu, sy0, K, n, eps_total)

        # Verify strain decomposition
        assert eps_total == pytest.approx(stress / E + eps_p, rel=1e-8)

        # Verify hardening law
        yield_stress = sy0 + K * eps_p**n
        assert stress == pytest.approx(yield_stress, rel=1e-8)

    def test_uniaxial_zero_hardening(self) -> None:
        """
        Verifies: K = 0 gives perfectly plastic response above yield.

        For K = 0, the yield surface is fixed at sigma_y0. Above yield,
        stress stays at sigma_y0 and all extra strain is plastic.
        """
        E, nu, sy0, K, n = 200_000.0, 0.3, 250.0, 0.0, 1.0
        eps_total = 0.01  # well above yield

        stress, eps_p = uniaxial_tension_hardening(E, nu, sy0, K, n, eps_total)

        # Perfectly plastic: sigma = sigma_y0
        assert stress == pytest.approx(sy0, rel=1e-10)

        # Strain decomposition
        assert eps_total == pytest.approx(stress / E + eps_p, rel=1e-10)

    def test_uniaxial_zero_strain_gives_zero_stress(self) -> None:
        """Verifies: zero total strain gives zero stress and zero plastic strain."""
        stress, eps_p = uniaxial_tension_hardening(
            self._E, self._nu, self._sy0, self._K, self._n, 0.0
        )
        assert stress == 0.0
        assert eps_p == 0.0

    def test_uniaxial_rejects_non_positive_E(self) -> None:
        """Verifies: E <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ee]"):
            uniaxial_tension_hardening(0.0, 0.3, 250.0, 500.0, 1.0, 0.001)

    def test_uniaxial_rejects_non_positive_sigma_y0(self) -> None:
        """Verifies: sigma_y0 <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Yy]ield"):
            uniaxial_tension_hardening(200_000.0, 0.3, 0.0, 500.0, 1.0, 0.001)

    def test_uniaxial_rejects_negative_K(self) -> None:
        """Verifies: K < 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Kk]"):
            uniaxial_tension_hardening(200_000.0, 0.3, 250.0, -1.0, 1.0, 0.001)

    def test_uniaxial_rejects_non_positive_n(self) -> None:
        """Verifies: n <= 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Nn]"):
            uniaxial_tension_hardening(200_000.0, 0.3, 250.0, 500.0, 0.0, 0.001)

    def test_uniaxial_rejects_negative_eps_total(self) -> None:
        """Verifies: eps_total < 0 raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ss]train"):
            uniaxial_tension_hardening(200_000.0, 0.3, 250.0, 500.0, 1.0, -0.001)


# ---------------------------------------------------------------------------
# P2-T5: Combined acceptance tests
# ---------------------------------------------------------------------------


class TestAnalyticalSolutionsCombined:
    """Tests for P2-T5: combined acceptance tests across all four functions.

    These tests may overlap with individual task tests above but verify
    cross-function consistency and integration.
    """

    def test_all_four_solutions_imported(self) -> None:
        """
        Verifies: all four analytical solution functions can be imported.

        Acceptance criterion: no import errors.
        """
        # The imports at the top of this module would have already failed if any
        # function were missing. This test also explicitly checks the names.
        assert callable(patch_test_reference)
        assert callable(rigid_body_reference)
        assert callable(cantilever_euler_bernoulli)
        assert callable(uniaxial_tension_hardening)

    def test_patch_test_and_rigid_body_consistent_zero(self) -> None:
        """
        Verifies: both patch_test_reference(zero strain) and rigid_body_reference(I, 0)
        produce identical zero displacement fields for the same coordinate set.
        """
        coords = _unit_cube_coords()
        u_patch = patch_test_reference(coords, np.zeros((3, 3)))
        u_rigid = rigid_body_reference(coords, np.eye(3), np.zeros(3))
        np.testing.assert_array_equal(u_patch, u_rigid)

    def test_cantilever_formula_consistent_with_scaling(self) -> None:
        """
        Verifies: cantilever deflection is consistent under parameter scaling.

        Scaling E by factor k should reduce deflection by factor k (inverse linear).
        """
        L, I_val, E_val, P = 3.0, 0.05, 100_000.0, 50.0
        d1 = cantilever_euler_bernoulli(L, I_val, E_val, P)
        d2 = cantilever_euler_bernoulli(L, I_val, 2 * E_val, P)
        np.testing.assert_allclose(d1 / d2, 2.0, rtol=1e-14)

    def test_hardening_above_yield_consistent_decomposition(self) -> None:
        """
        Verifies: for 10 strain values above yield, strain decomposition holds.

        eps_total = sigma/E + eps_p must hold for all points.
        """
        E, nu, sy0, K, n = 200_000.0, 0.3, 250.0, 500.0, 1.0
        for eps in np.linspace(0.002, 0.05, 10):
            stress, eps_p = uniaxial_tension_hardening(E, nu, sy0, K, n, eps)
            assert eps == pytest.approx(stress / E + eps_p, rel=1e-8), (
                f"Strain decomposition failed at eps_total={eps}: "
                f"sigma/E + eps_p = {stress / E + eps_p}"
            )
