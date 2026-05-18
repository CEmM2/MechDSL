"""Benchmark-local mesh helpers for Phase 10 prerequisite work.

This module is intentionally geometry-only: it creates coordinates,
connectivity, and boundary node sets, then validates element orientation. It
does not assemble residuals, choose materials, or run benchmark solvers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import numpy as np

from mechdsl.ir.element_factory import ElementFactory

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.ir.element_ir import ElementIR

_NODE_COUNT: Final[dict[str, int]] = {"hex8": 8, "tet10": 10, "hex20": 20}
_HEX20_EDGE_ORDER: Final[tuple[tuple[int, int], ...]] = (
    (0, 1),
    (1, 2),
    (3, 2),
    (0, 3),
    (4, 5),
    (5, 6),
    (7, 6),
    (4, 7),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)
_TET10_EDGE_ORDER: Final[tuple[tuple[int, int], ...]] = (
    (0, 1),
    (1, 2),
    (2, 0),
    (0, 3),
    (1, 3),
    (2, 3),
)
_HEX8_TO_TETS: Final[tuple[tuple[int, int, int, int], ...]] = (
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
    (0, 5, 1, 6),
)


@dataclass(frozen=True)
class BenchmarkMesh:
    """Geometry data shared by Phase 10 benchmark prerequisites."""

    element_type: str
    coordinates: NDArray[np.float64]
    connectivity: NDArray[np.int64]
    boundary_nodes: dict[str, NDArray[np.int64]] = field(default_factory=dict)
    face_tags: dict[str, NDArray[np.int64]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.element_type not in _NODE_COUNT:
            raise ValueError(
                f"Unsupported benchmark mesh element_type {self.element_type!r}; "
                f"expected one of {sorted(_NODE_COUNT)}."
            )

        coords = np.asarray(self.coordinates, dtype=np.float64)
        conn = np.asarray(self.connectivity, dtype=np.int64)
        if coords.ndim != 2 or coords.shape[1] != 3:
            raise ValueError(f"coordinates must have shape (n_nodes, 3), got {coords.shape}")
        if conn.ndim != 2 or conn.shape[1] != _NODE_COUNT[self.element_type]:
            expected = _NODE_COUNT[self.element_type]
            raise ValueError(
                f"{self.element_type} connectivity must have shape (n_elem, {expected}), "
                f"got {conn.shape}"
            )
        if conn.size and (int(conn.min()) < 0 or int(conn.max()) >= coords.shape[0]):
            raise ValueError("connectivity contains node ids outside the coordinate array")

        boundaries = {
            name: _validate_node_set(name, nodes, coords.shape[0])
            for name, nodes in self.boundary_nodes.items()
        }
        faces = {
            name: _validate_node_set(name, nodes, coords.shape[0])
            for name, nodes in self.face_tags.items()
        }

        object.__setattr__(self, "coordinates", coords)
        object.__setattr__(self, "connectivity", conn)
        object.__setattr__(self, "boundary_nodes", boundaries)
        object.__setattr__(self, "face_tags", faces)

    @property
    def n_nodes(self) -> int:
        return int(self.coordinates.shape[0])

    @property
    def n_elements(self) -> int:
        return int(self.connectivity.shape[0])


def structured_block_mesh(
    element_type: str,
    *,
    length: float = 1.0,
    width: float = 1.0,
    height: float = 1.0,
    nx: int = 1,
    ny: int = 1,
    nz: int = 1,
) -> BenchmarkMesh:
    """Build a structured block mesh for Phase 10 benchmark prerequisites."""

    _validate_block_inputs(length=length, width=width, height=height, nx=nx, ny=ny, nz=nz)
    hex8 = _structured_hex8_block(length=length, width=width, height=height, nx=nx, ny=ny, nz=nz)
    if element_type == "hex8":
        return hex8
    if element_type == "hex20":
        return _upgrade_hex8_to_hex20(hex8)
    if element_type == "tet10":
        return _split_hex8_to_tet10(hex8)
    raise ValueError(f"Unsupported structured block element_type {element_type!r}")


def cantilever_mesh(
    element_type: str,
    *,
    length: float = 10.0,
    width: float = 1.0,
    height: float = 1.0,
    nx: int = 2,
    ny: int = 1,
    nz: int = 1,
) -> BenchmarkMesh:
    """Build a block cantilever mesh with fixed and loaded end aliases."""

    mesh = structured_block_mesh(
        element_type,
        length=length,
        width=width,
        height=height,
        nx=nx,
        ny=ny,
        nz=nz,
    )
    boundaries = dict(mesh.boundary_nodes)
    boundaries["fixed"] = boundaries["x_min"]
    boundaries["load"] = boundaries["x_max"]
    return BenchmarkMesh(
        element_type=mesh.element_type,
        coordinates=mesh.coordinates,
        connectivity=mesh.connectivity,
        boundary_nodes=boundaries,
        face_tags=dict(mesh.face_tags),
    )


def cook_membrane_mesh(
    element_type: str,
    *,
    length: float = 48.0,
    left_height: float = 44.0,
    right_height: float = 16.0,
    thickness: float = 1.0,
    nx: int = 2,
    ny: int = 2,
    nz: int = 1,
) -> BenchmarkMesh:
    """Build a Cook-style trapezoidal mesh with fixed/load aliases."""

    if right_height <= 0.0 or right_height >= left_height:
        raise ValueError("right_height must be positive and smaller than left_height")
    mesh = structured_block_mesh(
        element_type,
        length=length,
        width=left_height,
        height=thickness,
        nx=nx,
        ny=ny,
        nz=nz,
    )
    coords = mesh.coordinates.copy()
    x = coords[:, 0]
    y_rect = coords[:, 1]
    top_height = left_height + (right_height - left_height) * (x / length)
    coords[:, 1] = y_rect * top_height / left_height

    boundaries = dict(mesh.boundary_nodes)
    boundaries["fixed"] = boundaries["x_min"]
    boundaries["load"] = boundaries["x_max"]
    boundaries["bottom"] = boundaries["y_min"]
    boundaries["top"] = boundaries["y_max"]
    return BenchmarkMesh(
        element_type=mesh.element_type,
        coordinates=coords,
        connectivity=mesh.connectivity,
        boundary_nodes=boundaries,
        face_tags=dict(mesh.face_tags),
    )


def jacobian_determinants(mesh: BenchmarkMesh, element: ElementIR | None = None) -> NDArray[np.float64]:
    """Return element Jacobian determinants at each quadrature point."""

    elem = element or ElementFactory.create(mesh.element_type)
    if elem.n_nodes != mesh.connectivity.shape[1]:
        raise ValueError(
            f"Element {elem.element_type} expects {elem.n_nodes} nodes, "
            f"got mesh connectivity width {mesh.connectivity.shape[1]}"
        )

    dets = np.empty((mesh.n_elements, elem.quadrature.n_points), dtype=np.float64)
    for e, conn in enumerate(mesh.connectivity):
        X = mesh.coordinates[conn]
        for q, point in enumerate(elem.quadrature.points):
            grad = elem.basis.gradient(float(point[0]), float(point[1]), float(point[2]))
            J = X.T @ grad
            dets[e, q] = float(np.linalg.det(J))
    return dets


def validate_positive_jacobians(
    mesh: BenchmarkMesh,
    element: ElementIR | None = None,
    *,
    tol: float = 1e-12,
) -> NDArray[np.float64]:
    """Validate that all element quadrature Jacobians are positive."""

    dets = jacobian_determinants(mesh, element)
    bad = np.argwhere(dets <= tol)
    if bad.size:
        e, q = (int(bad[0, 0]), int(bad[0, 1]))
        raise ValueError(
            f"Non-positive Jacobian for {mesh.element_type} element {e}, "
            f"quadrature point {q}: detJ={dets[e, q]:.6e}"
        )
    return dets


def _validate_node_set(name: str, nodes: NDArray[np.int64], n_nodes: int) -> NDArray[np.int64]:
    arr = np.asarray(nodes, dtype=np.int64)
    if arr.ndim != 1:
        raise ValueError(f"boundary node set {name!r} must be 1D, got shape {arr.shape}")
    if arr.size and (int(arr.min()) < 0 or int(arr.max()) >= n_nodes):
        raise ValueError(f"boundary node set {name!r} contains node ids outside the mesh")
    return np.unique(arr)


def _validate_block_inputs(
    *,
    length: float,
    width: float,
    height: float,
    nx: int,
    ny: int,
    nz: int,
) -> None:
    if length <= 0.0 or width <= 0.0 or height <= 0.0:
        raise ValueError("block dimensions must be positive")
    if nx <= 0 or ny <= 0 or nz <= 0:
        raise ValueError("block subdivisions nx, ny, nz must be positive")


def _structured_hex8_block(
    *,
    length: float,
    width: float,
    height: float,
    nx: int,
    ny: int,
    nz: int,
) -> BenchmarkMesh:
    xs = np.linspace(0.0, length, nx + 1)
    ys = np.linspace(0.0, width, ny + 1)
    zs = np.linspace(0.0, height, nz + 1)
    coords = np.array([[x, y, z] for z in zs for y in ys for x in xs], dtype=np.float64)

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    conn: list[list[int]] = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                conn.append(
                    [
                        node_id(i, j, k),
                        node_id(i + 1, j, k),
                        node_id(i + 1, j + 1, k),
                        node_id(i, j + 1, k),
                        node_id(i, j, k + 1),
                        node_id(i + 1, j, k + 1),
                        node_id(i + 1, j + 1, k + 1),
                        node_id(i, j + 1, k + 1),
                    ]
                )
    boundaries = _axis_boundaries(coords)
    return BenchmarkMesh(
        element_type="hex8",
        coordinates=coords,
        connectivity=np.asarray(conn, dtype=np.int64),
        boundary_nodes=boundaries,
        face_tags=dict(boundaries),
    )


def _upgrade_hex8_to_hex20(mesh: BenchmarkMesh) -> BenchmarkMesh:
    coords: list[NDArray[np.float64]] = [row.copy() for row in mesh.coordinates]
    midpoint_nodes: dict[tuple[int, int], int] = {}

    def midpoint(a: int, b: int) -> int:
        ai = int(a)
        bi = int(b)
        key = (min(ai, bi), max(ai, bi))
        if key not in midpoint_nodes:
            midpoint_nodes[key] = len(coords)
            coords.append(0.5 * (mesh.coordinates[key[0]] + mesh.coordinates[key[1]]))
        return midpoint_nodes[key]

    conn20: list[list[int]] = []
    for hex_conn in mesh.connectivity:
        row = [int(n) for n in hex_conn]
        row.extend(midpoint(hex_conn[a], hex_conn[b]) for a, b in _HEX20_EDGE_ORDER)
        conn20.append(row)

    coords_arr = np.asarray(coords, dtype=np.float64)
    boundaries = _axis_boundaries(coords_arr)
    return BenchmarkMesh(
        element_type="hex20",
        coordinates=coords_arr,
        connectivity=np.asarray(conn20, dtype=np.int64),
        boundary_nodes=boundaries,
        face_tags=dict(boundaries),
    )


def _split_hex8_to_tet10(mesh: BenchmarkMesh) -> BenchmarkMesh:
    coords: list[NDArray[np.float64]] = [row.copy() for row in mesh.coordinates]
    midpoint_nodes: dict[tuple[int, int], int] = {}

    def midpoint(a: int, b: int) -> int:
        ai = int(a)
        bi = int(b)
        key = (min(ai, bi), max(ai, bi))
        if key not in midpoint_nodes:
            midpoint_nodes[key] = len(coords)
            coords.append(0.5 * (mesh.coordinates[key[0]] + mesh.coordinates[key[1]]))
        return midpoint_nodes[key]

    conn10: list[list[int]] = []
    for hex_conn in mesh.connectivity:
        for tet in _HEX8_TO_TETS:
            corners = [int(hex_conn[idx]) for idx in tet]
            corners = _orient_tet_corners(mesh.coordinates, corners)
            row = list(corners)
            row.extend(midpoint(corners[a], corners[b]) for a, b in _TET10_EDGE_ORDER)
            conn10.append(row)

    coords_arr = np.asarray(coords, dtype=np.float64)
    boundaries = _axis_boundaries(coords_arr)
    return BenchmarkMesh(
        element_type="tet10",
        coordinates=coords_arr,
        connectivity=np.asarray(conn10, dtype=np.int64),
        boundary_nodes=boundaries,
        face_tags=dict(boundaries),
    )


def _orient_tet_corners(coords: NDArray[np.float64], corners: list[int]) -> list[int]:
    X = coords[corners]
    det = float(np.linalg.det(np.column_stack((X[1] - X[0], X[2] - X[0], X[3] - X[0]))))
    if det < 0.0:
        corners[1], corners[2] = corners[2], corners[1]
    return corners


def _axis_boundaries(coords: NDArray[np.float64]) -> dict[str, NDArray[np.int64]]:
    tol = 1e-12
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    return {
        "x_min": np.flatnonzero(np.isclose(coords[:, 0], mins[0], atol=tol)).astype(np.int64),
        "x_max": np.flatnonzero(np.isclose(coords[:, 0], maxs[0], atol=tol)).astype(np.int64),
        "y_min": np.flatnonzero(np.isclose(coords[:, 1], mins[1], atol=tol)).astype(np.int64),
        "y_max": np.flatnonzero(np.isclose(coords[:, 1], maxs[1], atol=tol)).astype(np.int64),
        "z_min": np.flatnonzero(np.isclose(coords[:, 2], mins[2], atol=tol)).astype(np.int64),
        "z_max": np.flatnonzero(np.isclose(coords[:, 2], maxs[2], atol=tol)).astype(np.int64),
    }
