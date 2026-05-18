"""Fiber-reinforced strip benchmark (TL x HGO x Hex8) — Task P10-9.

A unit (or small) rectangular Hex8 strip is loaded uniaxially either along the
fiber direction (longitudinal) or perpendicular to it (transverse).  The
resulting first Piola-Kirchhoff stress in the loading direction is compared
against a closed-form analytical curve derived from the same HGO strain
energy, enforcing zero lateral traction via a nonlinear 1D solve on the two
lateral stretches.

Reference
---------
Holzapfel, Gasser & Ogden (2000) "A new constitutive framework for arterial
wall mechanics and a comparative study of material models", J. Elasticity
61(1-3): 1-48.  The GOH (Gasser-Ogden-Holzapfel 2006) dispersion extension is
what the MechDSL ``HGOMaterial`` implements; at dispersion kappa_disp = 0 it
collapses to the original 2000 model.

Reference approach
------------------
*Closed-form* analytical reference.  For a homogeneous deformation F under
uniaxial stretch, the HGO PK2 stress is a closed-form function of F; the two
unknown lateral stretches are obtained by a 2x2 Newton solve enforcing
S_22 = S_33 = 0 (or S_11 = S_33 = 0 for transverse loading along y).  This
gives a self-consistent reference that depends only on the material model,
not on the FEM discretisation — so the 5% envelope in the acceptance criteria
measures FEM discretisation accuracy.

Notes
-----
- Only one fiber family is active in the strip benchmark; the second family
  is set equal to the first (the HGO kernel rejects zero-length vectors).
- ``HGOMaterial.kappa`` is the bulk modulus of the volumetric penalty; we
  pick kappa >> mu for near-incompressibility (arterial-wall-like response).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.symbolic.models.hgo import HGOMaterial, pk2_stress
from mechdsl.verify.benchmarks._core import BenchmarkResult

if TYPE_CHECKING:
    from numpy.typing import NDArray

_I3 = np.eye(3, dtype=np.float64)

# Callable signature for the HGO ref solver (matches ref_hex8_hgo.solve_hgo).
_SolveHgoFn = Callable[..., tuple["NDArray", list[float]]]

# Callable signature for the internal-force assembler used to recover reactions.
_AssembleFn = Callable[..., "NDArray"]


# ---------------------------------------------------------------------------
# Strip mesh
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StripMesh:
    """Rectangular Hex8 strip mesh on [0, Lx] x [0, Ly] x [0, Lz]."""

    coords: NDArray  # (n_nodes, 3)
    connectivity: NDArray  # (n_elem, 8)
    n_nodes: int
    n_elem: int
    Lx: float
    Ly: float
    Lz: float
    # Face-node index sets
    x0_nodes: NDArray
    x1_nodes: NDArray
    y0_nodes: NDArray
    z0_nodes: NDArray


def generate_strip_mesh(Lx: float, Ly: float, Lz: float, nx: int, ny: int, nz: int) -> StripMesh:
    """Generate a structured rectangular Hex8 mesh.

    Node ordering: k (z) slowest, j (y) middle, i (x) fastest:
        node_id(i, j, k) = k * (ny+1) * (nx+1) + j * (nx+1) + i.
    """
    if Lx <= 0 or Ly <= 0 or Lz <= 0:
        raise ValueError(f"Dimensions must be > 0, got {Lx}, {Ly}, {Lz}")
    if nx < 1 or ny < 1 or nz < 1:
        raise ValueError(f"Element counts must be >= 1, got {nx}, {ny}, {nz}")

    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * Lx / nx
                coords[idx, 1] = j * Ly / ny
                coords[idx, 2] = k * Lz / nz
                idx += 1

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    eidx = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                conn[eidx] = [
                    node_id(i, j, k),
                    node_id(i + 1, j, k),
                    node_id(i + 1, j + 1, k),
                    node_id(i, j + 1, k),
                    node_id(i, j, k + 1),
                    node_id(i + 1, j, k + 1),
                    node_id(i + 1, j + 1, k + 1),
                    node_id(i, j + 1, k + 1),
                ]
                eidx += 1

    tol = 1e-10
    x0_nodes = np.where(np.abs(coords[:, 0]) < tol)[0].astype(np.int64)
    x1_nodes = np.where(np.abs(coords[:, 0] - Lx) < tol)[0].astype(np.int64)
    y0_nodes = np.where(np.abs(coords[:, 1]) < tol)[0].astype(np.int64)
    z0_nodes = np.where(np.abs(coords[:, 2]) < tol)[0].astype(np.int64)

    return StripMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        Lx=Lx,
        Ly=Ly,
        Lz=Lz,
        x0_nodes=x0_nodes,
        x1_nodes=x1_nodes,
        y0_nodes=y0_nodes,
        z0_nodes=z0_nodes,
    )


def fiber_direction_field(mesh: StripMesh, direction_vec: NDArray) -> list[tuple[NDArray, NDArray]]:
    """Per-element fiber direction pairs (uniform field).

    Both families point along ``direction_vec`` — this is what the strip
    benchmark needs since only one family is active.  The HGO kernel rejects
    zero-length vectors, so duplicating the direction is the cleanest
    single-family specialisation.
    """
    v = np.asarray(direction_vec, dtype=np.float64)
    n = float(np.linalg.norm(v))
    if n <= 0.0:
        raise ValueError("direction_vec must be non-zero")
    a = v / n
    return [(a.copy(), a.copy()) for _ in range(mesh.n_elem)]


# ---------------------------------------------------------------------------
# Closed-form analytical reference — HGO uniaxial stress
# ---------------------------------------------------------------------------


def _F_uniaxial(lam_L: float, lam_T1: float, lam_T2: float, load_axis: int) -> NDArray:
    """Diagonal F for homogeneous uniaxial loading.

    ``load_axis`` picks which diagonal entry is the prescribed stretch
    ``lam_L``; the other two diagonals carry the lateral stretches.
    """
    F = np.eye(3, dtype=np.float64)
    stretches = [lam_T1, lam_T2]
    for ax in range(3):
        if ax == load_axis:
            F[ax, ax] = lam_L
        else:
            F[ax, ax] = stretches.pop(0)
    return F


def _pk2_of_F(material: HGOMaterial, F: NDArray, fiber_dir: NDArray) -> NDArray:
    E = 0.5 * (F.T @ F - _I3)
    a = np.asarray(fiber_dir, dtype=np.float64)
    return pk2_stress(material, E, (a, a))


def hgo_analytical_uniaxial_stress(
    stretch_lambda: float,
    fiber_dir: NDArray,
    material: HGOMaterial,
    *,
    load_axis: int = 0,
    lateral_tol: float = 1e-10,
    max_iter: int = 60,
) -> tuple[float, float, tuple[float, float]]:
    """Closed-form uniaxial HGO stress at prescribed stretch.

    Solves for the two lateral stretches ``(lam_T1, lam_T2)`` such that the
    PK2 stress components transverse to the loading axis vanish.  Uses a
    damped Newton iteration with a finite-difference 2x2 Jacobian of the
    residual ``(S_t1, S_t2)`` w.r.t. ``(lam_T1, lam_T2)``.

    Parameters
    ----------
    stretch_lambda : float
        Axial stretch applied along ``load_axis``.
    fiber_dir : (3,) unit vector
        Fiber direction in the reference configuration.
    material : HGOMaterial
    load_axis : int, one of {0, 1, 2}
        Axis along which ``stretch_lambda`` is prescribed.

    Returns
    -------
    P_axial : float
        First Piola-Kirchhoff stress component in the loading direction,
        P[load_axis, load_axis] = F @ S diagonal entry.
    S_axial : float
        Second Piola-Kirchhoff axial stress component.
    lateral_stretches : (lam_T1, lam_T2)
        Converged lateral stretches; transverse PK2 stress is zero.
    """
    if load_axis not in (0, 1, 2):
        raise ValueError(f"load_axis must be 0/1/2, got {load_axis}")
    if stretch_lambda <= 0.0:
        raise ValueError(f"stretch_lambda must be > 0, got {stretch_lambda}")

    transverse_axes = [ax for ax in range(3) if ax != load_axis]

    # Initial guess: incompressible lateral stretch lam_T = 1 / sqrt(lambda).
    lam_t = np.array(
        [1.0 / np.sqrt(stretch_lambda), 1.0 / np.sqrt(stretch_lambda)], dtype=np.float64
    )

    def residual(lam_t_vec: NDArray) -> NDArray:
        F = _F_uniaxial(stretch_lambda, float(lam_t_vec[0]), float(lam_t_vec[1]), load_axis)
        S = _pk2_of_F(material, F, fiber_dir)
        t1, t2 = transverse_axes
        return np.array([S[t1, t1], S[t2, t2]], dtype=np.float64)

    eps = 1e-7
    for _ in range(max_iter):
        r = residual(lam_t)
        if float(np.linalg.norm(r)) < lateral_tol:
            break

        # 2x2 central-difference Jacobian
        J = np.zeros((2, 2), dtype=np.float64)
        for k in range(2):
            d = np.zeros(2)
            d[k] = eps
            J[:, k] = (residual(lam_t + d) - residual(lam_t - d)) / (2.0 * eps)

        # Damped Newton step
        try:
            dlam = np.linalg.solve(J, -r)
        except np.linalg.LinAlgError as err:
            raise RuntimeError(f"Analytical uniaxial solve: singular Jacobian ({err})") from err

        # Line search: backtrack if residual grows or lateral stretch goes non-positive
        alpha = 1.0
        for _ls in range(20):
            trial = lam_t + alpha * dlam
            if trial[0] > 1e-6 and trial[1] > 1e-6:
                r_trial = residual(trial)
                if float(np.linalg.norm(r_trial)) <= float(np.linalg.norm(r)):
                    break
            alpha *= 0.5
        lam_t = lam_t + alpha * dlam
    else:
        raise RuntimeError(
            f"Analytical uniaxial solve did not converge for lambda={stretch_lambda:.4f}, "
            f"|r|={float(np.linalg.norm(residual(lam_t))):.3e}"
        )

    F = _F_uniaxial(stretch_lambda, float(lam_t[0]), float(lam_t[1]), load_axis)
    S = _pk2_of_F(material, F, fiber_dir)
    P = F @ S
    return (
        float(P[load_axis, load_axis]),
        float(S[load_axis, load_axis]),
        (
            float(lam_t[0]),
            float(lam_t[1]),
        ),
    )


# ---------------------------------------------------------------------------
# FEM benchmark orchestrator
# ---------------------------------------------------------------------------


def run_hgo_uniaxial(
    *,
    stretch_lambda: float,
    fiber_dir: NDArray,
    material: HGOMaterial,
    solve_hgo: _SolveHgoFn,
    assemble_internal_force: _AssembleFn,
    Lx: float = 1.0,
    Ly: float = 1.0,
    Lz: float = 1.0,
    nx: int = 1,
    ny: int = 1,
    nz: int = 1,
    load_axis: int = 0,
    n_load_steps: int = 4,
    tol: float = 1e-8,
    max_iter: int = 40,
) -> BenchmarkResult:
    """Run a uniaxial HGO strip benchmark and return stress / stretch data.

    Boundary conditions (load_axis = 0):
      - x0 face: u_x = 0
      - x1 face: u_x = (stretch_lambda - 1) * Lx   (displacement control)
      - y0 face: u_y = 0  (roller: lateral free in y)
      - z0 face: u_z = 0  (roller: lateral free in z)

    Analogous rollers for ``load_axis == 1`` or ``2`` (cycled axes).

    The FEM PK1 axial stress is recovered from the reaction force on the
    loaded face, divided by the reference face area.

    Parameters
    ----------
    solve_hgo : callable
        HGO TL Newton solver, injected by the caller
        (``tests.ref.ref_hex8_hgo.solve_hgo``).

    Returns
    -------
    BenchmarkResult
        ``extras`` contains:
        - ``"stretch"``           : prescribed axial stretch
        - ``"P_axial_fem"``       : FEM axial PK1 stress (reaction / area)
        - ``"P_axial_analytical"``: closed-form HGO axial PK1 stress
        - ``"rel_err"``           : |FEM - analytical| / |analytical|
        - ``"lateral_stretches"`` : (lam_T1, lam_T2) from the analytical solve
        - ``"fiber_dir"``         : fiber unit vector
        - ``"load_axis"``         : axis index (0, 1, 2)
    """
    if load_axis not in (0, 1, 2):
        raise ValueError(f"load_axis must be 0/1/2, got {load_axis}")

    mesh = generate_strip_mesh(Lx, Ly, Lz, nx, ny, nz)
    fibers = fiber_direction_field(mesh, fiber_dir)

    # Build Dirichlet BCs for the chosen load_axis.
    bc_mask = np.zeros((mesh.n_nodes, 3), dtype=bool)
    bc_values = np.zeros((mesh.n_nodes, 3), dtype=np.float64)

    L_axis = [Lx, Ly, Lz][load_axis]
    u_applied = (stretch_lambda - 1.0) * L_axis

    # Loaded-axis BCs.
    if load_axis == 0:
        bc_mask[mesh.x0_nodes, 0] = True
        bc_mask[mesh.x1_nodes, 0] = True
        bc_values[mesh.x1_nodes, 0] = u_applied
        # Lateral rollers: one node per face.
        bc_mask[mesh.y0_nodes, 1] = True
        bc_mask[mesh.z0_nodes, 2] = True
        loaded_face_nodes = mesh.x1_nodes
    elif load_axis == 1:
        bc_mask[mesh.y0_nodes, 1] = True
        y1_nodes = np.where(np.abs(mesh.coords[:, 1] - Ly) < 1e-10)[0].astype(np.int64)
        bc_mask[y1_nodes, 1] = True
        bc_values[y1_nodes, 1] = u_applied
        bc_mask[mesh.x0_nodes, 0] = True
        bc_mask[mesh.z0_nodes, 2] = True
        loaded_face_nodes = y1_nodes
    else:
        bc_mask[mesh.z0_nodes, 2] = True
        z1_nodes = np.where(np.abs(mesh.coords[:, 2] - Lz) < 1e-10)[0].astype(np.int64)
        bc_mask[z1_nodes, 2] = True
        bc_values[z1_nodes, 2] = u_applied
        bc_mask[mesh.x0_nodes, 0] = True
        bc_mask[mesh.y0_nodes, 1] = True
        loaded_face_nodes = z1_nodes

    f_ext = np.zeros((mesh.n_nodes, 3), dtype=np.float64)

    t0 = time.perf_counter()
    u, residuals = solve_hgo(
        mesh.coords,
        mesh.connectivity,
        material,
        fibers,
        bc_mask,
        bc_values,
        f_ext,
        n_steps=n_load_steps,
        tol=tol,
        max_iter=max_iter,
    )
    wallclock_s = time.perf_counter() - t0

    # ------------------------------------------------------------------
    # Recover FEM axial PK1 stress from the reaction on the loaded face.
    #
    # R = f_int(u) = integral_Omega0 (dN/dX) . P^T dV.  Summing the axial
    # component of f_int over the loaded face yields the total traction in
    # the reference configuration; dividing by the reference face area
    # gives P_axial.  The assembler is injected by the caller to avoid a
    # ``src -> tests`` import.
    # ------------------------------------------------------------------
    f_int = assemble_internal_force(u, mesh.coords, mesh.connectivity, material, fibers)
    reaction_axial = float(np.sum(f_int[loaded_face_nodes, load_axis]))

    if load_axis == 0:
        ref_area = Ly * Lz
    elif load_axis == 1:
        ref_area = Lx * Lz
    else:
        ref_area = Lx * Ly

    P_axial_fem = reaction_axial / ref_area

    # Closed-form analytical reference
    P_axial_ana, S_axial_ana, lateral = hgo_analytical_uniaxial_stress(
        stretch_lambda, fiber_dir, material, load_axis=load_axis
    )

    rel_err = abs(P_axial_fem - P_axial_ana) / abs(P_axial_ana) if abs(P_axial_ana) > 0 else 0.0

    extras: dict = {
        "stretch": stretch_lambda,
        "P_axial_fem": P_axial_fem,
        "P_axial_analytical": P_axial_ana,
        "S_axial_analytical": S_axial_ana,
        "rel_err": rel_err,
        "lateral_stretches": lateral,
        "fiber_dir": np.asarray(fiber_dir, dtype=np.float64),
        "load_axis": load_axis,
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=len(residuals),
        wallclock_s=wallclock_s,
        extras=extras,
    )
