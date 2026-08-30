"""Tests for boundary condition codegen (P7.2).

Verifies Dirichlet and Neumann BC compilation, merging, and
application to vectors and matvecs.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.boundary_codegen import (
    apply_dirichlet_to_matvec,
    apply_dirichlet_to_vector,
    compile_dirichlet,
    compile_neumann,
    merge_dirichlet,
    merge_neumann,
)
from mechdsl.solver.mesh_io import generate_hex8_mesh


@pytest.fixture
def mesh_2x2x2():
    """Standard 2x2x2 unit-cube mesh for BC tests."""
    return generate_hex8_mesh(2, 2, 2)


# ------------------------------------------------------------------
# 1. Dirichlet: all components fixed on face
# ------------------------------------------------------------------


class TestDirichletAllComponents:
    def test_all_components_fixed(self, mesh_2x2x2):
        """Fixing all components on x0 constrains 9 nodes * 3 components."""
        bc = compile_dirichlet(mesh_2x2x2, "x0", components=(0, 1, 2), value=0.0)
        n_face = len(mesh_2x2x2.boundary_tags["x0"])  # 9
        assert bc.mask.sum() == n_face * 3
        assert bc.mask.shape == (mesh_2x2x2.n_nodes, 3)

    def test_values_are_zero(self, mesh_2x2x2):
        """Default value=0.0 sets all constrained values to zero."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")
        np.testing.assert_allclose(bc.values[bc.mask], 0.0, atol=1e-15)


# ------------------------------------------------------------------
# 2. Dirichlet: single component fixed
# ------------------------------------------------------------------


class TestDirichletSingleComponent:
    def test_only_x_fixed(self, mesh_2x2x2):
        """Fixing only x-component on x0 constrains 9 nodes * 1 component."""
        bc = compile_dirichlet(mesh_2x2x2, "x0", components=(0,))
        n_face = len(mesh_2x2x2.boundary_tags["x0"])
        assert bc.mask.sum() == n_face
        # Only column 0 should be True
        assert bc.mask[:, 0].sum() == n_face
        assert bc.mask[:, 1].sum() == 0
        assert bc.mask[:, 2].sum() == 0

    def test_only_z_fixed(self, mesh_2x2x2):
        """Fixing only z-component on z1 constrains correct nodes."""
        bc = compile_dirichlet(mesh_2x2x2, "z1", components=(2,))
        n_face = len(mesh_2x2x2.boundary_tags["z1"])
        assert bc.mask[:, 2].sum() == n_face
        assert bc.mask[:, 0].sum() == 0
        assert bc.mask[:, 1].sum() == 0


# ------------------------------------------------------------------
# 3. Dirichlet: correct mask and values
# ------------------------------------------------------------------


class TestDirichletMaskValues:
    def test_nonzero_prescribed_value(self, mesh_2x2x2):
        """Prescribed value=0.1 appears at constrained locations."""
        bc = compile_dirichlet(mesh_2x2x2, "x1", components=(0,), value=0.1)
        face_nodes = mesh_2x2x2.boundary_tags["x1"]
        # Check mask
        for n in face_nodes:
            assert bc.mask[n, 0] is np.True_
        # Check values
        np.testing.assert_allclose(bc.values[face_nodes, 0], 0.1, atol=1e-15)

    def test_unconstrained_nodes_have_false_mask(self, mesh_2x2x2):
        """Nodes not on the face have False mask."""
        bc = compile_dirichlet(mesh_2x2x2, "x0", components=(0, 1, 2))
        face_nodes = set(mesh_2x2x2.boundary_tags["x0"])
        for n in range(mesh_2x2x2.n_nodes):
            if n not in face_nodes:
                assert not bc.mask[n].any(), f"Node {n} should be unconstrained"


# ------------------------------------------------------------------
# 4. Neumann: uniform traction on face produces correct force
# ------------------------------------------------------------------


