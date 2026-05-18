"""Generate mesh.npz input files for all dev/examples.

Run once to produce the mesh files consumed by the generated Taichi solvers:

    uv run python dev/examples/gen_meshes.py

Outputs (in dev/examples/):
    mesh_cantilever.npz  -- elastic cantilever (SVK)
    mesh_cook.npz        -- Cook's membrane (J2)
    mesh_necking.npz     -- necking bar 1/8 model (J2)
    mesh_patch.npz       -- patch test (SVK)
    mesh_uniaxial.npz    -- uniaxial tension (J2)

Each file contains:
    coords    float64 (n_nodes, 3)  -- reference nodal coordinates
    conn      int64   (n_elem, 8)   -- Hex8 connectivity (0-based)
    f_ext     float64 (n_nodes, 3)  -- external nodal forces
    bc_dofs   int64   (n_bc,)       -- constrained flat DOF indices (node*3 + c)
    bc_values float64 (n_bc,)       -- prescribed values at bc_dofs
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hex8_mesh(
    nx: int, ny: int, nz: int, Lx: float, Ly: float, Lz: float
) -> tuple[np.ndarray, np.ndarray]:
    """Structured Hex8 mesh on [0,Lx]×[0,Ly]×[0,Lz].

    Node ordering: bottom face (-z) CCW then top face (+z) CCW,
    matching the element_ir _HEX8_NODES convention.
    """
    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)
    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx] = [i * Lx / nx, j * Ly / ny, k * Lz / nz]
                idx += 1

    def nid(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)
    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                conn[eidx] = [
                    nid(i, j, k),
                    nid(i + 1, j, k),
                    nid(i + 1, j + 1, k),
                    nid(i, j + 1, k),
                    nid(i, j, k + 1),
                    nid(i + 1, j, k + 1),
                    nid(i + 1, j + 1, k + 1),
                    nid(i, j + 1, k + 1),
                ]
                eidx += 1

    return coords, conn


def bc_entries(
    node_ids: np.ndarray, components: list[int], values: list[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Return (dofs, vals) for a set of nodes and prescribed component values."""
    dofs, vals = [], []
    for n in node_ids:
        for c, v in zip(components, values):
            dofs.append(int(n) * 3 + c)
            vals.append(v)
    return np.array(dofs, dtype=np.int64), np.array(vals, dtype=np.float64)


