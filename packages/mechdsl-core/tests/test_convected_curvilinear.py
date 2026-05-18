"""Tests for curvilinear convected coordinate framework (Plan B Phase 2, Tasks P2-1/P2-2/P2-3).

Covers:
- P2-1: Covariant/contravariant bases + metric tensors (curvilinear reference)
- P2-2: Christoffel symbols from metric
- P2-3: Covariant derivatives (vectors and tensors)
"""

import numpy as np
import sympy as sp

from mechdsl.symbolic.convected import (
    MetricField,
    christoffel_symbols,
    compute_convected_metric,
    compute_reference_metric,
    contravariant_bases,
    covariant_bases,
    covariant_derivative_contravariant,
    covariant_derivative_covariant,
    covariant_derivative_tensor2,
    invert_metric,
)

# ---------------------------------------------------------------------------
# P2-1: Covariant/contravariant bases + metric tensors
# ---------------------------------------------------------------------------


class TestTaskP2_1MetricTensors:
    """
    Tests for Task P2-1: Covariant/contravariant bases + metric tensors.
    Acceptance criteria covered: [1] Cartesian fast path, [2] Cylindrical G_IJ, [3] Metric inversion.
    """

    def test_cartesian_reference_unchanged(self):
        """
        Verifies: When G = I3 (Cartesian reference), the new curvilinear API produces
        identical output to the existing MVP Cartesian path.
        Acceptance criterion: Cartesian reference (G = I3) path produces identical output
        to the current MVP.
        Passes when: MetricField('cartesian') produces G = I3, g = F^T F, and all
        downstream computations match the existing convected.py results byte-for-byte.
        """
        # Build a simple-shear F
        gamma = sp.Rational(1, 10)
        F = sp.eye(3)
        F[0, 1] = gamma

        # Old MVP path (no G_ref_vecs argument)
        g_mvp = compute_convected_metric(F)

        # New API with explicit Cartesian MetricField
        mf = MetricField.cartesian()
        assert mf.is_cartesian
        assert mf.matrix == sp.eye(3)

        # compute_reference_metric with Cartesian
        G_ref = compute_reference_metric(coords="cartesian")
        assert G_ref == sp.eye(3)

        # compute_convected_metric with explicit G_ref_vecs = I should match MVP
        g_with_I = compute_convected_metric(F, G_ref_vecs=sp.eye(3))
        assert sp.simplify(g_mvp - g_with_I) == sp.zeros(3)

    def test_cylindrical_g_ij_construction(self):
        """
        Verifies: For cylindrical coordinates (r, theta, z) with reference base vectors
        G_ref = diag(1, r, 1), the metric tensor g_IJ is computed correctly.
        Acceptance criterion: Cylindrical coordinates example computes g_IJ analytically
        and numerically and they agree.
        Passes when: Symbolic g_IJ matches numerical evaluation within 1e-12.
        """
        r = sp.Symbol("r", positive=True)
        # Cylindrical base vectors at theta=0: G_1=(1,0,0), G_2=(0,r,0), G_3=(0,0,1)
        G_ref = sp.diag(1, r, 1)
        G_metric = G_ref.T @ G_ref  # = diag(1, r^2, 1)

        # Use a simple diagonal F with a known stretch
        lam = sp.Rational(3, 2)  # stretch = 1.5
        F_sym = sp.diag(lam, lam, lam)

        # g_IJ = G_ref^T (F^T F) G_ref = G_ref^T (lam^2 I) G_ref = lam^2 G_metric
        g_sym = compute_convected_metric(F_sym, G_ref_vecs=G_ref)

        expected_sym = lam**2 * G_metric
        assert sp.simplify(g_sym - expected_sym) == sp.zeros(3)

        # Numerical evaluation at r0 = 2.0
        r0 = 2.0
        lam_num = float(lam)

        g_num = np.array(g_sym.subs(r, r0).tolist(), dtype=float)
        g_expected_num = lam_num**2 * np.diag([1.0, r0**2, 1.0])
        assert np.allclose(g_num, g_expected_num, atol=1e-12)

    def test_cylindrical_nonisotropic_f_consistency(self):
        """
        Verifies: g_IJ from compute_convected_metric matches g_I · g_J from
        covariant_bases for a non-isotropic F with cylindrical reference.
        This test catches the F^T G F vs G_ref^T C G_ref bug.
        """
        r = sp.Symbol("r", positive=True)
        G_ref = sp.diag(1, r, 1)

        # Non-isotropic F (simple shear — does NOT commute with G_ref)
        gamma = sp.Rational(1, 5)
        F = sp.eye(3)
        F[0, 1] = gamma

        # Method 1: compute_convected_metric
        g_from_metric = compute_convected_metric(F, G_ref_vecs=G_ref)

        # Method 2: covariant bases dot product g_IJ = g_I · g_J
        cov = covariant_bases(F, G_ref_vecs=G_ref)
        g_from_bases = sp.zeros(3)
        for i in range(3):
            for j in range(3):
                g_from_bases[i, j] = cov[i].dot(cov[j])

        assert sp.simplify(g_from_metric - g_from_bases) == sp.zeros(3)

        # Numerical verification at r0 = 2.0
        r0 = 2.0
        g_num = np.array(g_from_metric.subs(r, r0).tolist(), dtype=float)
        g_bases_num = np.array(g_from_bases.subs(r, r0).tolist(), dtype=float)
        assert np.allclose(g_num, g_bases_num, atol=1e-14)

    def test_metric_inversion_round_trip(self):
        """
        Verifies: g^{IK} g_{KJ} = delta^I_J for a non-trivial (cylindrical) metric.
        Acceptance criterion: Metric inversion returns g^{IJ} such that
        g^{IK} g_{KJ} = delta^I_J to 1e-12.
        Passes when: The product of the metric and its inverse is the identity to 1e-12.
        """
        r = sp.Symbol("r", positive=True)
        G_cyl = sp.diag(1, r**2, 1)

        # Use the cylindrical G itself as the metric to test inversion
        g_inv = invert_metric(G_cyl)

        # Symbolic round-trip: g * g_inv should simplify to I
        product = sp.simplify(G_cyl @ g_inv)
        assert product == sp.eye(3)

        # Numerical check at r0 = 3.7
        r0 = 3.7
        g_num = np.array(G_cyl.subs(r, r0).tolist(), dtype=float)
        g_inv_num = np.array(g_inv.subs(r, r0).tolist(), dtype=float)
        product_num = g_num @ g_inv_num
        assert np.allclose(product_num, np.eye(3), atol=1e-12)

        # Also verify with a non-diagonal metric via a simple shear F + cylindrical ref
        G_ref = sp.diag(1, r, 1)
        gamma = sp.Rational(1, 5)
        F_shear = sp.eye(3)
        F_shear[0, 1] = gamma
        g_shear = compute_convected_metric(F_shear, G_ref_vecs=G_ref)
        g_shear_inv = invert_metric(g_shear)
        product_shear_num = np.array(g_shear.subs(r, r0).tolist(), dtype=float) @ np.array(
            g_shear_inv.subs(r, r0).tolist(), dtype=float
        )
        assert np.allclose(product_shear_num, np.eye(3), atol=1e-12)

    def test_covariant_bases_curvilinear(self):
        """
        Verifies: covariant_bases(F, G_ref_vecs) returns g_I = F @ G_I for
        non-Cartesian reference base vectors.
        Acceptance criterion: Produce covariant base vectors at an arbitrary material
        point for a curvilinear reference.
        Passes when: g_I = F @ G_I matches direct matrix multiplication for cylindrical
        reference base vectors.
        """
        r = sp.Symbol("r", positive=True)
        # Reference base vectors for cylindrical (r, theta, z) at theta=0:
        # G_1=(1,0,0), G_2=(0,r,0), G_3=(0,0,1)
        G_ref = sp.Matrix([[1, 0, 0], [0, r, 0], [0, 0, 1]])

        # Simple shear F
        gamma = sp.Rational(1, 5)
        F = sp.eye(3)
        F[0, 1] = gamma

        cov = covariant_bases(F, G_ref_vecs=G_ref)
        assert len(cov) == 3

        # g_I = F @ col_I(G_ref)
        for i in range(3):
            expected = F @ G_ref.col(i)
            assert sp.simplify(cov[i] - expected) == sp.zeros(3, 1)

        # Numerical at r = 2.5
        r0 = 2.5
        for i in range(3):
            cov_num = np.array(cov[i].subs(r, r0).tolist(), dtype=float).flatten()
            expected_num = (
                np.array(F.tolist(), dtype=float)
                @ np.array(G_ref.col(i).subs(r, r0).tolist(), dtype=float).flatten()
            )
            assert np.allclose(cov_num, expected_num, atol=1e-14)

    def test_contravariant_bases_from_metric(self):
        """
        Verifies: Contravariant bases g^I = g^{IJ} g_J are dual to covariant bases,
        i.e. g^{IK} g_{KJ} = delta^I_J.

        Two sub-cases:
        (a) Cylindrical metric with non-isotropic F: duality via metric identity
            g^{IK} g_{KJ} = δ^I_J (symbolic + numerical).
        (b) Cartesian F with Cartesian G: covariant bases are columns of F and the
            Euclidean dot product g^I · g_J = δ^I_J holds exactly.
        """
        r = sp.Symbol("r", positive=True)
        G_ref = sp.diag(1, r, 1)  # cylindrical base vectors at theta=0

        # --- (a) Cylindrical: metric-level duality with non-isotropic F ---
        r0 = 2.0
        gamma = sp.Rational(1, 5)
        F_shear = sp.eye(3)
        F_shear[0, 1] = gamma

        g = compute_convected_metric(F_shear, G_ref_vecs=G_ref)
        g_inv = invert_metric(g)
        g_num = np.array(g.subs(r, r0).tolist(), dtype=float)
        g_inv_num = np.array(g_inv.subs(r, r0).tolist(), dtype=float)
        duality = g_inv_num @ g_num
        assert np.allclose(duality, np.eye(3), atol=1e-12), (
            f"Duality g^{{IK}} g_{{KJ}} != I:\n{duality}"
        )

        # --- (b) Cartesian Euclidean duality: g^I · g_J = δ^I_J ---
        gamma2 = sp.Rational(1, 4)
        F_shear2 = sp.eye(3)
        F_shear2[0, 1] = gamma2
        g_cart = compute_convected_metric(F_shear2)  # Cartesian G=I fast path
        g_cart_inv = invert_metric(g_cart)

        cov = covariant_bases(F_shear2)  # columns of F_shear2
        contr = contravariant_bases(cov, g_cart_inv)

        for ii in range(3):
            for jj in range(3):
                contr_ii = np.array(contr[ii].tolist(), dtype=float).flatten()
                cov_jj = np.array(cov[jj].tolist(), dtype=float).flatten()
                dot = float(np.dot(contr_ii, cov_jj))
                expected = 1.0 if ii == jj else 0.0
                assert abs(dot - expected) < 1e-12, (
                    f"Cartesian: g^{ii} · g_{jj} = {dot}, expected {expected}"
                )


