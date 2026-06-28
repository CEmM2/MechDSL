"""Tests for Phase 10 prerequisite mesh utilities."""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.verify.benchmarks._meshes import (
    BenchmarkMesh,
    cantilever_mesh,
    cook_membrane_mesh,
    structured_block_mesh,
    validate_positive_jacobians,
)


class TestTaskP1_1:
    """Tests for Task P1-1: Mesh datamodel and validation helpers."""

    @pytest.mark.unit
    def test_valid_mesh_datamodel_construction(self) -> None:
        """Verifies the mesh datamodel stores geometry and boundary sets."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)

        assert mesh.element_type == "hex8"
        assert mesh.coordinates.shape == (8, 3)
        assert mesh.connectivity.shape == (1, 8)
        assert mesh.n_nodes == 8
        assert mesh.n_elements == 1
        assert {"x_min", "x_max", "y_min", "y_max", "z_min", "z_max"} <= set(mesh.boundary_nodes)

    @pytest.mark.unit
    def test_invalid_connectivity_shape_is_rejected(self) -> None:
        """Verifies malformed connectivity fails before downstream use."""
        coords = np.zeros((8, 3), dtype=np.float64)
        bad_conn = np.zeros((1, 7), dtype=np.int64)

        with pytest.raises(ValueError, match="connectivity"):
            BenchmarkMesh(element_type="hex8", coordinates=coords, connectivity=bad_conn)

    @pytest.mark.unit
    def test_non_positive_jacobian_is_rejected(self) -> None:
        """Verifies inverted element orientation is detected."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)
        inverted = mesh.connectivity.copy()
        inverted[0, [0, 1]] = inverted[0, [1, 0]]
        bad_mesh = BenchmarkMesh(
            element_type="hex8",
            coordinates=mesh.coordinates,
            connectivity=inverted,
            boundary_nodes=mesh.boundary_nodes,
        )

        with pytest.raises(ValueError, match="Non-positive Jacobian"):
            validate_positive_jacobians(bad_mesh)


class TestTaskP1_2:
    """Tests for Task P1-2: Phase 10 Hex8/Tet10/Hex20 mesh builders."""

    @pytest.mark.unit
    @pytest.mark.parametrize("element_type", ["hex8", "tet10", "hex20"])
    def test_structured_block_meshes_have_positive_jacobians(self, element_type: str) -> None:
        """Verifies every supported block mesh has positive quadrature Jacobians."""
        mesh = structured_block_mesh(element_type, length=2.0, width=1.0, height=0.5)

        dets = validate_positive_jacobians(mesh)

        assert dets.shape[0] == mesh.n_elements
        assert np.all(dets > 0.0)
        assert mesh.boundary_nodes["x_min"].size > 0
        assert mesh.boundary_nodes["x_max"].size > 0

    @pytest.mark.unit
    @pytest.mark.parametrize("element_type", ["hex8", "tet10", "hex20"])
    def test_cantilever_mesh_has_fixed_and_load_aliases(self, element_type: str) -> None:
        """Verifies cantilever boundary aliases are deterministic."""
        mesh = cantilever_mesh(element_type, length=4.0, width=1.0, height=1.0, nx=2)

        validate_positive_jacobians(mesh)
        assert np.array_equal(mesh.boundary_nodes["fixed"], mesh.boundary_nodes["x_min"])
        assert np.array_equal(mesh.boundary_nodes["load"], mesh.boundary_nodes["x_max"])

    @pytest.mark.unit
    def test_cook_tet10_mesh_preserves_loaded_and_fixed_boundaries(self) -> None:
        """Verifies Cook Tet10 mesh generation keeps boundary tags after warping."""
        mesh = cook_membrane_mesh("tet10", nx=1, ny=1, nz=1)

        validate_positive_jacobians(mesh)
        assert np.array_equal(mesh.boundary_nodes["fixed"], mesh.boundary_nodes["x_min"])
        assert np.array_equal(mesh.boundary_nodes["load"], mesh.boundary_nodes["x_max"])
        assert mesh.boundary_nodes["top"].size > 0
