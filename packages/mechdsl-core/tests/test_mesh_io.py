"""Tests for structured Hex8 mesh I/O (P7.3).

Verifies mesh generation produces correct topology, geometry, and
boundary tags for structured hexahedral meshes.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.solver.mesh_io import (
    HexMesh,
    generate_cook_membrane_mesh,
    generate_hex8_mesh,
    generate_necking_bar_mesh,
    get_face_nodes,
)

# ------------------------------------------------------------------
# 1. 2x2x2 mesh: 27 nodes, 8 elements
# ------------------------------------------------------------------


class TestMesh2x2x2:
    @pytest.fixture
    def mesh(self) -> HexMesh:
        return generate_hex8_mesh(2, 2, 2)

    def test_node_count(self, mesh: HexMesh):
        """2x2x2 mesh has (2+1)*(2+1)*(2+1) = 27 nodes."""
        assert mesh.n_nodes == 27
        assert mesh.coords.shape == (27, 3)

    def test_element_count(self, mesh: HexMesh):
        """2x2x2 mesh has 2*2*2 = 8 elements."""
        assert mesh.n_elem == 8
        assert mesh.connectivity.shape == (8, 8)

    def test_n_dof(self, mesh: HexMesh):
        """Total DOFs = 3 * n_nodes."""
        assert mesh.n_dof == 27 * 3


# ------------------------------------------------------------------
# 2. 4x2x1 mesh: correct counts
# ------------------------------------------------------------------


class TestMesh4x2x1:
    @pytest.fixture
    def mesh(self) -> HexMesh:
        return generate_hex8_mesh(4, 2, 1)

    def test_node_count(self, mesh: HexMesh):
        """4x2x1 mesh has (4+1)*(2+1)*(1+1) = 30 nodes."""
        assert mesh.n_nodes == 30

    def test_element_count(self, mesh: HexMesh):
        """4x2x1 mesh has 4*2*1 = 8 elements."""
        assert mesh.n_elem == 8


# ------------------------------------------------------------------
# 3. All connectivity indices in valid range
# ------------------------------------------------------------------


class TestConnectivityRange:
    @pytest.mark.parametrize(
        "nx, ny, nz",
        [(1, 1, 1), (2, 2, 2), (3, 2, 1), (4, 4, 4)],
    )
    def test_indices_in_range(self, nx: int, ny: int, nz: int):
        """All connectivity indices are in [0, n_nodes)."""
        mesh = generate_hex8_mesh(nx, ny, nz)
        assert mesh.connectivity.min() >= 0
        assert mesh.connectivity.max() < mesh.n_nodes

    @pytest.mark.parametrize(
        "nx, ny, nz",
        [(1, 1, 1), (2, 2, 2), (3, 2, 1)],
    )
    def test_no_duplicate_nodes_in_element(self, nx: int, ny: int, nz: int):
        """Each element has 8 distinct nodes."""
        mesh = generate_hex8_mesh(nx, ny, nz)
        for e in range(mesh.n_elem):
            nodes = mesh.connectivity[e]
            assert len(set(nodes)) == 8, f"Element {e} has duplicate nodes"


# ------------------------------------------------------------------
# 4. Boundary tags exist for all 6 faces
# ------------------------------------------------------------------


class TestBoundaryTagsExist:
    def test_all_six_faces_present(self):
        """All 6 boundary tags exist."""
        mesh = generate_hex8_mesh(2, 2, 2)
        for tag in ("x0", "x1", "y0", "y1", "z0", "z1"):
            assert tag in mesh.boundary_tags, f"Missing boundary tag: {tag}"

    def test_face_nodes_non_empty(self):
        """All boundary faces have at least one node."""
        mesh = generate_hex8_mesh(2, 2, 2)
        for tag in ("x0", "x1", "y0", "y1", "z0", "z1"):
            assert len(mesh.boundary_tags[tag]) > 0, f"Empty face: {tag}"


# ------------------------------------------------------------------
# 5. Face node counts correct
# ------------------------------------------------------------------


class TestFaceNodeCounts:
    def test_face_node_counts_2x2x2(self):
        """For 2x2x2 mesh, x-faces have 3*3=9 nodes, etc."""
        mesh = generate_hex8_mesh(2, 2, 2)
        # x-faces: (ny+1)*(nz+1) = 3*3 = 9
        assert len(get_face_nodes(mesh, "x0")) == 9
        assert len(get_face_nodes(mesh, "x1")) == 9
        # y-faces: (nx+1)*(nz+1) = 3*3 = 9
        assert len(get_face_nodes(mesh, "y0")) == 9
        assert len(get_face_nodes(mesh, "y1")) == 9
        # z-faces: (nx+1)*(ny+1) = 3*3 = 9
        assert len(get_face_nodes(mesh, "z0")) == 9
        assert len(get_face_nodes(mesh, "z1")) == 9

    def test_face_node_counts_4x2x1(self):
        """For 4x2x1 mesh, face node counts vary by direction."""
        mesh = generate_hex8_mesh(4, 2, 1)
        # x-faces: (ny+1)*(nz+1) = 3*2 = 6
        assert len(get_face_nodes(mesh, "x0")) == 6
        assert len(get_face_nodes(mesh, "x1")) == 6
        # y-faces: (nx+1)*(nz+1) = 5*2 = 10
        assert len(get_face_nodes(mesh, "y0")) == 10
        assert len(get_face_nodes(mesh, "y1")) == 10
        # z-faces: (nx+1)*(ny+1) = 5*3 = 15
        assert len(get_face_nodes(mesh, "z0")) == 15
        assert len(get_face_nodes(mesh, "z1")) == 15


# ------------------------------------------------------------------
# 6. Mesh coordinates span correct domain
# ------------------------------------------------------------------


class TestCoordinateDomain:
    def test_default_domain(self):
        """Default mesh spans [0,1]^3."""
        mesh = generate_hex8_mesh(3, 3, 3)
        np.testing.assert_allclose(mesh.coords[:, 0].min(), 0.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 0].max(), 1.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].min(), 0.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].max(), 1.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].min(), 0.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].max(), 1.0, atol=1e-15)

    def test_custom_dimensions(self):
        """Mesh with Lx=2, Ly=3, Lz=4 spans correct domain."""
        mesh = generate_hex8_mesh(2, 2, 2, Lx=2.0, Ly=3.0, Lz=4.0)
        np.testing.assert_allclose(mesh.coords[:, 0].max(), 2.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].max(), 3.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].max(), 4.0, atol=1e-15)

    def test_dtype_float64(self):
        """Coordinates use float64."""
        mesh = generate_hex8_mesh(2, 2, 2)
        assert mesh.coords.dtype == np.float64

    def test_connectivity_dtype_int64(self):
        """Connectivity uses int64."""
        mesh = generate_hex8_mesh(2, 2, 2)
        assert mesh.connectivity.dtype == np.int64


# ------------------------------------------------------------------
# 7. No degenerate elements (all volumes positive)
# ------------------------------------------------------------------


class TestNoDegenerate:
    @pytest.mark.parametrize(
        "nx, ny, nz",
        [(1, 1, 1), (2, 2, 2), (3, 2, 1), (4, 4, 4)],
    )
    def test_all_elements_positive_volume(self, nx: int, ny: int, nz: int):
        """All elements have positive Jacobian determinant at center."""
        mesh = generate_hex8_mesh(nx, ny, nz)
        for e in range(mesh.n_elem):
            X_elem = mesh.coords[mesh.connectivity[e]]
            # Compute Jacobian at element center (xi=eta=zeta=0)
            # dN/dxi at center for Hex8
            dN_dxi = (
                np.array(
                    [
                        [-1, -1, -1],
                        [+1, -1, -1],
                        [+1, +1, -1],
                        [-1, +1, -1],
                        [-1, -1, +1],
                        [+1, -1, +1],
                        [+1, +1, +1],
                        [-1, +1, +1],
                    ],
                    dtype=np.float64,
                )
                / 8.0
            )
            J0 = X_elem.T @ dN_dxi
            detJ0 = np.linalg.det(J0)
            assert detJ0 > 0.0, f"Element {e} has non-positive Jacobian ({detJ0:.6e})"


# ------------------------------------------------------------------
# 8. Custom origin works
# ------------------------------------------------------------------


class TestCustomOrigin:
    def test_shifted_origin(self):
        """Mesh with origin=(1, 2, 3) shifts all coordinates."""
        origin = (1.0, 2.0, 3.0)
        mesh = generate_hex8_mesh(2, 2, 2, Lx=1.0, Ly=1.0, Lz=1.0, origin=origin)
        np.testing.assert_allclose(mesh.coords[:, 0].min(), 1.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 0].max(), 2.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].min(), 2.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].max(), 3.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].min(), 3.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].max(), 4.0, atol=1e-15)

    def test_boundary_tags_with_origin(self):
        """Boundary tags work correctly with shifted origin."""
        origin = (1.0, 2.0, 3.0)
        mesh = generate_hex8_mesh(2, 2, 2, origin=origin)
        # x0 face nodes should have x = 1.0
        x0_nodes = get_face_nodes(mesh, "x0")
        np.testing.assert_allclose(mesh.coords[x0_nodes, 0], 1.0, atol=1e-15)
        # x1 face nodes should have x = 2.0
        x1_nodes = get_face_nodes(mesh, "x1")
        np.testing.assert_allclose(mesh.coords[x1_nodes, 0], 2.0, atol=1e-15)

    def test_negative_origin(self):
        """Mesh with negative origin works."""
        origin = (-1.0, -2.0, -3.0)
        mesh = generate_hex8_mesh(2, 2, 2, Lx=2.0, Ly=4.0, Lz=6.0, origin=origin)
        np.testing.assert_allclose(mesh.coords[:, 0].min(), -1.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 0].max(), 1.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].min(), -2.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 1].max(), 2.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].min(), -3.0, atol=1e-15)
        np.testing.assert_allclose(mesh.coords[:, 2].max(), 3.0, atol=1e-15)


# ------------------------------------------------------------------
# 9. Compatibility with reference solver mesh
# ------------------------------------------------------------------


class TestReferenceCompatibility:
    """Verify that generate_hex8_mesh produces results compatible with
    the reference solver's mesh generation."""

    def test_matches_ref_coords(self):
        """Coords match ref solver's generate_hex8_mesh for same parameters."""
        from tests.ref.ref_hex8_elastic import (
            generate_hex8_mesh as ref_generate,
        )

        ref_coords, ref_conn = ref_generate(2, 2, 2, 1.0, 1.0, 1.0)
        mesh = generate_hex8_mesh(2, 2, 2, Lx=1.0, Ly=1.0, Lz=1.0)

        np.testing.assert_allclose(mesh.coords, ref_coords, atol=1e-15)
        np.testing.assert_array_equal(mesh.connectivity, ref_conn)


