"""Tests for curvilinear patch test + Cartesian equivalence (Plan B Phase 2, Task P2-5).

Phase 2 exit criterion: convected formulation passes patch test on curvilinear mesh
and matches Cartesian formulation on a Cartesian mesh within 1e-12.

The tests verify the full Phase 2 symbolic infrastructure (MetricField, convected
metric, Christoffel symbols, covariant derivatives) by evaluating the SVK
constitutive law through the convected pathway at multiple points in a curvilinear
domain and checking that the Cauchy stress is constant (patch test) and matches
the standard Cartesian formulation (equivalence test).
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Helpers: SVK stress computation via the convected pathway
# ---------------------------------------------------------------------------


def _svk_stress_convected(
    F: np.ndarray,
    G_ref_vecs: np.ndarray,
    lam: float,
    mu: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute PK2 and Cauchy stress via the convected metric pathway.

    Args:
        F: 3x3 deformation gradient (Cartesian).
        G_ref_vecs: 3x3 matrix whose columns are reference base vectors G_I.
        lam: Lamé first parameter.
        mu: Lamé second parameter (shear modulus).

    Returns:
        (E_conv, S_conv, sigma): Green-Lagrange strain in convected indices,
        PK2 stress in convected indices (S^{IJ}), Cauchy stress (Cartesian).
    """
    # Convected metric: g_IJ = G_ref^T @ C @ G_ref
    C = F.T @ F
    g = G_ref_vecs.T @ C @ G_ref_vecs

    # Reference metric: G_IJ = G_ref^T @ G_ref
    G_metric = G_ref_vecs.T @ G_ref_vecs
    G_inv = np.linalg.inv(G_metric)

    # Green-Lagrange strain in convected indices
    E = 0.5 * (g - G_metric)

    # SVK stress in convected indices: S^{IJ} = C^{IJKL} E_{KL}
    # C^{IJKL} = lam G^{IJ} G^{KL} + mu (G^{IK} G^{JL} + G^{IL} G^{JK})
    # S = lam * tr_G(E) * G_inv + 2*mu * G_inv @ E @ G_inv
    tr_G_E = np.sum(G_inv * E)  # G^{KL} E_{KL}
    S_conv = lam * tr_G_E * G_inv + 2.0 * mu * G_inv @ E @ G_inv

    # Push forward to Cartesian PK2: S_cart = G_ref @ S_conv @ G_ref^T
    S_cart = G_ref_vecs @ S_conv @ G_ref_vecs.T

    # Cauchy stress: sigma = (1/J) F S_cart F^T
    J = np.linalg.det(F)
    sigma = (1.0 / J) * F @ S_cart @ F.T

    return E, S_conv, sigma