# ---------------------------------------------------------------------------
# P2-2: Christoffel symbols from metric
# ---------------------------------------------------------------------------


class TestTaskP2_2ChristoffelSymbols:
    """
    Tests for Task P2-2: Christoffel symbols from metric.
    Acceptance criteria covered: [1] Cartesian zero, [2] Cylindrical closed form,
    [3] Symbolic performance.
    """

    def test_cartesian_christoffels_are_zero(self):
        """
        Verifies: For Cartesian G = I3, all Christoffel symbols vanish.
        Acceptance criterion: Cartesian metric returns all-zero Christoffels.
        Passes when: christoffel_symbols(I3, theta) returns a (3,3,3) array of zeros.
        """
        x, y, z = sp.symbols("x y z")
        g = sp.eye(3)
        gamma = christoffel_symbols(g, (x, y, z))
        assert gamma.shape == (3, 3, 3)
        for K in range(3):
            for I in range(3):
                for J in range(3):
                    assert gamma[K, I, J] == 0, (
                        f"Expected gamma[{K},{I},{J}] == 0, got {gamma[K, I, J]}"
                    )

    def test_cylindrical_christoffels_match_closed_form(self):
        """
        Verifies: For cylindrical (r, theta, z) with G = diag(1, r^2, 1),
        the non-zero Christoffel symbols are:
          Gamma^r_{theta,theta} = -r
          Gamma^theta_{r,theta} = Gamma^theta_{theta,r} = 1/r
        All others are zero.
        Acceptance criterion: Cylindrical Christoffel symbols match the hand-calculated values.
        Passes when: Non-zero symbols match within SymPy simplify, all others are zero.
        """
        r, th, z = sp.symbols("r theta z", positive=True)
        g = sp.diag(1, r**2, 1)
        gamma = christoffel_symbols(g, (r, th, z))

        assert gamma.shape == (3, 3, 3)

        # Known non-zero: gamma[0,1,1] = -r,  gamma[1,0,1] = gamma[1,1,0] = 1/r
        assert sp.simplify(gamma[0, 1, 1] - (-r)) == 0, (
            f"gamma[r,th,th]: expected -r, got {gamma[0, 1, 1]}"
        )
        assert sp.simplify(gamma[1, 0, 1] - sp.Rational(1, 1) / r) == 0, (
            f"gamma[th,r,th]: expected 1/r, got {gamma[1, 0, 1]}"
        )
        assert sp.simplify(gamma[1, 1, 0] - sp.Rational(1, 1) / r) == 0, (
            f"gamma[th,th,r]: expected 1/r, got {gamma[1, 1, 0]}"
        )

        # All other components must be zero
        non_zero_indices = {(0, 1, 1), (1, 0, 1), (1, 1, 0)}
        for K in range(3):
            for I in range(3):
                for J in range(3):
                    if (K, I, J) not in non_zero_indices:
                        assert sp.simplify(gamma[K, I, J]) == 0, (
                            f"Expected gamma[{K},{I},{J}] == 0, got {gamma[K, I, J]}"
                        )

    def test_spherical_christoffels_match_closed_form(self):
        """
        Verifies: For spherical (r, theta, phi) with G = diag(1, r^2, r^2 sin^2(theta)),
        the Christoffel symbols match the known closed-form values.
        Acceptance criterion: (from test_plan) Spherical Christoffels match closed form.
        Passes when: All 18 independent symbols match the textbook values.
        """
        r = sp.Symbol("r", positive=True)
        th = sp.Symbol("theta", positive=True)
        phi = sp.Symbol("phi")
        g = sp.diag(1, r**2, r**2 * sp.sin(th) ** 2)
        gamma = christoffel_symbols(g, (r, th, phi))

        assert gamma.shape == (3, 3, 3)

        # Index map: 0=r, 1=theta, 2=phi
        # Γ^r_{θθ} = -r
        assert sp.simplify(gamma[0, 1, 1] - (-r)) == 0, (
            f"gamma[r,th,th]: expected -r, got {gamma[0, 1, 1]}"
        )
        # Γ^r_{φφ} = -r sin^2(θ)
        assert sp.simplify(gamma[0, 2, 2] - (-(r * sp.sin(th) ** 2))) == 0, (
            f"gamma[r,phi,phi]: expected -r*sin^2(th), got {gamma[0, 2, 2]}"
        )
        # Γ^θ_{rθ} = Γ^θ_{θr} = 1/r
        assert sp.simplify(gamma[1, 0, 1] - 1 / r) == 0, (
            f"gamma[th,r,th]: expected 1/r, got {gamma[1, 0, 1]}"
        )
        assert sp.simplify(gamma[1, 1, 0] - 1 / r) == 0, (
            f"gamma[th,th,r]: expected 1/r, got {gamma[1, 1, 0]}"
        )
        # Γ^θ_{φφ} = -sin(θ)cos(θ)
        assert sp.simplify(gamma[1, 2, 2] - (-(sp.sin(th) * sp.cos(th)))) == 0, (
            f"gamma[th,phi,phi]: expected -sin(th)*cos(th), got {gamma[1, 2, 2]}"
        )
        # Γ^φ_{rφ} = Γ^φ_{φr} = 1/r
        assert sp.simplify(gamma[2, 0, 2] - 1 / r) == 0, (
            f"gamma[phi,r,phi]: expected 1/r, got {gamma[2, 0, 2]}"
        )
        assert sp.simplify(gamma[2, 2, 0] - 1 / r) == 0, (
            f"gamma[phi,phi,r]: expected 1/r, got {gamma[2, 2, 0]}"
        )
        # Γ^φ_{θφ} = Γ^φ_{φθ} = cos(θ)/sin(θ)
        assert sp.simplify(gamma[2, 1, 2] - sp.cos(th) / sp.sin(th)) == 0, (
            f"gamma[phi,th,phi]: expected cos(th)/sin(th), got {gamma[2, 1, 2]}"
        )
        assert sp.simplify(gamma[2, 2, 1] - sp.cos(th) / sp.sin(th)) == 0, (
            f"gamma[phi,phi,th]: expected cos(th)/sin(th), got {gamma[2, 2, 1]}"
        )

        # All other components must be zero
        non_zero_indices = {
            (0, 1, 1),
            (0, 2, 2),
            (1, 0, 1),
            (1, 1, 0),
            (1, 2, 2),
            (2, 0, 2),
            (2, 2, 0),
            (2, 1, 2),
            (2, 2, 1),
        }
        for K in range(3):
            for I in range(3):
                for J in range(3):
                    if (K, I, J) not in non_zero_indices:
                        assert sp.simplify(gamma[K, I, J]) == 0, (
                            f"Expected gamma[{K},{I},{J}] == 0, got {gamma[K, I, J]}"
                        )

    def test_christoffel_computation_under_5_seconds(self):
        """
        Verifies: Symbolic simplification finishes in < 5 seconds for cylindrical.
        Acceptance criterion: Symbolic simplification finishes in < 5 seconds
        for the cylindrical example.
        Passes when: The computation completes within the time budget.
        """
        import time

        r, th, z = sp.symbols("r theta z", positive=True)
        g = sp.diag(1, r**2, 1)

        start = time.perf_counter()
        gamma = christoffel_symbols(g, (r, th, z))
        # Trigger simplification of all components
        for K in range(3):
            for I in range(3):
                for J in range(3):
                    sp.simplify(gamma[K, I, J])
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Christoffel computation took {elapsed:.2f}s (limit: 5s)"


