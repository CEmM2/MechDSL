"""Tests for Phase 3 patch test and rigid body verification.

Covers Tasks P3-T4, P3-T5.
Reference: dev/design_docs/08-VERIFICATION.md §4.1 (patch test), §4.3 (rigid body)
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.verify.patch_test import (
    PatchTestResult,
    RigidBodyResult,
    generate_irregular_mesh,
    run_patch_test,
    run_rigid_body_test,
)

# ---------------------------------------------------------------------------
# Material parameters
# ---------------------------------------------------------------------------
# Unit material parameters are used for element-level patch / rigid body tests.
# The patch test verifies the correctness of the element formulation, which is
# independent of the specific material stiffness values.  Using unit material
# avoids scaling issues: with E=200e3 MPa the round-off floor is ~MU * eps_mach
# ~ 77000 * 2e-16 ~ 1.5e-11, which exceeds the 1e-12 acceptance criterion.
# With unit material (lam=mu=1), round-off is at ~1e-15, well below 1e-12.
LAM = 1.0
MU = 1.0


class TestTaskP3T4:
    """
    Tests for Task P3-T4: Implement run_patch_test() and run_rigid_body_test()

    Objective: Patch test compares solver output against
    analytical.patch_test_reference() (error < 1e-12). Rigid body test
    asserts internal force norm < 1e-12.

    Acceptance criteria covered: [1, 2, 3]
    """

    @pytest.mark.slow
    def test_patch_test_regular_mesh(self):
        """
        Verifies: SVK patch test passes on regular Hex8 mesh
        Acceptance criterion: Patch test passes for SVK on regular mesh (error < 1e-12)
        Passes when: PatchTestResult.error < 1e-12
        """
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)

        # Small uniaxial strain (linearised regime, Green-Lagrange)
        eps = 1e-4
        strain = np.array(
            [
                [eps, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Patch test FAILED on regular mesh: error={result.error:.3e} >= tol={result.tol:.3e}\n"
            f"  {result}"
        )
        assert result.error < 1e-12, (
            f"Patch test error {result.error:.3e} exceeds 1e-12 on regular mesh"
        )

    @pytest.mark.slow
    def test_patch_test_irregular_mesh(self):
        """
        Verifies: SVK patch test passes on irregular Hex8 mesh (perturbed nodes, 10% element size)
        Acceptance criterion: Patch test passes for SVK on irregular mesh (error < 1e-12)
        Passes when: PatchTestResult.error < 1e-12 on perturbed mesh
        """
        coords, conn = generate_irregular_mesh(
            2, 2, 2, 1.0, 1.0, 1.0, perturbation_fraction=0.1, seed=42
        )

        # Small hydrostatic strain
        eps = 1e-4
        strain = np.diag([eps, eps, eps]).astype(np.float64)

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Patch test FAILED on irregular mesh: error={result.error:.3e} >= tol={result.tol:.3e}\n"
            f"  {result}"
        )
        assert result.error < 1e-12, (
            f"Patch test error {result.error:.3e} exceeds 1e-12 on irregular mesh"
        )

    @pytest.mark.slow
    def test_rigid_body_identity(self):
        """
        Verifies: rigid body identity (R=I, t=0) produces zero internal force
        Acceptance criterion: Rigid body test passes (force norm < 1e-12)
        Passes when: RigidBodyResult.force_norm < 1e-12
        """
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)

        rotation = np.eye(3, dtype=np.float64)
        translation = np.zeros(3, dtype=np.float64)

        result = run_rigid_body_test(coords, conn, LAM, MU, rotation, translation, tol=1e-12)

        assert isinstance(result, RigidBodyResult)
        assert result.passed, (
            f"Rigid body identity FAILED: force_norm={result.force_norm:.3e} >= tol={result.tol:.3e}\n"
            f"  {result}"
        )
        assert result.force_norm < 1e-12, (
            f"Rigid body identity force norm {result.force_norm:.3e} exceeds 1e-12"
        )

    @pytest.mark.slow
    def test_rigid_body_rotation(self):
        """
        Verifies: rigid body rotation produces zero internal force
        Acceptance criterion: Rigid body test passes (force norm < 1e-12)
        Passes when: RigidBodyResult.force_norm < 1e-12

        SVK constitutive model: S = lambda*tr(E)*I + 2*mu*E
        For rigid body rotation, F = R (proper rotation), C = R^T R = I,
        E = (C - I)/2 = 0 exactly, so S = 0 and f_int = 0 exactly.

        This test uses unit material parameters (lam=mu=1) so that floating-
        point round-off is at machine epsilon scale (~1e-15), well below 1e-12.
        """
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)

        # 45-degree rotation about z-axis (finite rotation)
        theta = np.pi / 4.0
        rotation = np.array(
            [
                [np.cos(theta), -np.sin(theta), 0.0],
                [np.sin(theta), np.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        translation = np.array([1.0, 0.0, 0.0], dtype=np.float64)

        result = run_rigid_body_test(coords, conn, LAM, MU, rotation, translation, tol=1e-12)

        assert isinstance(result, RigidBodyResult)
        assert result.passed, (
            f"Rigid body rotation FAILED: force_norm={result.force_norm:.3e} >= tol={result.tol:.3e}\n"
            f"  {result}"
        )
        assert result.force_norm < 1e-12, (
            f"Rigid body rotation force norm {result.force_norm:.3e} exceeds 1e-12"
        )


class TestPatchTestFailureRoutes:
    """
    Failure-route analysis: untested paths in run_patch_test() and run_rigid_body_test().

    These are fast tests (no Newton solver, no @pytest.mark.slow) that cover
    boundary conditions of the implementation:
    - Single-element mesh (all nodes are boundary → fallback to all-forces metric)
    - Shear strain (off-diagonal strain component)
    - Large rigid body translation
    - Dataclass __str__ representations
    """

    def test_patch_test_single_element(self):
        """Single element: all 8 nodes are on the boundary, no interior nodes.

        The fallback degrades to checking global force balance.
        """
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        # 1x1x1 mesh = single element
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        assert conn.shape[0] == 1

        eps = 1e-4
        strain = np.array([[eps, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64)

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert isinstance(result, PatchTestResult)
        assert result.n_nodes == 8
        assert result.n_elements == 1
        assert result.interior_force_max == 0.0  # no interior nodes
        assert result.passed, (
            f"Single-element patch test failed: error={result.error:.3e}, "
            f"boundary_force_sum={result.boundary_force_sum:.3e}"
        )
        assert result.error < 1e-12

    def test_patch_test_shear_strain(self):
        """Symmetric shear strain (off-diagonal components) must also be reproduced."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)

        eps = 1e-4
        # Symmetric shear: E_xy = E_yx = eps/2
        strain = np.array(
            [[0.0, eps / 2, 0.0], [eps / 2, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64
        )

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"Shear strain patch test FAILED: error={result.error:.3e}\n  {result}"
        )

    def test_patch_test_hydrostatic_multi_element(self):
        """Hydrostatic strain on a 3x3x3 mesh."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(3, 3, 3, 1.0, 1.0, 1.0)
        eps = 1e-4
        strain = np.diag([eps, eps, eps]).astype(np.float64)

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert result.passed, (
            f"Hydrostatic strain patch test (3x3x3) FAILED: error={result.error:.3e}\n  {result}"
        )

    def test_rigid_body_large_translation(self):
        """Large rigid body translation still gives zero internal force."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)

        rotation = np.eye(3, dtype=np.float64)
        # Translation of 1000 units
        translation = np.array([1000.0, 2000.0, -3000.0], dtype=np.float64)

        result = run_rigid_body_test(coords, conn, LAM, MU, rotation, translation, tol=1e-12)

        assert result.passed, (
            f"Large translation rigid body FAILED: force_norm={result.force_norm:.3e}\n  {result}"
        )

    def test_patch_test_result_str_passed(self):
        """PatchTestResult __str__ shows PASSED status."""
        r = PatchTestResult(
            error=1e-15,
            passed=True,
            tol=1e-12,
            n_nodes=27,
            n_elements=8,
            interior_force_max=1e-15,
            boundary_force_sum=1e-16,
            residual_history=[],
        )
        s = str(r)
        assert "PASSED" in s
        assert "1.000e-15" in s

    def test_patch_test_result_str_failed(self):
        """PatchTestResult __str__ shows FAILED status."""
        r = PatchTestResult(
            error=5e-10,
            passed=False,
            tol=1e-12,
            n_nodes=27,
            n_elements=8,
            interior_force_max=5e-10,
            boundary_force_sum=1e-8,
            residual_history=[1.0, 0.1],
        )
        s = str(r)
        assert "FAILED" in s

    def test_rigid_body_result_str(self):
        """RigidBodyResult __str__ shows PASSED status."""
        r = RigidBodyResult(force_norm=1e-16, passed=True, tol=1e-12, n_nodes=27, n_elements=8)
        s = str(r)
        assert "PASSED" in s
        assert "1.000e-16" in s

    def test_generate_irregular_mesh_shape(self):
        """generate_irregular_mesh returns correct shapes and boundary nodes unchanged."""
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh

        coords_reg, conn_reg = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)
        coords_irr, conn_irr = generate_irregular_mesh(
            2, 2, 2, 1.0, 1.0, 1.0, perturbation_fraction=0.1, seed=0
        )

        # Shapes match regular mesh
        assert coords_irr.shape == coords_reg.shape
        assert conn_irr.shape == conn_reg.shape

        # Connectivity is unchanged
        np.testing.assert_array_equal(conn_irr, conn_reg)

        # Boundary nodes are unchanged
        bnd = (
            (coords_reg[:, 0] < 1e-12)
            | (coords_reg[:, 0] > 1 - 1e-12)
            | (coords_reg[:, 1] < 1e-12)
            | (coords_reg[:, 1] > 1 - 1e-12)
            | (coords_reg[:, 2] < 1e-12)
            | (coords_reg[:, 2] > 1 - 1e-12)
        )
        np.testing.assert_array_equal(coords_irr[bnd], coords_reg[bnd])

        # Interior nodes are different
        interior = ~bnd
        if np.any(interior):
            assert not np.allclose(coords_irr[interior], coords_reg[interior]), (
                "Interior nodes should be perturbed"
            )