def merge_bcs(
    *parts: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Merge multiple (dofs, vals) pairs, keeping first occurrence per DOF."""
    seen: dict[int, float] = {}
    for dofs, vals in parts:
        for d, v in zip(dofs.tolist(), vals.tolist()):
            if d not in seen:
                seen[d] = v
    sorted_items = sorted(seen.items())
    if not sorted_items:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64)
    d_arr, v_arr = zip(*sorted_items)
    return np.array(d_arr, dtype=np.int64), np.array(v_arr, dtype=np.float64)


def face_nodes(coords: np.ndarray, axis: int, at_max: bool, tol: float = 1e-10) -> np.ndarray:
    vals = coords[:, axis]
    ref = vals.max() if at_max else vals.min()
    return np.where(np.abs(vals - ref) < tol)[0]


def save(
    name: str,
    coords: np.ndarray,
    conn: np.ndarray,
    f_ext: np.ndarray,
    bc_dofs: np.ndarray,
    bc_values: np.ndarray,
) -> None:
    path = HERE / name
    np.savez(path, coords=coords, conn=conn, f_ext=f_ext, bc_dofs=bc_dofs, bc_values=bc_values)
    n_nodes, n_elem = len(coords), len(conn)
    print(f"  {name}: {n_elem} elem, {n_nodes} nodes, {len(bc_dofs)} bc DOFs")


# ---------------------------------------------------------------------------
# 1. Elastic cantilever  (SVK, elastic_cantilever.py)
#    Domain: [0,10]×[0,2]×[0,2],  4×2×2 Hex8
#    BCs: fix x0 (all), Neumann z-traction on x1
# ---------------------------------------------------------------------------
def gen_cantilever() -> None:
    nx, ny, nz = 4, 2, 2
    Lx, Ly, Lz = 10.0, 2.0, 2.0
    coords, conn = hex8_mesh(nx, ny, nz, Lx, Ly, Lz)

    x0 = face_nodes(coords, 0, at_max=False)
    x1 = face_nodes(coords, 0, at_max=True)

    bc_dofs, bc_values = bc_entries(x0, [0, 1, 2], [0.0, 0.0, 0.0])

    f_ext = np.zeros((len(coords), 3), dtype=np.float64)
    f_ext[x1, 2] = -1000.0 / len(x1)  # total downward z-force = -1 kN

    save("mesh_cantilever.npz", coords, conn, f_ext, bc_dofs, bc_values)


# ---------------------------------------------------------------------------
# 2. Cook's membrane  (J2, cook_membrane.py)
#    Domain: 4×4×1 box [0,48]×[0,44]×[0,1] (rectangular approximation)
#    BCs: clamp x0 (all), Neumann y-shear on x1
# ---------------------------------------------------------------------------
def gen_cook() -> None:
    nx, ny, nz = 4, 4, 1
    Lx, Ly, Lz = 48.0, 44.0, 1.0
    coords, conn = hex8_mesh(nx, ny, nz, Lx, Ly, Lz)

    x0 = face_nodes(coords, 0, at_max=False)
    x1 = face_nodes(coords, 0, at_max=True)

    bc_dofs, bc_values = bc_entries(x0, [0, 1, 2], [0.0, 0.0, 0.0])

    f_ext = np.zeros((len(coords), 3), dtype=np.float64)
    f_ext[x1, 1] = 100.0 / len(x1)  # total y-shear = 100 N

    save("mesh_cook.npz", coords, conn, f_ext, bc_dofs, bc_values)


# ---------------------------------------------------------------------------
# 3. Necking bar  (J2, necking_bar.py)
#    Domain: 1/8 symmetry model [0,5]×[0,5]×[0,10],  2×2×4 Hex8
#    BCs: x_sym (u_x=0 on x0), y_sym (u_y=0 on y0), z_fix (u_z=0 on z0),
#         pull (u_z=1.0 on z1)
# ---------------------------------------------------------------------------
def gen_necking() -> None:
    nx, ny, nz = 2, 2, 4
    Lx, Ly, Lz = 5.0, 5.0, 10.0
    coords, conn = hex8_mesh(nx, ny, nz, Lx, Ly, Lz)

    x0 = face_nodes(coords, 0, at_max=False)
    y0 = face_nodes(coords, 1, at_max=False)
    z0 = face_nodes(coords, 2, at_max=False)
    z1 = face_nodes(coords, 2, at_max=True)

    bc_dofs, bc_values = merge_bcs(
        bc_entries(x0, [0], [0.0]),  # x-symmetry
        bc_entries(y0, [1], [0.0]),  # y-symmetry
        bc_entries(z0, [2], [0.0]),  # bottom fixed in z
        bc_entries(z1, [2], [1.0]),  # 1 mm axial pull
    )

    f_ext = np.zeros((len(coords), 3), dtype=np.float64)

    save("mesh_necking.npz", coords, conn, f_ext, bc_dofs, bc_values)


# ---------------------------------------------------------------------------
# 4. Patch test  (SVK, patch_test.py)
#    Domain: [0,1]³,  2×2×2 Hex8
#    BCs: anchor x0 (all), prescribed x-stretch on x1
# ---------------------------------------------------------------------------
def gen_patch() -> None:
    nx, ny, nz = 2, 2, 2
    Lx, Ly, Lz = 1.0, 1.0, 1.0
    coords, conn = hex8_mesh(nx, ny, nz, Lx, Ly, Lz)

    x0 = face_nodes(coords, 0, at_max=False)
    x1 = face_nodes(coords, 0, at_max=True)

    bc_dofs, bc_values = merge_bcs(
        bc_entries(x0, [0, 1, 2], [0.0, 0.0, 0.0]),  # anchor
        bc_entries(x1, [0], [0.01]),  # 1% stretch
    )

    f_ext = np.zeros((len(coords), 3), dtype=np.float64)

    save("mesh_patch.npz", coords, conn, f_ext, bc_dofs, bc_values)


# ---------------------------------------------------------------------------
# 5. Plastic uniaxial  (J2, plastic_uniaxial.py)
#    Domain: [0,10]×[0,2]×[0,2],  4×2×2 Hex8
#    BCs: fix x0 (all), prescribed x-displacement on x1
# ---------------------------------------------------------------------------
def gen_uniaxial() -> None:
    nx, ny, nz = 4, 2, 2
    Lx, Ly, Lz = 10.0, 2.0, 2.0
    coords, conn = hex8_mesh(nx, ny, nz, Lx, Ly, Lz)

    x0 = face_nodes(coords, 0, at_max=False)
    x1 = face_nodes(coords, 0, at_max=True)

    bc_dofs, bc_values = merge_bcs(
        bc_entries(x0, [0, 1, 2], [0.0, 0.0, 0.0]),  # fully fixed
        bc_entries(x1, [0], [0.1]),  # 0.1 mm pull (1%)
    )

    f_ext = np.zeros((len(coords), 3), dtype=np.float64)

    save("mesh_uniaxial.npz", coords, conn, f_ext, bc_dofs, bc_values)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating mesh files in", HERE)
    gen_cantilever()
    gen_cook()
    gen_necking()
    gen_patch()
    gen_uniaxial()
    print("Done.")