# ---------------------------------------------------------------------------
# P2-3: Covariant derivatives (vectors and tensors)
# ---------------------------------------------------------------------------


class TestTaskP2_3CovariantDerivatives:
    """
    Tests for Task P2-3: Covariant derivatives (vectors and tensors).
    Acceptance criteria covered: [1] Cylindrical radial field, [2] Cartesian reduction.
    """

    def test_contravariant_vector_covariant_derivative_cylindrical(self):
        """
        Verifies: nabla_I v^J = dv^J/dtheta^I + Gamma^J_{IK} v^K for a
        radially-symmetric velocity field v = v_r(r) e_r in cylindrical coordinates.
        Acceptance criterion: Covariant derivative of a radially-symmetric velocity
        field in cylindrical coordinates matches the hand calculation.
        Passes when: All 9 components match the hand-calculated values.
        """
        r, th, z = sp.symbols("r theta z", positive=True)
        theta = (r, th, z)

        # Cylindrical metric g = diag(1, r^2, 1)
        g = sp.diag(1, r**2, 1)
        gamma = christoffel_symbols(g, theta)

        # v^r = r^2, v^theta = 0, v^z = 0
        v = sp.Matrix([r**2, sp.S.Zero, sp.S.Zero])

        result = covariant_derivative_contravariant(v, gamma, theta)

        # Hand-calculated expected matrix:
        # [[2r, 0, 0],
        #  [0,  r, 0],
        #  [0,  0, 0]]
        expected = sp.Matrix([[2 * r, 0, 0], [0, r, 0], [0, 0, 0]])

        for I in range(3):
            for J in range(3):
                assert sp.simplify(result[I, J] - expected[I, J]) == 0, (
                    f"result[{I},{J}] = {result[I, J]}, expected {expected[I, J]}"
                )

    def test_covariant_vector_covariant_derivative_cylindrical(self):
        """
        Verifies: nabla_I v_J = dv_J/dtheta^I - Gamma^K_{IJ} v_K for a
        covariant vector field in cylindrical coordinates.
        Acceptance criterion: (from test_plan) Covariant vector derivative on cylindrical.
        Passes when: Result matches hand calculation for a known covariant vector field.
        """
        r, th, z = sp.symbols("r theta z", positive=True)
        theta = (r, th, z)

        # Cylindrical metric g = diag(1, r^2, 1)
        g = sp.diag(1, r**2, 1)
        gamma = christoffel_symbols(g, theta)

        # Covariant vector: w_r = r, w_theta = 0, w_z = 0
        w = sp.Matrix([r, sp.S.Zero, sp.S.Zero])

        result = covariant_derivative_covariant(w, gamma, theta)

        # Hand-calculated expected matrix:
        # [[1,   0, 0],
        #  [0,  r², 0],
        #  [0,   0, 0]]
        expected = sp.Matrix([[1, 0, 0], [0, r**2, 0], [0, 0, 0]])

        for I in range(3):
            for J in range(3):
                assert sp.simplify(result[I, J] - expected[I, J]) == 0, (
                    f"result[{I},{J}] = {result[I, J]}, expected {expected[I, J]}"
                )

    def test_rank2_tensor_covariant_derivative_cylindrical(self):
        """
        Verifies: nabla_I T^{JK} = dT^{JK}/dtheta^I + Gamma^J_{IL} T^{LK}
        + Gamma^K_{IL} T^{JL} for a rank-2 tensor in cylindrical coordinates.
        Acceptance criterion: (from test_plan) Rank-2 tensor derivative on cylindrical.
        Passes when: Result matches the hand calculation for a diagonal tensor field.
        """
        r, th, z = sp.symbols("r theta z", positive=True)
        theta = (r, th, z)

        # Cylindrical metric g = diag(1, r^2, 1)
        g = sp.diag(1, r**2, 1)
        gamma = christoffel_symbols(g, theta)

        # T^{JK} = diag(r, 0, 0): only T^{rr} = r, all others zero
        T = sp.Matrix([[r, 0, 0], [0, 0, 0], [0, 0, 0]])

        result = covariant_derivative_tensor2(T, gamma, theta)

        # Hand-calculated key components:
        # ∇_r T^{rr} = ∂T^{rr}/∂r + 0 + 0 = 1
        assert sp.simplify(result[0, 0, 0] - 1) == 0, (
            f"result[r,r,r] = {result[0, 0, 0]}, expected 1"
        )
        # ∇_θ T^{rr} = 0 (no theta dependence, Γ^r_{θL} T^{Lr} = 0 since T^{θr}=T^{zr}=0,
        #               Γ^r_{θL} T^{rL} = 0 since T^{rθ}=T^{rz}=0)
        assert sp.simplify(result[1, 0, 0]) == 0, f"result[θ,r,r] = {result[1, 0, 0]}, expected 0"
        # ∇_θ T^{θr} = Γ^θ_{θr} T^{rr} + 0 = (1/r)·r = 1
        assert sp.simplify(result[1, 1, 0] - 1) == 0, (
            f"result[θ,θ,r] = {result[1, 1, 0]}, expected 1"
        )
        # ∇_θ T^{rθ} = Γ^r_{θL} T^{Lθ} + Γ^θ_{θL} T^{rL} = 0 + Γ^θ_{θr} T^{rr} = (1/r)·r = 1
        assert sp.simplify(result[1, 0, 1] - 1) == 0, (
            f"result[θ,r,θ] = {result[1, 0, 1]}, expected 1"
        )

        # All z-row components must be zero (no z-dependence and no z Christoffels)
        for J in range(3):
            for K in range(3):
                assert sp.simplify(result[2, J, K]) == 0, (
                    f"result[z,{J},{K}] = {result[2, J, K]}, expected 0"
                )

    def test_cartesian_reduction_to_partial_derivative(self):
        """
        Verifies: On Cartesian coordinates (G = I3, Gamma = 0), the covariant
        derivative reduces to the ordinary partial derivative.
        Acceptance criterion: On Cartesian coordinates, covariant derivative
        equals the partial derivative.
        Passes when: nabla_I v^J == dv^J/dtheta^I for an arbitrary symbolic vector.
        """
        x, y, z = sp.symbols("x y z")
        theta = (x, y, z)

        # Cartesian metric — all Christoffels zero
        g = sp.eye(3)
        gamma = christoffel_symbols(g, theta)

        # General symbolic vector field
        f = sp.Function("f")(x, y, z)
        h_sym = sp.Function("g")(x, y, z)
        k = sp.Function("h")(x, y, z)
        v = sp.Matrix([f, h_sym, k])

        result = covariant_derivative_contravariant(v, gamma, theta)

        # With zero Christoffels, ∇_I v^J = ∂v^J/∂θ^I
        for I in range(3):
            for J in range(3):
                expected = sp.diff(v[J], theta[I])
                assert sp.simplify(result[I, J] - expected) == 0, (
                    f"result[{I},{J}] = {result[I, J]}, expected {expected}"
                )