# ---------------------------------------------------------------------------
# __post_init__ validation tests for HexMesh
# ---------------------------------------------------------------------------


class TestHexMeshValidation:
    """Tests for HexMesh __post_init__ validators."""

    def test_bad_coords_shape(self) -> None:
        with pytest.raises(ValueError, match="coords must be"):
            HexMesh(
                coords=np.zeros((10,)),
                connectivity=np.zeros((1, 8), dtype=int),
                n_nodes=10,
                n_elem=1,
                boundary_tags={},
            )

    def test_bad_connectivity_shape(self) -> None:
        with pytest.raises(ValueError, match="connectivity must be"):
            HexMesh(
                coords=np.zeros((10, 3)),
                connectivity=np.zeros((1, 4), dtype=int),
                n_nodes=10,
                n_elem=1,
                boundary_tags={},
            )

    def test_n_nodes_mismatch(self) -> None:
        with pytest.raises(ValueError, match="n_nodes"):
            HexMesh(
                coords=np.zeros((10, 3)),
                connectivity=np.zeros((1, 8), dtype=int),
                n_nodes=5,  # wrong
                n_elem=1,
                boundary_tags={},
            )

    def test_n_elem_mismatch(self) -> None:
        with pytest.raises(ValueError, match="n_elem"):
            HexMesh(
                coords=np.zeros((10, 3)),
                connectivity=np.zeros((2, 8), dtype=int),
                n_nodes=10,
                n_elem=1,  # wrong
                boundary_tags={},
            )