class TestNeumannForce:
    def test_total_force_equals_traction_times_area(self, mesh_2x2x2):
        """Total force on face = traction * face_area."""
        traction = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        bc = compile_neumann(mesh_2x2x2, "x1", traction)

        # For unit cube, x-face area = Ly * Lz = 1.0
        total_force = bc.force.sum(axis=0)
        np.testing.assert_allclose(total_force, [1.0, 0.0, 0.0], atol=1e-14)

    def test_total_force_custom_dimensions(self):
        """Total force correct for non-unit mesh."""
        mesh = generate_hex8_mesh(2, 2, 2, Lx=2.0, Ly=3.0, Lz=4.0)
        traction = np.array([0.0, 5.0, 0.0], dtype=np.float64)
        bc = compile_neumann(mesh, "x0", traction)

        # x-face area = Ly * Lz = 3 * 4 = 12
        total_force = bc.force.sum(axis=0)
        np.testing.assert_allclose(total_force, [0.0, 60.0, 0.0], atol=1e-12)


# ------------------------------------------------------------------
# 5. Neumann: traction distributed over correct nodes
# ------------------------------------------------------------------


class TestNeumannDistribution:
    def test_only_face_nodes_have_force(self, mesh_2x2x2):
        """Only nodes on the face receive nonzero force."""
        traction = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        bc = compile_neumann(mesh_2x2x2, "y1", traction)

        face_nodes = set(mesh_2x2x2.boundary_tags["y1"])
        for n in range(mesh_2x2x2.n_nodes):
            if n not in face_nodes:
                np.testing.assert_allclose(
                    bc.force[n],
                    0.0,
                    atol=1e-15,
                    err_msg=f"Node {n} should have zero force",
                )
            else:
                assert np.linalg.norm(bc.force[n]) > 0.0, f"Face node {n} should have nonzero force"

    def test_uniform_distribution(self, mesh_2x2x2):
        """All face nodes receive equal force."""
        traction = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        bc = compile_neumann(mesh_2x2x2, "x1", traction)

        face_nodes = mesh_2x2x2.boundary_tags["x1"]
        forces_on_face = bc.force[face_nodes]
        # All rows should be identical
        for i in range(1, len(face_nodes)):
            np.testing.assert_allclose(forces_on_face[i], forces_on_face[0], atol=1e-15)


# ------------------------------------------------------------------
# 6. Merge dirichlet: multiple faces combined
# ------------------------------------------------------------------


class TestMergeDirichlet:
    def test_merge_two_faces(self, mesh_2x2x2):
        """Merging x0 (all) and y0 (all) gives union of constrained DOFs."""
        bc_x0 = compile_dirichlet(mesh_2x2x2, "x0")
        bc_y0 = compile_dirichlet(mesh_2x2x2, "y0")
        merged = merge_dirichlet([bc_x0, bc_y0], mesh_2x2x2.n_nodes)

        # Union of masks
        expected_mask = bc_x0.mask | bc_y0.mask
        np.testing.assert_array_equal(merged.mask, expected_mask)

    def test_merge_different_components(self, mesh_2x2x2):
        """Merging x-only and y-only BCs on same face gives both constrained."""
        bc_x = compile_dirichlet(mesh_2x2x2, "x0", components=(0,))
        bc_y = compile_dirichlet(mesh_2x2x2, "x0", components=(1,))
        merged = merge_dirichlet([bc_x, bc_y], mesh_2x2x2.n_nodes)

        face_nodes = mesh_2x2x2.boundary_tags["x0"]
        for n in face_nodes:
            assert merged.mask[n, 0]
            assert merged.mask[n, 1]
            assert not merged.mask[n, 2]

    def test_merge_preserves_values(self, mesh_2x2x2):
        """Later BC overwrites earlier where masks overlap."""
        bc1 = compile_dirichlet(mesh_2x2x2, "x0", components=(0,), value=1.0)
        bc2 = compile_dirichlet(mesh_2x2x2, "x0", components=(0,), value=2.0)
        merged = merge_dirichlet([bc1, bc2], mesh_2x2x2.n_nodes)

        face_nodes = mesh_2x2x2.boundary_tags["x0"]
        # bc2 overwrites bc1
        np.testing.assert_allclose(merged.values[face_nodes, 0], 2.0, atol=1e-15)


