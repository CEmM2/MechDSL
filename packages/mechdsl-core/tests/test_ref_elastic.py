"""Tests for the handwritten TL Hex8 elastic reference solver.

Verifies correctness of element routines, assembly, and Newton solver
using patch tests, rigid body modes, and a small cantilever problem.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.ref.ref_hex8_elastic import (
    apply_dirichlet,
    assemble_internal_force,
    element_internal_force,
    element_tangent_matvec,
    generate_hex8_mesh,
    solve_elastic,
)

# ---------------------------------------------------------------------------
# Material parameters (steel-like SVK)
# ---------------------------------------------------------------------------

E_YOUNG = 200.0e3  # Young's modulus [MPa]
NU = 0.3  # Poisson's ratio
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _single_element_coords() -> np.ndarray:
    """Reference coordinates for a single unit cube [0,1]^3 Hex8 element.

    Node ordering matches the _HEX8_NODES convention in element_ir:
    bottom face (-z) CCW then top face (+z) CCW.
    """
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )


def _apply_constant_strain(
    X_elem: np.ndarray, eps_xx: float = 0.0, eps_yy: float = 0.0, eps_zz: float = 0.0
) -> np.ndarray:
    """Compute displacements from a constant engineering strain field.

    For small strain, u_i = eps_ii * X_i (no shear).
    """
    u_elem = np.zeros_like(X_elem)
    u_elem[:, 0] = eps_xx * X_elem[:, 0]
    u_elem[:, 1] = eps_yy * X_elem[:, 1]
    u_elem[:, 2] = eps_zz * X_elem[:, 2]
    return u_elem


# ===========================================================================
# Test 1: Mesh generation
# ===========================================================================


class TestMeshGeneration:
    """Verify structured hex mesh generation."""

    def test_node_count(self):
        """Number of nodes = (nx+1)*(ny+1)*(nz+1)."""
        coords, _conn = generate_hex8_mesh(3, 2, 1, 3.0, 2.0, 1.0)
        assert coords.shape == (4 * 3 * 2, 3)

    def test_element_count(self):
        """Number of elements = nx*ny*nz."""
        _coords, conn = generate_hex8_mesh(3, 2, 1, 3.0, 2.0, 1.0)
        assert conn.shape == (3 * 2 * 1, 8)

    def test_single_element(self):
        """1x1x1 mesh has 8 nodes and 1 element."""
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        assert coords.shape == (8, 3)
        assert conn.shape == (1, 8)

    def test_node_bounds(self):
        """All nodes within [0,Lx] x [0,Ly] x [0,Lz]."""
        Lx, Ly, Lz = 5.0, 3.0, 2.0
        coords, _ = generate_hex8_mesh(4, 3, 2, Lx, Ly, Lz)
        assert np.all(coords[:, 0] >= 0.0) and np.all(coords[:, 0] <= Lx)
        assert np.all(coords[:, 1] >= 0.0) and np.all(coords[:, 1] <= Ly)
        assert np.all(coords[:, 2] >= 0.0) and np.all(coords[:, 2] <= Lz)

    def test_connectivity_valid(self):
        """All connectivity indices are valid node indices."""
        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        assert np.all(conn >= 0)
        assert np.all(conn < n_nodes)

    def test_no_degenerate_elements(self):
        """All elements have 8 distinct nodes."""
        _, conn = generate_hex8_mesh(3, 3, 3, 1.0, 1.0, 1.0)
        for e in range(conn.shape[0]):
            assert len(set(conn[e])) == 8, f"Element {e} has duplicate nodes"


# ===========================================================================
# Test 2: Patch test — constant strain field
# ===========================================================================


class TestPatchTest:
    """Patch test: constant strain should produce analytically correct forces.

    For SVK with small strain eps, the Green-Lagrange strain is approximately:
        E_ij ≈ eps_ij + O(eps^2)
    For uniaxial strain eps_xx:
        S_xx = lambda * eps_xx + 2 * mu * eps_xx = (lambda + 2*mu) * eps_xx
        S_yy = S_zz = lambda * eps_xx
    PK1 stress P = F @ S ≈ S for small strain.
    """

    def test_uniaxial_strain(self):
        """Single element with small uniaxial strain eps_xx = 1e-4."""
        X_elem = _single_element_coords()
        eps = 1e-4
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps)

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)

        # Analytical PK2 stress for uniaxial strain (small strain regime)
        # E_xx ≈ eps + eps^2/2, but for small eps, E ≈ eps
        # More precisely, F = diag(1+eps, 1, 1), C = F^T F = diag((1+eps)^2, 1, 1)
        # E = (C - I)/2 = diag(eps + eps^2/2, 0, 0)
        E_exact = eps + eps**2 / 2.0
        S_xx = LAM * E_exact + 2.0 * MU * E_exact
        S_zz = LAM * E_exact  # S_yy = S_zz = lambda * tr(E)

        # P = F @ S, F = diag(1+eps, 1, 1)
        P_xx = (1.0 + eps) * S_xx
        # P_yy = S_yy (used only for documentation of the analytical result)
        P_zz = S_zz

        # The total internal force for a unit cube under constant stress
        # should have forces at nodes that balance. The net x-force on the
        # right face (nodes 1,2,5,6) should equal P_xx * area = P_xx * 1.0
        # and opposite on the left face.

        # Check: sum of all internal forces should be zero (equilibrium)
        f_total = f_int.sum(axis=0)
        np.testing.assert_allclose(f_total, 0.0, atol=1e-8)

        # Right face nodes (x=1): 1, 2, 5, 6
        right_nodes = [1, 2, 5, 6]
        f_right_x = f_int[right_nodes, 0].sum()
        np.testing.assert_allclose(f_right_x, P_xx, rtol=1e-10)

        # Top face nodes (z=1): 4, 5, 6, 7
        top_nodes = [4, 5, 6, 7]
        f_top_z = f_int[top_nodes, 2].sum()
        np.testing.assert_allclose(f_top_z, P_zz, rtol=1e-10)

    def test_hydrostatic_strain(self):
        """Single element with uniform volumetric strain."""
        X_elem = _single_element_coords()
        eps = 1e-4
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps, eps_yy=eps, eps_zz=eps)

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)

        # Equilibrium: total force must be zero
        f_total = f_int.sum(axis=0)
        np.testing.assert_allclose(f_total, 0.0, atol=1e-8)

        # By symmetry, forces on opposite faces should be equal and opposite
        # Right face x-force = -Left face x-force
        right_nodes = [1, 2, 5, 6]
        left_nodes = [0, 3, 4, 7]
        f_right_x = f_int[right_nodes, 0].sum()
        f_left_x = f_int[left_nodes, 0].sum()
        np.testing.assert_allclose(f_right_x, -f_left_x, atol=1e-12)


# ===========================================================================
# Test 3: Rigid body translation
# ===========================================================================


class TestRigidBodyTranslation:
    """Rigid body translation must produce zero internal forces."""

    def test_uniform_translation(self):
        """Uniform displacement produces zero internal force."""
        X_elem = _single_element_coords()
        # Translate all nodes by [1.5, -2.3, 0.7]
        u_elem = np.tile([1.5, -2.3, 0.7], (8, 1))

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)
        np.testing.assert_allclose(f_int, 0.0, atol=1e-10)

    def test_large_translation(self):
        """Large translation should still give zero forces."""
        X_elem = _single_element_coords()
        u_elem = np.tile([100.0, 200.0, 300.0], (8, 1))

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)
        # Floating-point rounding at large translations can produce ~1e-9 noise
        np.testing.assert_allclose(f_int, 0.0, atol=1e-8)


# ===========================================================================
# Test 4: Rigid body rotation (small angle)
# ===========================================================================


class TestRigidBodyRotation:
    """Small rigid rotation should produce near-zero forces.

    Note: SVK is not exactly frame-indifferent for finite rotations (it's a
    limitation of the model), but for small angles the forces should be small.
    """

    def test_small_rotation_about_z(self):
        """Small rotation (1e-4 rad) about z-axis gives near-zero forces."""
        X_elem = _single_element_coords()
        theta = 1e-4  # small angle [rad]

        # Rotation matrix about z-axis
        R = np.array(
            [
                [np.cos(theta), -np.sin(theta), 0.0],
                [np.sin(theta), np.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        # Rotate about centroid
        centroid = X_elem.mean(axis=0)
        X_shifted = X_elem - centroid
        X_rotated = (R @ X_shifted.T).T + centroid
        u_elem = X_rotated - X_elem

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)

        # For small angle, SVK forces should be proportional to theta^2
        # (since E ~ theta^2 for pure rotation). Forces should be very small.
        f_norm = np.linalg.norm(f_int)
        # Green-Lagrange strain is rotationally invariant — forces should be ~0
        assert f_norm < 1e-10, f"Rigid rotation forces too large: {f_norm:.6e}"


# ===========================================================================
# Test 5: Element force symmetry
# ===========================================================================


class TestElementForceSymmetry:
    """Symmetric loading must produce symmetric force response."""

    def test_symmetric_uniaxial(self):
        """Symmetric uniaxial extension: f_y and f_z forces symmetric."""
        X_elem = _single_element_coords()
        eps = 1e-3
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps)

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)

        # Bottom face (z=0) nodes: 0,1,2,3
        # Top face (z=1) nodes: 4,5,6,7
        # By symmetry about z=0.5 plane, z-forces should be antisymmetric
        f_bot_z = f_int[:4, 2].sum()
        f_top_z = f_int[4:, 2].sum()
        np.testing.assert_allclose(f_bot_z, -f_top_z, atol=1e-10)

        # By symmetry about y=0.5 plane, y-forces should be antisymmetric
        front_nodes = [0, 1, 4, 5]  # y=0
        back_nodes = [2, 3, 6, 7]  # y=1
        f_front_y = f_int[front_nodes, 1].sum()
        f_back_y = f_int[back_nodes, 1].sum()
        np.testing.assert_allclose(f_front_y, -f_back_y, atol=1e-10)

    def test_isotropic_symmetry(self):
        """Equal strain in x and y should give symmetric x/y force pattern."""
        X_elem = _single_element_coords()
        eps = 1e-4
        u_elem = _apply_constant_strain(X_elem, eps_xx=eps, eps_yy=eps)

        f_int = element_internal_force(u_elem, X_elem, LAM, MU)

        # Right face x-force should equal back face y-force by isotropy
        right_nodes = [1, 2, 5, 6]
        back_nodes = [2, 3, 6, 7]
        f_right_x = f_int[right_nodes, 0].sum()
        f_back_y = f_int[back_nodes, 1].sum()
        np.testing.assert_allclose(f_right_x, f_back_y, rtol=1e-10)


# ===========================================================================
# Test 6: Tangent matvec consistency
# ===========================================================================


class TestTangentMavec:
    """Verify tangent matvec is consistent with internal force."""

    def test_fd_tangent_vs_direct(self):
        """FD tangent matvec should approximate the true tangent."""
        X_elem = _single_element_coords()
        u_elem = _apply_constant_strain(X_elem, eps_xx=1e-3)
        v_elem = np.random.default_rng(42).standard_normal((8, 3)) * 1e-4

        Kv = element_tangent_matvec(u_elem, X_elem, v_elem, LAM, MU)

        # Verify via independent FD with a different step size
        h2 = 5e-8 * max(float(np.linalg.norm(u_elem)), 1.0)
        f_p = element_internal_force(u_elem + h2 * v_elem, X_elem, LAM, MU)
        f_m = element_internal_force(u_elem - h2 * v_elem, X_elem, LAM, MU)
        Kv_check = (f_p - f_m) / (2.0 * h2)

        # Two FD approximations with different step sizes have O(h^2) error;
        # comparing them amplifies the discrepancy. rtol=1e-3 is appropriate.
        np.testing.assert_allclose(Kv, Kv_check, rtol=1e-3)

    def test_tangent_symmetry(self):
        """Tangent should be symmetric: v^T K w = w^T K v."""
        X_elem = _single_element_coords()
        u_elem = _apply_constant_strain(X_elem, eps_xx=1e-3)
        rng = np.random.default_rng(99)
        v = rng.standard_normal((8, 3)) * 1e-4
        w = rng.standard_normal((8, 3)) * 1e-4

        Kv = element_tangent_matvec(u_elem, X_elem, v, LAM, MU)
        Kw = element_tangent_matvec(u_elem, X_elem, w, LAM, MU)

        vKw = np.sum(v * Kw)
        wKv = np.sum(w * Kv)

        np.testing.assert_allclose(vKw, wKv, rtol=1e-5)


# ===========================================================================
# Test 7: Global assembly
# ===========================================================================


class TestGlobalAssembly:
    """Test global assembly operations."""

    def test_force_balance(self):
        """Global internal force sums to zero for free body."""
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]

        # Apply small uniform strain
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        u[:, 0] = 1e-4 * coords[:, 0]

        f_int = assemble_internal_force(u, coords, conn, LAM, MU)

        # Total force should be zero (Newton's third law)
        f_total = f_int.sum(axis=0)
        np.testing.assert_allclose(f_total, 0.0, atol=1e-8)

    def test_rigid_translation_assembly(self):
        """Global assembly: rigid translation gives zero forces."""
        coords, conn = generate_hex8_mesh(2, 2, 2, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        u = np.tile([3.0, -1.0, 2.0], (n_nodes, 1))

        f_int = assemble_internal_force(u, coords, conn, LAM, MU)
        np.testing.assert_allclose(f_int, 0.0, atol=1e-10)


# ===========================================================================
# Test 8: Dirichlet BC application
# ===========================================================================


class TestDirichletBC:
    """Test Dirichlet boundary condition application."""

    def test_apply_dirichlet(self):
        """Constrained DOFs get prescribed values."""
        n = 6
        u = np.zeros((n, 3), dtype=np.float64)
        bc_mask = np.zeros((n, 3), dtype=bool)
        bc_values = np.zeros((n, 3), dtype=np.float64)

        # Fix first two nodes in all directions
        bc_mask[:2, :] = True
        bc_values[0] = [1.0, 2.0, 3.0]
        bc_values[1] = [4.0, 5.0, 6.0]

        u_out = apply_dirichlet(u, bc_mask, bc_values)

        np.testing.assert_allclose(u_out[0], [1.0, 2.0, 3.0])
        np.testing.assert_allclose(u_out[1], [4.0, 5.0, 6.0])
        # Remaining nodes unchanged
        np.testing.assert_allclose(u_out[2:], 0.0)

    def test_does_not_modify_input(self):
        """apply_dirichlet should not modify the input array."""
        u = np.zeros((4, 3), dtype=np.float64)
        bc_mask = np.zeros((4, 3), dtype=bool)
        bc_mask[0, :] = True
        bc_values = np.ones((4, 3), dtype=np.float64)

        u_original = u.copy()
        _ = apply_dirichlet(u, bc_mask, bc_values)

        np.testing.assert_array_equal(u, u_original)


# ===========================================================================
# Test 9: Cantilever beam (Newton convergence)
# ===========================================================================


class TestCantileverBeam:
    """Small cantilever beam: 4x2x1 mesh, fixed left face, point load right.

    This is not a precision test (coarse mesh), but verifies:
    1. Newton converges
    2. Displacement sign is correct
    3. Reasonable magnitude
    """

    @pytest.fixture
    def cantilever_setup(self) -> dict:
        """Set up a 4x2x1 cantilever beam problem."""
        nx, ny, nz = 4, 2, 1
        Lx, Ly, Lz = 4.0, 2.0, 1.0
        coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
        n_nodes = coords.shape[0]

        # Material: softer for larger displacements on coarse mesh
        E_mod = 1000.0
        nu = 0.3
        lam = E_mod * nu / ((1 + nu) * (1 - 2 * nu))
        mu_val = E_mod / (2 * (1 + nu))

        # BC: fix all DOFs on left face (x=0)
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        # Load: downward point force on the right-top-front corner
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        # Find node at (Lx, Ly, Lz) — right, back, top
        right_top = np.where(
            (np.abs(coords[:, 0] - Lx) < 1e-12)
            & (np.abs(coords[:, 1] - Ly) < 1e-12)
            & (np.abs(coords[:, 2] - Lz) < 1e-12)
        )[0]
        assert len(right_top) == 1, f"Expected 1 corner node, found {len(right_top)}"
        f_ext[right_top[0], 2] = -10.0  # downward in z

        return {
            "coords": coords,
            "conn": conn,
            "lam": lam,
            "mu": mu_val,
            "bc_mask": bc_mask,
            "bc_values": bc_values,
            "f_ext": f_ext,
            "n_nodes": n_nodes,
            "right_top_node": right_top[0],
        }

    def test_newton_converges(self, cantilever_setup: dict):
        """Newton-Raphson converges for the cantilever problem."""
        s = cantilever_setup
        _u, residuals = solve_elastic(
            s["coords"],
            s["conn"],
            s["lam"],
            s["mu"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            tol=1e-8,
            max_iter=50,
        )

        # Should converge (residual decreased significantly)
        assert len(residuals) >= 2, "Should take at least 1 Newton iteration"
        assert residuals[-1] < 1e-8 * residuals[0], (
            f"Newton did not converge: initial={residuals[0]:.6e}, final={residuals[-1]:.6e}"
        )

    def test_tip_displacement_sign(self, cantilever_setup: dict):
        """Tip displacement should be downward (negative z)."""
        s = cantilever_setup
        u, _ = solve_elastic(
            s["coords"],
            s["conn"],
            s["lam"],
            s["mu"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            tol=1e-8,
            max_iter=50,
        )

        tip_uz = u[s["right_top_node"], 2]
        assert tip_uz < 0.0, f"Tip displacement should be negative (downward), got {tip_uz:.6e}"

    def test_fixed_face_zero(self, cantilever_setup: dict):
        """Fixed face displacements should be exactly zero."""
        s = cantilever_setup
        u, _ = solve_elastic(
            s["coords"],
            s["conn"],
            s["lam"],
            s["mu"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            tol=1e-8,
            max_iter=50,
        )

        np.testing.assert_allclose(u[s["bc_mask"]], 0.0, atol=1e-15)

    def test_displacement_magnitude_reasonable(self, cantilever_setup: dict):
        """Tip displacement should be finite and nonzero."""
        s = cantilever_setup
        u, _ = solve_elastic(
            s["coords"],
            s["conn"],
            s["lam"],
            s["mu"],
            s["bc_mask"],
            s["bc_values"],
            s["f_ext"],
            tol=1e-8,
            max_iter=50,
        )

        tip_disp = np.linalg.norm(u[s["right_top_node"]])
        assert tip_disp > 1e-6, f"Displacement too small: {tip_disp:.6e}"
        assert tip_disp < 10.0, f"Displacement unreasonably large: {tip_disp:.6e}"


# ===========================================================================
# Test 10: Zero external load equilibrium
# ===========================================================================


class TestZeroLoadEquilibrium:
    """With zero external load and zero BCs, solution should be zero."""

    def test_zero_load_zero_displacement(self):
        """Zero external load with homogeneous BCs gives zero displacement."""
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]

        # Fix left face
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        # Zero external load
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

        u, _residuals = solve_elastic(coords, conn, LAM, MU, bc_mask, bc_values, f_ext, tol=1e-8)

        np.testing.assert_allclose(u, 0.0, atol=1e-14)
