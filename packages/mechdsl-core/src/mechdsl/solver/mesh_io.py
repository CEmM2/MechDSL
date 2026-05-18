"""Structured Hex8 mesh generation and I/O (P7.3).

Generates structured hexahedral meshes on rectangular domains with
boundary face tags for BC application.  Node ordering within each
element follows the standard Hex8 convention matching ``hex8_tables``:
bottom face (-z) CCW then top face (+z) CCW.

All coordinates use float64.  Connectivity uses int64.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.ir.mechanics_ir import BoundaryRegionError, MeshContract

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True)
class HexMesh:
    """Structured Hex8 mesh.

    Attributes
    ----------
    coords : NDArray, shape (n_nodes, 3)
        Nodal coordinates in the reference configuration.
    connectivity : NDArray, shape (n_elem, 8)
        Element connectivity (0-based node indices).
    n_nodes : int
        Total number of nodes.
    n_elem : int
        Total number of elements.
    boundary_tags : dict[str, NDArray]
        Mapping from boundary name to an array of node indices on that face.
    """

    coords: NDArray  # (n_nodes, 3)
    connectivity: NDArray  # (n_elem, 8)
    n_nodes: int
    n_elem: int
    boundary_tags: dict[str, NDArray]  # name -> node indices array

    def __post_init__(self) -> None:
        if self.coords.ndim != 2 or self.coords.shape[1] != 3:
            raise ValueError(f"coords must be (n, 3), got {self.coords.shape}")
        if self.connectivity.ndim != 2 or self.connectivity.shape[1] != 8:
            raise ValueError(f"connectivity must be (n, 8), got {self.connectivity.shape}")
        if self.n_nodes != self.coords.shape[0]:
            raise ValueError(
                f"n_nodes ({self.n_nodes}) != coords.shape[0] ({self.coords.shape[0]})"
            )
        if self.n_elem != self.connectivity.shape[0]:
            raise ValueError(
                f"n_elem ({self.n_elem}) != connectivity.shape[0] ({self.connectivity.shape[0]})"
            )

    @property
    def n_dof(self) -> int:
        """Total number of degrees of freedom (3 per node)."""
        return self.n_nodes * 3


def generate_hex8_mesh(
    nx: int,
    ny: int,
    nz: int,
    Lx: float = 1.0,
    Ly: float = 1.0,
    Lz: float = 1.0,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> HexMesh:
    """Generate structured Hex8 mesh on rectangular domain.

    Creates a mesh on [origin[0], origin[0]+Lx] x [origin[1], origin[1]+Ly]
    x [origin[2], origin[2]+Lz] with nx * ny * nz elements.

    Node ordering: k (z) varies slowest, j (y) next, i (x) fastest.
    Element local node ordering follows Hex8 convention (bottom face CCW
    then top face CCW when viewed from -z).

    Parameters
    ----------
    nx, ny, nz : int
        Number of elements in each direction.
    Lx, Ly, Lz : float
        Domain lengths in each direction.
    origin : tuple[float, float, float]
        Domain origin.

    Returns
    -------
    HexMesh
        The generated mesh with boundary tags for all 6 faces.

    Boundary tags generated
    -----------------------
    - ``"x0"``: face at x = origin[0] (left)
    - ``"x1"``: face at x = origin[0] + Lx (right)
    - ``"y0"``: face at y = origin[1] (bottom)
    - ``"y1"``: face at y = origin[1] + Ly (top)
    - ``"z0"``: face at z = origin[2] (back)
    - ``"z1"``: face at z = origin[2] + Lz (front)
    """
    ox, oy, oz = origin
    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = ox + i * Lx / nx
                coords[idx, 1] = oy + j * Ly / ny
                coords[idx, 2] = oz + k * Lz / nz
                idx += 1

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                # Bottom face (k), CCW when viewed from -z
                n0 = node_id(i, j, k)
                n1 = node_id(i + 1, j, k)
                n2 = node_id(i + 1, j + 1, k)
                n3 = node_id(i, j + 1, k)
                # Top face (k+1), CCW when viewed from -z
                n4 = node_id(i, j, k + 1)
                n5 = node_id(i + 1, j, k + 1)
                n6 = node_id(i + 1, j + 1, k + 1)
                n7 = node_id(i, j + 1, k + 1)
                conn[eidx] = [n0, n1, n2, n3, n4, n5, n6, n7]
                eidx += 1

    # Build boundary tags — collect node indices for each face
    tol = 1e-12
    x0_min, x1_max = ox, ox + Lx
    y0_min, y1_max = oy, oy + Ly
    z0_min, z1_max = oz, oz + Lz

    boundary_tags: dict[str, NDArray] = {
        "x0": np.where(np.abs(coords[:, 0] - x0_min) < tol)[0].astype(np.int64),
        "x1": np.where(np.abs(coords[:, 0] - x1_max) < tol)[0].astype(np.int64),
        "y0": np.where(np.abs(coords[:, 1] - y0_min) < tol)[0].astype(np.int64),
        "y1": np.where(np.abs(coords[:, 1] - y1_max) < tol)[0].astype(np.int64),
        "z0": np.where(np.abs(coords[:, 2] - z0_min) < tol)[0].astype(np.int64),
        "z1": np.where(np.abs(coords[:, 2] - z1_max) < tol)[0].astype(np.int64),
    }

    return HexMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        boundary_tags=boundary_tags,
    )


def generate_cook_membrane_mesh(nx: int, ny: int, nz: int) -> HexMesh:
    """Generate structured Hex8 mesh for Cook's membrane benchmark geometry.

    Cook's membrane is a trapezoidal domain:
    - x in [0, 48] mm
    - Left face (x=0): height 44 mm
    - Right face (x=48): height 16 mm
    - Thickness z in [0, 1] mm

    The mesh is constructed by warping a rectangular mesh on
    [0, 48] x [0, 44] x [0, 1] using:
        y_warped = y * (44 - 28 * x / 48) / 44

    This maps:
    - Bottom edge (y=0) stays at y=0.
    - (0, 44)  -> (0, 44)   [left top corner unchanged]
    - (48, 44) -> (48, 16)  [right top corner warped down]

    Boundary tags are detected on the pre-warp rectangular mesh so
    that the ``y1`` face (top edge) is identified correctly.

    Parameters
    ----------
    nx, ny, nz : int
        Number of elements in x, y, z directions respectively.

    Returns
    -------
    HexMesh
        Mesh with trapezoidal Cook's geometry and boundary tags:
        - ``"x0"``: nodes at x=0 (fixed / Dirichlet face)
        - ``"x1"``: nodes at x=48 (loaded / Neumann face)
        - ``"y0"``: nodes on bottom edge (y_warped=0)
        - ``"y1"``: nodes on top edge (y=Ly before warping)
        - ``"z0"``: nodes at z=0 (back face)
        - ``"z1"``: nodes at z=1 (front face)
    """
    Lx: float = 48.0
    Ly: float = 44.0
    Lz: float = 1.0

    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    # Build rectangular mesh first, then warp y
    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * Lx / nx
                coords[idx, 1] = j * Ly / ny
                coords[idx, 2] = k * Lz / nz
                idx += 1

    # Detect boundary tags on the pre-warp rectangular mesh
    tol = 1e-12
    boundary_tags: dict[str, NDArray] = {
        "x0": np.where(np.abs(coords[:, 0] - 0.0) < tol)[0].astype(np.int64),
        "x1": np.where(np.abs(coords[:, 0] - Lx) < tol)[0].astype(np.int64),
        "y0": np.where(np.abs(coords[:, 1] - 0.0) < tol)[0].astype(np.int64),
        "y1": np.where(np.abs(coords[:, 1] - Ly) < tol)[0].astype(np.int64),
        "z0": np.where(np.abs(coords[:, 2] - 0.0) < tol)[0].astype(np.int64),
        "z1": np.where(np.abs(coords[:, 2] - Lz) < tol)[0].astype(np.int64),
    }

    # Warp y-coordinates: y_warped = y * (44 - 28*x/48) / 44
    x = coords[:, 0]
    y = coords[:, 1]
    coords[:, 1] = y * (44.0 - 28.0 * x / 48.0) / 44.0

    # Build connectivity (same ordering as generate_hex8_mesh)
    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                n0 = node_id(i, j, k)
                n1 = node_id(i + 1, j, k)
                n2 = node_id(i + 1, j + 1, k)
                n3 = node_id(i, j + 1, k)
                n4 = node_id(i, j, k + 1)
                n5 = node_id(i + 1, j, k + 1)
                n6 = node_id(i + 1, j + 1, k + 1)
                n7 = node_id(i, j + 1, k + 1)
                conn[eidx] = [n0, n1, n2, n3, n4, n5, n6, n7]
                eidx += 1

    return HexMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        boundary_tags=boundary_tags,
    )


def generate_necking_bar_mesh(
    nx: int,
    ny: int,
    nz: int,
    L: float = 20.0,
    W: float = 2.0,
    imperfection: float = 0.005,
) -> HexMesh:
    """Generate structured Hex8 quarter-model mesh for necking bar benchmark.

    The full bar has length L along the z-axis and square cross-section W x W.
    A quarter-model symmetry reduces the domain to:
        x in [0, W/2],  y in [0, W/2],  z in [0, L/2]

    A smooth geometric imperfection tapers the cross-section near z = L/2
    (the bar midplane in the full model).  The taper is a cosine bell that
    peaks at z = L/2 and vanishes at z = 0:

        f(z) = 0.5 * (1 - cos(pi * z / (L/2)))

    The x and y coordinates of each node are scaled by:

        scale(z) = 1 - imperfection * f(z)

    so that at z = L/2 the cross-section is reduced by ``imperfection * W/2``
    on each axis (i.e. ``imperfection * W`` in the full cross-section width).

    Boundary tags are detected on the **pre-warp** rectangular mesh so that
    all four symmetry/loading faces are identified correctly.

    Parameters
    ----------
    nx, ny, nz : int
        Number of elements in x, y, z directions (z is the bar axis).
    L : float
        Full bar length.  Quarter-model spans [0, L/2] in z.
    W : float
        Full bar width/height (square cross-section W x W).
        Quarter-model spans [0, W/2] in x and y.
    imperfection : float
        Fractional cross-section reduction at midplane
        (e.g. 0.005 → 0.5 % reduction per half-width).

    Returns
    -------
    HexMesh
        Mesh with boundary tags:
        - ``"x0"``: x = 0 symmetry face (u_x = 0)
        - ``"y0"``: y = 0 symmetry face (u_y = 0)
        - ``"z0"``: z = 0 symmetry face (u_z = 0)
        - ``"z1"``: z = L/2 face (prescribed displacement)
    """
    half_L = L / 2.0
    half_W = W / 2.0

    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    # Build rectangular mesh on [0, W/2] x [0, W/2] x [0, L/2]
    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * half_W / nx
                coords[idx, 1] = j * half_W / ny
                coords[idx, 2] = k * half_L / nz
                idx += 1

    # Detect boundary tags on the pre-warp rectangular mesh
    tol = 1e-12
    boundary_tags: dict[str, NDArray] = {
        "x0": np.where(np.abs(coords[:, 0] - 0.0) < tol)[0].astype(np.int64),
        "y0": np.where(np.abs(coords[:, 1] - 0.0) < tol)[0].astype(np.int64),
        "z0": np.where(np.abs(coords[:, 2] - 0.0) < tol)[0].astype(np.int64),
        "z1": np.where(np.abs(coords[:, 2] - half_L) < tol)[0].astype(np.int64),
    }

    # Apply smooth cosine-bell imperfection taper to x and y coordinates.
    # f(z) = 0.5 * (1 - cos(pi * z / half_L))  → 0 at z=0, 1 at z=half_L
    z = coords[:, 2]
    f = 0.5 * (1.0 - np.cos(np.pi * z / half_L))
    scale = 1.0 - imperfection * f
    coords[:, 0] *= scale
    coords[:, 1] *= scale

    # Build connectivity (same ordering as generate_hex8_mesh)
    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                # Bottom face (k), CCW when viewed from -z
                n0 = node_id(i, j, k)
                n1 = node_id(i + 1, j, k)
                n2 = node_id(i + 1, j + 1, k)
                n3 = node_id(i, j + 1, k)
                # Top face (k+1), CCW when viewed from -z
                n4 = node_id(i, j, k + 1)
                n5 = node_id(i + 1, j, k + 1)
                n6 = node_id(i + 1, j + 1, k + 1)
                n7 = node_id(i, j + 1, k + 1)
                conn[eidx] = [n0, n1, n2, n3, n4, n5, n6, n7]
                eidx += 1

    return HexMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        boundary_tags=boundary_tags,
    )


def get_face_nodes(mesh: HexMesh, face_name: str) -> NDArray:
    """Get node indices for a named boundary face.

    Parameters
    ----------
    mesh : HexMesh
        The mesh to query.
    face_name : str
        Boundary face name (one of "x0", "x1", "y0", "y1", "z0", "z1").

    Returns
    -------
    NDArray
        Array of node indices on the requested face.

    Raises
    ------
    KeyError
        If ``face_name`` is not a known boundary tag.
    """
    return mesh.boundary_tags[face_name]


def validate_mesh_against_contract(mesh: HexMesh, contract: MeshContract) -> None:
    """Reject a mesh that does not carry every region the IR contract requires.

    Pre-P3-3 the "BC name == mesh boundary tag" assumption was scattered:
    each consumer (assemblers, codegen runtime, BC compilers in
    :mod:`mechdsl.codegen.boundary_codegen`) re-derived it from
    ``mesh.boundary_tags[bc.name]`` lookups that surfaced as ``KeyError``
    deep inside the runtime. This helper centralizes the check on the
    boundary between IR and mesh — call it once with
    :meth:`ProblemIR.derived_mesh_contract` and the failure points at the
    IR/mesh interface instead of the codegen layer.

    Parameters
    ----------
    mesh : HexMesh
        The runtime mesh whose ``boundary_tags`` populates the named
        regions the IR will reference.
    contract : MeshContract
        The IR's expected region-tag set. Use
        :meth:`ProblemIR.derived_mesh_contract` if you do not have an
        explicit contract.

    Raises
    ------
    BoundaryRegionError
        If any tag in ``contract.region_tags`` is missing from
        ``mesh.boundary_tags``. The message lists the missing tags and
        the tags the mesh actually carries so the user can see the
        mismatch at a glance.
    """
    missing = [tag for tag in contract.region_tags if tag not in mesh.boundary_tags]
    if missing:
        raise BoundaryRegionError(
            f"Mesh is missing required boundary tags {missing}. "
            f"Mesh boundary_tags has {sorted(mesh.boundary_tags)}; "
            f"IR contract requires {list(contract.region_tags)}. "
            "Either tag the mesh's missing regions or extend "
            "ProblemIR.boundaries / mesh_contract.region_tags to match the mesh."
        )