# ------------------------------------------------------------------
# 7. Merge neumann: forces summed
# ------------------------------------------------------------------


class TestMergeNeumann:
    def test_forces_summed(self, mesh_2x2x2):
        """Merging two Neumann BCs sums the forces."""
        t1 = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        t2 = np.array([0.0, 2.0, 0.0], dtype=np.float64)
        bc1 = compile_neumann(mesh_2x2x2, "x1", t1)
        bc2 = compile_neumann(mesh_2x2x2, "y1", t2)
        merged = merge_neumann([bc1, bc2], mesh_2x2x2.n_nodes)

        # Total force = sum of both
        total = merged.force.sum(axis=0)
        expected = bc1.force.sum(axis=0) + bc2.force.sum(axis=0)
        np.testing.assert_allclose(total, expected, atol=1e-14)

    def test_same_face_forces_add(self, mesh_2x2x2):
        """Two tractions on the same face produce doubled force."""
        t = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        bc1 = compile_neumann(mesh_2x2x2, "x1", t)
        bc2 = compile_neumann(mesh_2x2x2, "x1", t)
        merged = merge_neumann([bc1, bc2], mesh_2x2x2.n_nodes)

        total = merged.force.sum(axis=0)
        np.testing.assert_allclose(total, [2.0, 0.0, 0.0], atol=1e-14)


# ------------------------------------------------------------------
# 8. apply_dirichlet_to_vector: constrained DOFs zeroed
# ------------------------------------------------------------------


class TestApplyDirichletToVector:
    def test_constrained_dofs_zeroed(self, mesh_2x2x2):
        """Constrained DOFs are set to zero."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")
        v = np.ones((mesh_2x2x2.n_nodes, 3), dtype=np.float64)
        result = apply_dirichlet_to_vector(v, bc)

        # Constrained DOFs should be zero
        np.testing.assert_allclose(result[bc.mask], 0.0, atol=1e-15)

    def test_free_dofs_unchanged(self, mesh_2x2x2):
        """Free DOFs are not modified."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")
        rng = np.random.default_rng(42)
        v = rng.standard_normal((mesh_2x2x2.n_nodes, 3))
        result = apply_dirichlet_to_vector(v, bc)

        free_mask = ~bc.mask
        np.testing.assert_allclose(result[free_mask], v[free_mask], atol=1e-15)

    def test_does_not_modify_input(self, mesh_2x2x2):
        """Input vector is not modified in place."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")
        v = np.ones((mesh_2x2x2.n_nodes, 3), dtype=np.float64)
        v_copy = v.copy()
        _ = apply_dirichlet_to_vector(v, bc)
        np.testing.assert_array_equal(v, v_copy)


# ------------------------------------------------------------------
# 9. apply_dirichlet_to_matvec: constrained DOFs produce zero
# ------------------------------------------------------------------


class TestApplyDirichletToMatvec:
    def test_constrained_dofs_zero_in_output(self, mesh_2x2x2):
        """Constrained DOFs in matvec output are zero."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")

        def identity_matvec(v):
            return v.copy()

        wrapped = apply_dirichlet_to_matvec(identity_matvec, bc)

        rng = np.random.default_rng(42)
        v = rng.standard_normal(mesh_2x2x2.n_dof)
        result = wrapped(v)

        flat_mask = bc.mask.ravel()
        np.testing.assert_allclose(result[flat_mask], 0.0, atol=1e-15)

    def test_constrained_input_zeroed(self, mesh_2x2x2):
        """Constrained DOFs in input are zeroed before calling inner matvec."""
        bc = compile_dirichlet(mesh_2x2x2, "x0")

        captured_inputs = []

        def spy_matvec(v):
            captured_inputs.append(v.copy())
            return v.copy()

        wrapped = apply_dirichlet_to_matvec(spy_matvec, bc)

        v = np.ones(mesh_2x2x2.n_dof, dtype=np.float64)
        _ = wrapped(v)

        flat_mask = bc.mask.ravel()
        np.testing.assert_allclose(captured_inputs[0][flat_mask], 0.0, atol=1e-15)

    def test_free_dofs_pass_through(self, mesh_2x2x2):
        """Free DOFs pass through the identity matvec unchanged."""
        bc = compile_dirichlet(mesh_2x2x2, "z1", components=(2,))

        def identity_matvec(v):
            return v.copy()

        wrapped = apply_dirichlet_to_matvec(identity_matvec, bc)

        rng = np.random.default_rng(99)
        v = rng.standard_normal(mesh_2x2x2.n_dof)
        result = wrapped(v)

        flat_mask = bc.mask.ravel()
        free_mask = ~flat_mask
        np.testing.assert_allclose(result[free_mask], v[free_mask], atol=1e-15)

    def test_symmetric_matvec(self, mesh_2x2x2):
        """Wrapped matvec of SPD matrix preserves symmetry on free DOFs."""
        bc = compile_dirichlet(mesh_2x2x2, "x0", components=(0,))
        ndof = mesh_2x2x2.n_dof

        # Create a simple SPD matrix (diagonal)
        rng = np.random.default_rng(123)
        diag = rng.uniform(1.0, 10.0, size=ndof)

        def diag_matvec(v):
            return diag * v

        wrapped = apply_dirichlet_to_matvec(diag_matvec, bc)

        # Check: for free DOFs, e_i^T A e_j = e_j^T A e_i
        flat_mask = bc.mask.ravel()
        free_indices = np.where(~flat_mask)[0]
        # Check a few pairs
        for _ in range(5):
            i, j = rng.choice(free_indices, size=2, replace=False)
            ei = np.zeros(ndof, dtype=np.float64)
            ej = np.zeros(ndof, dtype=np.float64)
            ei[i] = 1.0
            ej[j] = 1.0
            Aei = wrapped(ei)
            Aej = wrapped(ej)
            np.testing.assert_allclose(
                Aei[j],
                Aej[i],
                atol=1e-14,
                err_msg=f"Symmetry broken at ({i}, {j})",
            )