@pytest.mark.e2e
class TestTaskP3T5:
    """
    Tests for Task P3-T5: Write patch test

    End-to-end patch test and rigid body test using run_patch_test() and
    run_rigid_body_test() from P3-T4 on generated solvers.

    Acceptance criteria covered: [1, 2, 3]
    """

    @pytest.mark.slow
    def test_svk_patch_test_irregular_mesh(self):
        """
        Verifies: SVK patch test passes on irregular Hex8 mesh via generated solver
        Acceptance criterion: Patch test passes on irregular mesh
        Passes when: displacement error < 1e-12
        """
        coords, conn = generate_irregular_mesh(
            3, 3, 3, 1.0, 1.0, 1.0, perturbation_fraction=0.1, seed=123
        )

        # Biaxial strain: equal stretching in x and y, zero in z
        eps = 1e-4
        strain = np.array(
            [
                [eps, 0.0, 0.0],
                [0.0, eps, 0.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )

        result = run_patch_test(coords, conn, LAM, MU, strain, tol=1e-12)

        assert isinstance(result, PatchTestResult)
        assert result.passed, (
            f"SVK patch test FAILED on irregular 3x3x3 mesh (biaxial strain): "
            f"error={result.error:.3e} >= tol={result.tol:.3e}\n  {result}"
        )
        assert result.error < 1e-12, (
            f"SVK patch test error {result.error:.3e} exceeds 1e-12 on irregular mesh"
        )

    @pytest.mark.slow
    def test_rigid_body_rotation_zero_force(self):
        """
        Verifies: rigid body rotation produces zero internal force via generated solver
        Acceptance criterion: Rigid body test passes
        Passes when: internal force norm < 1e-12
        """
        coords, conn = generate_irregular_mesh(2, 2, 2, 1.0, 1.0, 1.0, seed=99)

        # 30-degree rotation about the z-axis (finite rotation)
        theta = np.pi / 6.0
        rotation = np.array(
            [
                [np.cos(theta), -np.sin(theta), 0.0],
                [np.sin(theta), np.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        translation = np.array([0.5, -0.25, 1.0], dtype=np.float64)

        result = run_rigid_body_test(coords, conn, LAM, MU, rotation, translation, tol=1e-12)

        assert isinstance(result, RigidBodyResult)
        assert result.passed, (
            f"Rigid body rotation (30 degrees about z) FAILED on irregular 2x2x2 mesh: "
            f"force_norm={result.force_norm:.3e} >= tol={result.tol:.3e}\n  {result}"
        )
        assert result.force_norm < 1e-12, (
            f"Rigid body rotation force norm {result.force_norm:.3e} exceeds 1e-12 "
            f"on irregular mesh"
        )