# ------------------------------------------------------------------
# Cook's membrane mesh
# ------------------------------------------------------------------


class TestCookMembraneGeometry:
    """Tests for Task P2-1 / P2-2: generate_cook_membrane_mesh().

    Acceptance criteria covered:
    - P2-1 AC1: Corner coordinates match Cook's geometry
    - P2-1 AC2: Boundary tags correctly identify all 6 faces
    - P2-1 AC3: Node count = (nx+1)*(ny+1)*(nz+1)
    - P2-2 AC1: All corner coordinates verified
    - P2-2 AC2: Boundary tags correctly identify fixed (x0) and loaded (x1) faces
    """

    def test_corner_coordinates_match_trapezoid(self) -> None:
        """Verifies: Corner nodes match Cook's trapezoidal geometry.

        Cook's membrane: x in [0,48], left height=44, right height=16, z in [0,1].
        After y-warping: y_warped = y * (44 - 28*x/48) / 44.
        Bottom edge y=0 is unchanged; top edge maps (0,44)->(0,44) and (48,44)->(48,16).

        Passes when: 8 corner coordinates match expected values to machine precision.
        """
        mesh = generate_cook_membrane_mesh(nx=4, ny=4, nz=1)
        coords = mesh.coords
        tol = 1e-10

        # Expected 8 corners of Cook's membrane (x, y, z)
        expected_corners = [
            (0.0, 0.0, 0.0),  # bottom-left-back
            (48.0, 0.0, 0.0),  # bottom-right-back
            (0.0, 44.0, 0.0),  # top-left-back
            (48.0, 16.0, 0.0),  # top-right-back
            (0.0, 0.0, 1.0),  # bottom-left-front
            (48.0, 0.0, 1.0),  # bottom-right-front
            (0.0, 44.0, 1.0),  # top-left-front
            (48.0, 16.0, 1.0),  # top-right-front
        ]

        for ex, ey, ez in expected_corners:
            # Find a node close to this expected corner
            dist = np.sqrt(
                (coords[:, 0] - ex) ** 2 + (coords[:, 1] - ey) ** 2 + (coords[:, 2] - ez) ** 2
            )
            assert dist.min() < tol, (
                f"No node found near expected corner ({ex}, {ey}, {ez}); "
                f"closest dist = {dist.min():.3e}"
            )

    def test_boundary_tags_present_and_nonempty(self) -> None:
        """Verifies: All 6 boundary tags exist and contain correct nodes.

        Passes when: boundary_tags has keys x0, x1, y0, y1, z0, z1,
        each mapping to a non-empty array of node indices.
        """
        mesh = generate_cook_membrane_mesh(nx=4, ny=4, nz=1)
        for tag in ("x0", "x1", "y0", "y1", "z0", "z1"):
            assert tag in mesh.boundary_tags, f"Missing boundary tag '{tag}'"
            assert len(mesh.boundary_tags[tag]) > 0, f"Boundary tag '{tag}' is empty"

    def test_node_and_element_counts(self) -> None:
        """Verifies: Mesh topology matches structured hex convention.

        Passes when: n_nodes == (nx+1)*(ny+1)*(nz+1) and n_elem == nx*ny*nz.
        """
        nx, ny, nz = 4, 4, 2
        mesh = generate_cook_membrane_mesh(nx=nx, ny=ny, nz=nz)
        assert mesh.n_nodes == (nx + 1) * (ny + 1) * (nz + 1)
        assert mesh.n_elem == nx * ny * nz
        assert mesh.coords.shape == (mesh.n_nodes, 3)
        assert mesh.connectivity.shape == (mesh.n_elem, 8)

    def test_positive_jacobians(self) -> None:
        """Verifies: No inverted elements after y-coordinate warping.

        Passes when: All element Jacobian determinants at centroids are positive.
        """
        mesh = generate_cook_membrane_mesh(nx=4, ny=4, nz=1)
        coords = mesh.coords
        conn = mesh.connectivity

        for e in range(mesh.n_elem):
            nodes = conn[e]  # 8 node indices
            pts = coords[nodes]
            # Positive-orientation check: det(J) at the element centre is approximated
            # by the mean tri-linear Jacobian, det(J) ~ vol/8, and must be > 0.
            x = pts[:, 0]
            y = pts[:, 1]
            z = pts[:, 2]
            # Jacobian columns at (xi,eta,zeta)=(0,0,0) for trilinear hex:
            # d/dxi  = 1/8 * [(-x0+x1+x2-x3-x4+x5+x6-x7), same for y,z]
            jcol0 = np.array(
                [
                    (-x[0] + x[1] + x[2] - x[3] - x[4] + x[5] + x[6] - x[7]),
                    (-y[0] + y[1] + y[2] - y[3] - y[4] + y[5] + y[6] - y[7]),
                    (-z[0] + z[1] + z[2] - z[3] - z[4] + z[5] + z[6] - z[7]),
                ]
            )
            jcol1 = np.array(
                [
                    (-x[0] - x[1] + x[2] + x[3] - x[4] - x[5] + x[6] + x[7]),
                    (-y[0] - y[1] + y[2] + y[3] - y[4] - y[5] + y[6] + y[7]),
                    (-z[0] - z[1] + z[2] + z[3] - z[4] - z[5] + z[6] + z[7]),
                ]
            )
            jcol2 = np.array(
                [
                    (-x[0] - x[1] - x[2] - x[3] + x[4] + x[5] + x[6] + x[7]),
                    (-y[0] - y[1] - y[2] - y[3] + y[4] + y[5] + y[6] + y[7]),
                    (-z[0] - z[1] - z[2] - z[3] + z[4] + z[5] + z[6] + z[7]),
                ]
            )
            J = np.column_stack([jcol0, jcol1, jcol2]) / 8.0
            det_J = np.linalg.det(J)
            assert det_J > 0, f"Element {e} has non-positive Jacobian det={det_J:.6e} at centroid"

    def test_fixed_face_x0_nodes(self) -> None:
        """Verifies: x0 boundary tag selects all nodes at x=0 (Dirichlet face).

        Passes when: boundary_tags['x0'] matches np.where(coords[:,0] < tol).
        """
        mesh = generate_cook_membrane_mesh(nx=4, ny=4, nz=1)
        tol = 1e-12
        expected = np.where(np.abs(mesh.coords[:, 0]) < tol)[0].astype(np.int64)
        actual = np.sort(mesh.boundary_tags["x0"])
        np.testing.assert_array_equal(np.sort(expected), actual)

    def test_loaded_face_x1_nodes(self) -> None:
        """Verifies: x1 boundary tag selects all nodes at x=48 (Neumann face).

        Passes when: boundary_tags['x1'] matches np.where(coords[:,0] > 48-tol).
        """
        mesh = generate_cook_membrane_mesh(nx=4, ny=4, nz=1)
        tol = 1e-12
        expected = np.where(np.abs(mesh.coords[:, 0] - 48.0) < tol)[0].astype(np.int64)
        actual = np.sort(mesh.boundary_tags["x1"])
        np.testing.assert_array_equal(np.sort(expected), actual)

    @pytest.mark.parametrize(
        "nx,ny,nz",
        [
            (1, 1, 1),
            (8, 8, 2),
        ],
        ids=["1x1x1", "8x8x2"],
    )
    def test_corners_and_boundary_tags_multi_density(self, nx: int, ny: int, nz: int) -> None:
        """AC1+AC2 at multiple mesh densities: corner coordinates and face tags.

        Parametrized over (1x1x1) and (8x8x2) to verify that the trapezoidal
        warping formula and boundary-tag extraction are density-independent.

        Passes when:
          - All 8 corners match Cook's geometry (x in [0,48], left h=44, right h=16)
          - x0 tag == all nodes with x~0, x1 tag == all nodes with x~48
          - node count == (nx+1)*(ny+1)*(nz+1)
        """
        mesh = generate_cook_membrane_mesh(nx=nx, ny=ny, nz=nz)
        coords = mesh.coords
        tol = 1e-10

        # AC1: verify 8 corners of Cook's trapezoid.
        # Lz is always 1.0 regardless of nz (nz only controls element count).
        expected_corners = [
            (0.0, 0.0, 0.0),
            (48.0, 0.0, 0.0),
            (0.0, 44.0, 0.0),
            (48.0, 16.0, 0.0),
            (0.0, 0.0, 1.0),
            (48.0, 0.0, 1.0),
            (0.0, 44.0, 1.0),
            (48.0, 16.0, 1.0),
        ]
        for ex, ey, ez in expected_corners:
            dist = np.sqrt(
                (coords[:, 0] - ex) ** 2 + (coords[:, 1] - ey) ** 2 + (coords[:, 2] - ez) ** 2
            )
            assert dist.min() < tol, (
                f"nx={nx} ny={ny} nz={nz}: no node near corner "
                f"({ex}, {ey}, {ez}); closest dist={dist.min():.3e}"
            )

        # Node count
        assert mesh.n_nodes == (nx + 1) * (ny + 1) * (nz + 1)

        # AC2: x0 (fixed) face — all nodes at x == 0
        expected_x0 = np.where(np.abs(coords[:, 0]) < 1e-12)[0].astype(np.int64)
        np.testing.assert_array_equal(np.sort(expected_x0), np.sort(mesh.boundary_tags["x0"]))

        # AC2: x1 (loaded) face — all nodes at x == 48
        expected_x1 = np.where(np.abs(coords[:, 0] - 48.0) < 1e-12)[0].astype(np.int64)
        np.testing.assert_array_equal(np.sort(expected_x1), np.sort(mesh.boundary_tags["x1"]))


