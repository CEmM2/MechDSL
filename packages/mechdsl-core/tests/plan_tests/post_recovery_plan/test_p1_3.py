"""Tests for Task P1-3: Lower Neumann BC to per-node force contributions."""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.ir.mechanics_ir import BCType, BoundaryCondition
from mechdsl.lowering.boundary import (
    NodalForceContribution,
    lower_neumann,
    per_node_contributions,
    resolve_traction_vector,
)
from mechdsl.solver.mesh_io import generate_hex8_mesh


@pytest.fixture
def unit_cube_mesh():
    """1x1x1 element on a unit cube — face area exactly 1.0."""
    return generate_hex8_mesh(1, 1, 1, Lx=1.0, Ly=1.0, Lz=1.0)


@pytest.fixture
def two_cube_mesh():
    """2x2x2 element mesh — multi-element face for aggregation tests."""
    return generate_hex8_mesh(2, 2, 2, Lx=1.0, Ly=1.0, Lz=1.0)


class TestTaskP1_3:
    """Tests for Task P1-3: Neumann BC lowering to nodal force contributions."""

    @pytest.mark.unit
    def test_uniform_traction_face_total_force(self, unit_cube_mesh):
        """
        Uniform traction (0, 0, -1000) on the unit-area z1 face yields a
        total nodal force whose sum equals the prescribed traction.
        Acceptance criterion #1.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=(0.0, 0.0, -1000.0),
            surface_tag="z1",
        )
        nbc = lower_neumann(bc, unit_cube_mesh)
        total = nbc.force.sum(axis=0)
        np.testing.assert_allclose(total, [0.0, 0.0, -1000.0], rtol=0, atol=1e-9)

    @pytest.mark.unit
    def test_non_tagged_surface_zero_contribution(self, unit_cube_mesh):
        """
        Nodes outside the tagged surface receive zero contribution.
        Acceptance criterion #2.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=(0.0, 0.0, -1000.0),
            surface_tag="z1",
        )
        nbc = lower_neumann(bc, unit_cube_mesh)
        z1_nodes = unit_cube_mesh.boundary_tags["z1"]
        mask = np.ones(unit_cube_mesh.n_nodes, dtype=bool)
        mask[z1_nodes] = False
        np.testing.assert_array_equal(nbc.force[mask], 0.0)

    @pytest.mark.unit
    def test_index_convention_lowercase_spatial(self, unit_cube_mesh):
        """
        Traction indices are spatial (lowercase i,j,k) per 07-CONVENTIONS:
        the returned force array has shape (n_nodes, 3) with components
        ordered (x, y, z). A pure-x traction must produce only x-component
        forces.
        Acceptance criterion #3.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=(500.0, 0.0, 0.0),
            surface_tag="x1",
        )
        nbc = lower_neumann(bc, unit_cube_mesh)
        # y and z components everywhere zero — no spurious cross-coupling.
        np.testing.assert_array_equal(nbc.force[:, 1], 0.0)
        np.testing.assert_array_equal(nbc.force[:, 2], 0.0)
        # Total x-force matches prescribed traction.
        np.testing.assert_allclose(nbc.force[:, 0].sum(), 500.0, rtol=0, atol=1e-9)

    @pytest.mark.unit
    def test_multi_face_aggregation(self, two_cube_mesh):
        """
        A surface tag covering multiple element faces aggregates per-node
        contributions correctly: total force on z1 in the 2x2x2 mesh still
        equals the prescribed traction.
        Test plan case: multi-face aggregation.
        """
        bc = BoundaryCondition(
            name="top_load",
            bc_type=BCType.NEUMANN,
            traction=(0.0, 0.0, -2000.0),
            surface_tag="z1",
        )
        nbc = lower_neumann(bc, two_cube_mesh)
        np.testing.assert_allclose(nbc.force.sum(axis=0), [0.0, 0.0, -2000.0], rtol=0, atol=1e-9)

    @pytest.mark.unit
    def test_per_node_contributions_sparse_list(self, unit_cube_mesh):
        """
        per_node_contributions returns one entry per face node and zero
        entries for interior nodes.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=(0.0, 0.0, -1000.0),
            surface_tag="z1",
        )
        contribs = per_node_contributions(bc, unit_cube_mesh)
        z1_nodes = set(unit_cube_mesh.boundary_tags["z1"].tolist())
        assert {c.node_id for c in contribs} == z1_nodes
        # Each entry is a NodalForceContribution with 3-tuple force.
        for c in contribs:
            assert isinstance(c, NodalForceContribution)
            assert len(c.force) == 3

    @pytest.mark.unit
    def test_surface_tag_falls_back_to_name(self, unit_cube_mesh):
        """
        When surface_tag is None the BC's `name` is used as the surface
        identifier (effective_surface_tag fallback from P1-1).
        """
        bc = BoundaryCondition(
            name="z1",  # name doubles as surface tag
            bc_type=BCType.NEUMANN,
            traction=(0.0, 0.0, -1000.0),
        )
        nbc = lower_neumann(bc, unit_cube_mesh)
        np.testing.assert_allclose(nbc.force.sum(axis=0), [0.0, 0.0, -1000.0], rtol=0, atol=1e-9)

    @pytest.mark.unit
    def test_dirichlet_bc_rejected(self, unit_cube_mesh):
        """
        Lowering a Dirichlet BC raises — only Neumann BCs lower to nodal
        forces.
        """
        bc = BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET)
        with pytest.raises(ValueError, match="NEUMANN"):
            lower_neumann(bc, unit_cube_mesh)

    @pytest.mark.unit
    def test_symbolic_traction_requires_registry(self, unit_cube_mesh):
        """
        A symbolic-string traction (legacy "t_bar" form) must be resolved
        through a registry, otherwise lowering raises with a clear message.
        """
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction="t_bar",
            surface_tag="z1",
        )
        with pytest.raises(ValueError, match="t_bar"):
            lower_neumann(bc, unit_cube_mesh)
        # Supplying the registry resolves the symbol.
        registry = {"t_bar": (0.0, 0.0, -250.0)}
        nbc = lower_neumann(bc, unit_cube_mesh, traction_registry=registry)
        np.testing.assert_allclose(nbc.force.sum(axis=0), [0.0, 0.0, -250.0], rtol=0, atol=1e-9)

    @pytest.mark.unit
    def test_resolve_traction_vector_from_tuple(self):
        """resolve_traction_vector returns a numpy array for tuple input."""
        bc = BoundaryCondition(
            name="load",
            bc_type=BCType.NEUMANN,
            traction=(1.0, 2.0, 3.0),
        )
        v = resolve_traction_vector(bc)
        assert isinstance(v, np.ndarray)
        np.testing.assert_array_equal(v, [1.0, 2.0, 3.0])