# ---------------------------------------------------------------------------
# Invalid face name error path
# ---------------------------------------------------------------------------


class TestBoundaryCodegenErrorPaths:
    """T4: Invalid face name and axis validation."""

    def test_invalid_face_name_raises(self) -> None:
        """Unknown face name raises KeyError from boundary_tags lookup."""
        mesh = generate_hex8_mesh(2, 2, 2)
        with pytest.raises(KeyError):
            compile_neumann(mesh, "invalid_face", np.array([1.0, 0.0, 0.0]))

    def test_invalid_axis_raises(self) -> None:
        """Face name not starting with x/y/z raises ValueError."""
        mesh = generate_hex8_mesh(2, 2, 2)
        # Inject a fake boundary tag so it doesn't raise KeyError first
        mesh.boundary_tags["w0"] = mesh.boundary_tags["x0"]
        with pytest.raises(ValueError, match="Cannot determine face orientation"):
            compile_neumann(mesh, "w0", np.array([1.0, 0.0, 0.0]))


# ---------------------------------------------------------------------------
# __post_init__ validation tests for DirichletBC/NeumannBC
# ---------------------------------------------------------------------------


class TestBCValidation:
    """Tests for DirichletBC and NeumannBC __post_init__ validators."""

    def test_dirichlet_bad_mask_shape(self) -> None:
        from mechdsl.codegen.boundary_codegen import DirichletBC

        with pytest.raises(ValueError, match="mask must be"):
            DirichletBC(
                mask=np.zeros((10,), dtype=bool),
                values=np.zeros((10, 3)),
            )

    def test_dirichlet_shape_mismatch(self) -> None:
        from mechdsl.codegen.boundary_codegen import DirichletBC

        with pytest.raises(ValueError, match="mask shape"):
            DirichletBC(
                mask=np.zeros((10, 3), dtype=bool),
                values=np.zeros((5, 3)),
            )

    def test_neumann_bad_force_shape(self) -> None:
        from mechdsl.codegen.boundary_codegen import NeumannBC

        with pytest.raises(ValueError, match="force must be"):
            NeumannBC(force=np.zeros((10,)))