# ---------------------------------------------------------------------------
# Necking bar mesh geometry
# ---------------------------------------------------------------------------


class TestNeckingBarGeometry:
    """Tests for generate_necking_bar_mesh (Task P3-1, P3-2).

    Acceptance criteria covered:
      AC1: Mesh has correct quarter-model geometry
      AC2: Imperfection reduces cross-section at midplane
      AC3: Boundary tags correctly identify symmetry and loading faces
    """

    def test_geometry_dimensions(self) -> None:
        """Verify mesh spans [0, L/2]x[0, W/2]x[0, W/2] quarter-model domain.

        Acceptance criterion: AC1
        Passes when: all 8 corner nodes of the bounding box are present.
        """
        L, W = 20.0, 2.0
        mesh = generate_necking_bar_mesh(nx=2, ny=2, nz=4, L=L, W=W)
        coords = mesh.coords
        half_L, half_W = L / 2.0, W / 2.0

        # z-axis spans [0, L/2] exactly (no imperfection in z)
        assert np.isclose(coords[:, 2].min(), 0.0), "z min should be 0"
        assert np.isclose(coords[:, 2].max(), half_L), "z max should be L/2"

        # x and y: at z=0 f(0)=0 so no taper → span [0, W/2]
        tol = 1e-12
        z0_mask = np.abs(coords[:, 2] - 0.0) < tol
        assert np.isclose(coords[z0_mask, 0].max(), half_W), "x max at z=0 should be W/2"
        assert np.isclose(coords[z0_mask, 1].max(), half_W), "y max at z=0 should be W/2"

        # x min and y min are always 0 (symmetry planes untouched)
        assert np.isclose(coords[:, 0].min(), 0.0), "x min should be 0"
        assert np.isclose(coords[:, 1].min(), 0.0), "y min should be 0"

    def test_imperfection_reduces_cross_section(self) -> None:
        """Verify imperfection reduces cross-section at z=L/2 midplane.

        Acceptance criterion: AC2
        Passes when: max x-extent and max y-extent at z=L/2 are smaller
        than at z=0 by approximately imperfection * W.
        """
        L, W, imp = 20.0, 2.0, 0.005
        mesh = generate_necking_bar_mesh(nx=2, ny=2, nz=4, L=L, W=W, imperfection=imp)
        coords = mesh.coords
        half_L, half_W = L / 2.0, W / 2.0
        tol = 1e-12

        # At z=0: f(0)=0, scale=1 → full half-width
        z0_mask = np.abs(coords[:, 2] - 0.0) < tol
        x_max_z0 = coords[z0_mask, 0].max()
        y_max_z0 = coords[z0_mask, 1].max()

        # At z=L/2: f(L/2)=1, scale = 1 - imperfection
        z1_mask = np.abs(coords[:, 2] - half_L) < tol
        x_max_z1 = coords[z1_mask, 0].max()
        y_max_z1 = coords[z1_mask, 1].max()

        expected_z1_max = half_W * (1.0 - imp)
        assert np.isclose(x_max_z0, half_W), f"x max at z=0 should be {half_W}"
        assert np.isclose(y_max_z0, half_W), f"y max at z=0 should be {half_W}"
        assert np.isclose(x_max_z1, expected_z1_max, rtol=1e-10), (
            f"x max at z=L/2 should be {expected_z1_max}, got {x_max_z1}"
        )
        assert np.isclose(y_max_z1, expected_z1_max, rtol=1e-10), (
            f"y max at z=L/2 should be {expected_z1_max}, got {y_max_z1}"
        )
        # Midplane is strictly smaller than z=0 face
        assert x_max_z1 < x_max_z0, "x cross-section not reduced at midplane"
        assert y_max_z1 < y_max_z0, "y cross-section not reduced at midplane"

    def test_boundary_tags_symmetry_faces(self) -> None:
        """Verify boundary tags: x0, y0, z0 (symmetry), z1 (loading).

        Acceptance criterion: AC3
        Passes when: each tag contains exactly the nodes on that face.
        """
        L, W = 20.0, 2.0
        nx, ny, nz = 2, 2, 4
        mesh = generate_necking_bar_mesh(nx=nx, ny=ny, nz=nz, L=L, W=W)
        coords = mesh.coords
        half_L = L / 2.0
        tol = 1e-12

        # All four required tags must exist
        for tag in ("x0", "y0", "z0", "z1"):
            assert tag in mesh.boundary_tags, f"boundary tag '{tag}' missing"
            assert len(mesh.boundary_tags[tag]) > 0, f"boundary tag '{tag}' is empty"

        # x0: nodes at x=0 (symmetry plane — not warped)
        x0_nodes = mesh.boundary_tags["x0"]
        assert np.all(np.abs(coords[x0_nodes, 0]) < tol), "x0 tag has nodes not at x=0"
        assert len(x0_nodes) == (ny + 1) * (nz + 1), "x0 node count wrong"

        # y0: nodes at y=0 (symmetry plane — not warped)
        y0_nodes = mesh.boundary_tags["y0"]
        assert np.all(np.abs(coords[y0_nodes, 1]) < tol), "y0 tag has nodes not at y=0"
        assert len(y0_nodes) == (nx + 1) * (nz + 1), "y0 node count wrong"

        # z0: nodes at z=0 (symmetry plane, no imperfection applied here)
        z0_nodes = mesh.boundary_tags["z0"]
        assert np.all(np.abs(coords[z0_nodes, 2]) < tol), "z0 tag has nodes not at z=0"
        assert len(z0_nodes) == (nx + 1) * (ny + 1), "z0 node count wrong"

        # z1: nodes at z=L/2 (prescribed displacement face)
        z1_nodes = mesh.boundary_tags["z1"]
        assert np.all(np.abs(coords[z1_nodes, 2] - half_L) < tol), "z1 tag has nodes not at z=L/2"
        assert len(z1_nodes) == (nx + 1) * (ny + 1), "z1 node count wrong"

    def test_node_element_counts(self) -> None:
        """Verify n_nodes == (nx+1)*(ny+1)*(nz+1) and n_elem == nx*ny*nz.

        Acceptance criterion: AC1 (support)
        Passes when: counts match structured hex convention.
        """
        nx, ny, nz = 3, 3, 6
        mesh = generate_necking_bar_mesh(nx=nx, ny=ny, nz=nz)
        assert mesh.n_nodes == (nx + 1) * (ny + 1) * (nz + 1), "node count mismatch"
        assert mesh.n_elem == nx * ny * nz, "element count mismatch"
        assert mesh.coords.shape == (mesh.n_nodes, 3), "coords shape mismatch"
        assert mesh.connectivity.shape == (mesh.n_elem, 8), "connectivity shape mismatch"

    def test_positive_jacobians(self) -> None:
        """Verify all element Jacobians are positive even with imperfection.

        Acceptance criterion: AC1 (support)
        Passes when: det(J) > 0 at all element centroids.
        """
        mesh = generate_necking_bar_mesh(nx=2, ny=2, nz=4, imperfection=0.005)
        coords = mesh.coords
        conn = mesh.connectivity

        for e in range(mesh.n_elem):
            nodes = conn[e]
            pts = coords[nodes]
            x = pts[:, 0]
            y = pts[:, 1]
            z = pts[:, 2]
            # Trilinear Jacobian columns at centroid (xi=eta=zeta=0)
            jcol0 = np.array(
                [
                    (-x[0] + x[1] + x[2] - x[3] - x[4] + x[5] + x[6] - x[7]),
                    (-y[0] + y[1] + y[2] - y[3] - y[4] + y[5] + y[6] - y[7]),
                    (-z[0] + z[1] + z[2] - z[3] - z[4] + z[5] + z[6] - z[7]),
                ]
            )
            jcol1 = np.array(
                [
                    (-x[0] - x[1] + x[2] + x[3] - x[4] - x[5] + x[6] + x[7]),
                    (-y[0] - y[1] + y[2] + y[3] - y[4] - y[5] + y[6] + y[7]),
                    (-z[0] - z[1] + z[2] + z[3] - z[4] - z[5] + z[6] + z[7]),
                ]
            )
            jcol2 = np.array(
                [
                    (-x[0] - x[1] - x[2] - x[3] + x[4] + x[5] + x[6] + x[7]),
                    (-y[0] - y[1] - y[2] - y[3] + y[4] + y[5] + y[6] + y[7]),
                    (-z[0] - z[1] - z[2] - z[3] + z[4] + z[5] + z[6] + z[7]),
                ]
            )
            J = np.column_stack([jcol0, jcol1, jcol2]) / 8.0
            det_J = np.linalg.det(J)
            assert det_J > 0, f"Element {e} has non-positive Jacobian det={det_J:.6e}"

    @pytest.mark.parametrize("nx,ny,nz", [(1, 1, 2), (2, 2, 4), (4, 4, 8)])
    def test_multi_density(self, nx: int, ny: int, nz: int) -> None:
        """Verify geometry and imperfection are consistent across mesh densities.

        Acceptance criterion: AC1 + AC2 (parametrized)
        Passes when: corner coordinates and imperfection reduction are correct.
        """
        L, W, imp = 20.0, 2.0, 0.005
        mesh = generate_necking_bar_mesh(nx=nx, ny=ny, nz=nz, L=L, W=W, imperfection=imp)
        coords = mesh.coords
        half_L, half_W = L / 2.0, W / 2.0
        tol = 1e-12

        # AC1: correct node/element counts
        assert mesh.n_nodes == (nx + 1) * (ny + 1) * (nz + 1)
        assert mesh.n_elem == nx * ny * nz

        # AC1: z-axis spans [0, L/2]
        assert np.isclose(coords[:, 2].min(), 0.0)
        assert np.isclose(coords[:, 2].max(), half_L)

        # AC1: at z=0, x and y span [0, W/2]
        z0_mask = np.abs(coords[:, 2] - 0.0) < tol
        assert np.isclose(coords[z0_mask, 0].max(), half_W)
        assert np.isclose(coords[z0_mask, 1].max(), half_W)

        # AC2: at z=L/2, cross-section is reduced
        z1_mask = np.abs(coords[:, 2] - half_L) < tol
        expected_max = half_W * (1.0 - imp)
        assert np.isclose(coords[z1_mask, 0].max(), expected_max, rtol=1e-10)
        assert np.isclose(coords[z1_mask, 1].max(), expected_max, rtol=1e-10)