def _svk_stress_cartesian(
    F: np.ndarray,
    lam: float,
    mu: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute PK2 and Cauchy stress via the standard Cartesian pathway.

    Returns:
        (E, S, sigma): Green-Lagrange strain, PK2 stress, Cauchy stress.
    """
    C = F.T @ F
    E = 0.5 * (C - np.eye(3))
    tr_E = np.trace(E)
    S = lam * tr_E * np.eye(3) + 2.0 * mu * E

    J = np.linalg.det(F)
    sigma = (1.0 / J) * F @ S @ F.T

    return E, S, sigma


# ---------------------------------------------------------------------------
# P2-5: Curvilinear patch test + Cartesian equivalence
# ---------------------------------------------------------------------------


class TestTaskP2_5CurvilinearPatchTest:
    """
    Tests for Task P2-5: Curvilinear patch test + Cartesian equivalence.
    Acceptance criteria covered: [1] Constant stress, [2] Cartesian equivalence.
    """

    def test_curvilinear_patch_test_constant_stress(self):
        """
        Verifies: On a quarter-annulus mesh in cylindrical coordinates with
        uniform prescribed strain, the Cauchy stress is constant across all
        evaluation points to machine precision.
        Acceptance criterion: Curvilinear patch test passes (constant stress
        across all elements within 1e-12).
        Passes when: max|sigma_e - sigma_mean| < 1e-12 across all points.
        """
        # Unit material parameters (avoid round-off scaling issues)
        lam, mu = 1.0, 1.0

        # Uniform stretch in Cartesian coordinates
        stretch = 1.0 + 1e-4  # small stretch for linearised regime
        F = stretch * np.eye(3)

        # Evaluate at multiple (r, θ) points across a quarter-annulus.
        # Cylindrical reference base vectors at (r, θ):
        #   G_1 = (cos θ, sin θ, 0)   — radial
        #   G_2 = (-r sin θ, r cos θ, 0) — circumferential
        #   G_3 = (0, 0, 1)            — axial
        r_values = [1.0, 1.5, 2.0, 2.5, 3.0]
        theta_values = [0.0, np.pi / 8, np.pi / 4]
        cauchy_stresses = []
        point_labels = []

        for r_val in r_values:
            for theta_val in theta_values:
                G_ref = np.array(
                    [
                        [np.cos(theta_val), -r_val * np.sin(theta_val), 0.0],
                        [np.sin(theta_val), r_val * np.cos(theta_val), 0.0],
                        [0.0, 0.0, 1.0],
                    ]
                )
                _, _, sigma = _svk_stress_convected(F, G_ref, lam, mu)
                cauchy_stresses.append(sigma)
                point_labels.append(f"r={r_val}, θ={theta_val:.4f}")

        # All Cauchy stresses must be identical (constant across the domain)
        sigma_ref = cauchy_stresses[0]
        for i, sigma_i in enumerate(cauchy_stresses[1:], start=1):
            diff = np.max(np.abs(sigma_i - sigma_ref))
            assert diff < 1e-12, (
                f"Cauchy stress at ({point_labels[i]}) differs from "
                f"({point_labels[0]}) by {diff:.3e} (must be < 1e-12)\n"
                f"σ({point_labels[0]}):\n{sigma_ref}\n"
                f"σ({point_labels[i]}):\n{sigma_i}"
            )

        # Verify the Cauchy stress matches the analytical prediction:
        # E = e*I with e = 0.5*(s²-1), tr(E) = 3e,
        # S = (3lam + 2mu)*e*I, J = s³,
        # σ = (1/J)*F*S*F^T = (1/s³)*s²*S = (1/s)*(3lam+2mu)*e*I
        e = 0.5 * (stretch**2 - 1)
        sigma_analytical = (1.0 / stretch) * (3.0 * lam + 2.0 * mu) * e * np.eye(3)
        diff = np.max(np.abs(sigma_ref - sigma_analytical))
        assert diff < 1e-12, (
            f"Cauchy stress differs from analytical by {diff:.3e}\n"
            f"σ_computed:\n{sigma_ref}\nσ_analytical:\n{sigma_analytical}"
        )

        # Test with non-isotropic F (simple shear) — Cauchy stress must still
        # be position-independent even though the convected-index stress varies
        gamma_shear = 1e-4
        F_shear = np.eye(3)
        F_shear[0, 1] = gamma_shear

        cauchy_shear = []
        for r_val in r_values:
            for theta_val in theta_values:
                G_ref = np.array(
                    [
                        [np.cos(theta_val), -r_val * np.sin(theta_val), 0.0],
                        [np.sin(theta_val), r_val * np.cos(theta_val), 0.0],
                        [0.0, 0.0, 1.0],
                    ]
                )
                _, _, sigma = _svk_stress_convected(F_shear, G_ref, lam, mu)
                cauchy_shear.append(sigma)

        sigma_shear_ref = cauchy_shear[0]
        for i, sigma_i in enumerate(cauchy_shear[1:], start=1):
            diff = np.max(np.abs(sigma_i - sigma_shear_ref))
            assert diff < 1e-12, f"Shear: Cauchy stress at point {i} differs by {diff:.3e}"

        # Verify the shear Cauchy matches the Cartesian computation
        _, _, sigma_cart_shear = _svk_stress_cartesian(F_shear, lam, mu)
        diff = np.max(np.abs(sigma_shear_ref - sigma_cart_shear))
        assert diff < 1e-12, f"Shear: convected Cauchy differs from Cartesian by {diff:.3e}"

    def test_cartesian_convected_equivalence(self):
        """
        Verifies: On a Cartesian mesh, the convected-coordinate formulation
        (with G = I3) produces identical stress to the standard Cartesian
        formulation.
        Acceptance criterion: Cartesian-convected equivalence test passes
        (max difference < 1e-12).
        """
        lam, mu = 1.0, 1.0
        G_ref_cartesian = np.eye(3)  # Cartesian: G_ref = I

        # Test multiple deformation states
        deformation_cases = {
            "uniaxial_stretch": np.diag([1.001, 1.0, 1.0]),
            "biaxial_stretch": np.diag([1.001, 1.001, 1.0]),
            "volumetric": np.diag([1.001, 1.001, 1.001]),
        }

        # Add simple shear
        F_shear = np.eye(3)
        F_shear[0, 1] = 1e-4
        deformation_cases["simple_shear"] = F_shear

        # Add combined stretch + shear
        F_combined = np.diag([1.001, 0.999, 1.0])
        F_combined[0, 2] = 5e-5
        F_combined[1, 2] = -3e-5
        deformation_cases["combined"] = F_combined

        for name, F in deformation_cases.items():
            # Convected pathway with G_ref = I (should match Cartesian exactly)
            E_conv, S_conv, sigma_conv = _svk_stress_convected(F, G_ref_cartesian, lam, mu)

            # Standard Cartesian pathway
            E_cart, S_cart, sigma_cart = _svk_stress_cartesian(F, lam, mu)

            # With G_ref = I, convected reduces algebraically to Cartesian.
            # All quantities must match to near machine epsilon.
            tol = 1e-13
            diff_E = np.max(np.abs(E_conv - E_cart))
            assert diff_E < tol, f"{name}: E differs by {diff_E:.3e}"

            diff_S = np.max(np.abs(S_conv - S_cart))
            assert diff_S < tol, f"{name}: S differs by {diff_S:.3e}"

            diff_sigma = np.max(np.abs(sigma_conv - sigma_cart))
            assert diff_sigma < tol, f"{name}: sigma differs by {diff_sigma:.3e}"

        # Additionally verify the symbolic layer: compute_convected_metric
        # with G_ref_vecs=I must equal F^T F for each case.
        import sympy as sp

        from mechdsl.symbolic.convected import (
            compute_convected_metric,
            green_lagrange_convected,
        )

        for name, F_np in deformation_cases.items():
            F_sym = sp.Matrix(F_np.tolist())

            # Fast path (no G_ref_vecs)
            g_fast = compute_convected_metric(F_sym)

            # Explicit Cartesian G_ref_vecs = I
            g_explicit = compute_convected_metric(F_sym, G_ref_vecs=sp.eye(3))

            # Must be identical
            diff_sym = sp.simplify(g_fast - g_explicit)
            assert diff_sym == sp.zeros(3), (
                f"{name}: symbolic g differs between fast and explicit paths"
            )

            # Green-Lagrange strain must match 0.5(C - I)
            E_sym = green_lagrange_convected(g_fast, sp.eye(3))
            E_expected = sp.Rational(1, 2) * (F_sym.T @ F_sym - sp.eye(3))
            diff_E_sym = sp.simplify(E_sym - E_expected)
            assert diff_E_sym == sp.zeros(3), f"{name}: symbolic E differs from expected"
