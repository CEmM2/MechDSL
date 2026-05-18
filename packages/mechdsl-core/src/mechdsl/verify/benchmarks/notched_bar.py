"""Notched bar benchmark (P10-8): TL x Lemaitre damage x Hex8.

Extends the Phase 6 P6-3 notched-bar unit test into a full benchmark:
  - Public mesh generator for a rectangular Hex8 bar with a semi-circular
    notch on the +y face.
  - Orchestrator that compiles a Lemaitre ProblemIR, applies displacement-
    controlled tension, and records the load-displacement history plus the
    final damage field.

Reference literature approach
-----------------------------
The canonical notched-bar damage benchmark in the literature is the one
introduced by Lemaitre (1985) and re-used in Lemaitre & Desmorat (2005,
Engineering Damage Mechanics, Fig 2.29) and de Souza Neto, Peric & Owen
(2008, Computational Methods for Plasticity, Ch 12).  None of those sources
ship a fully-digitised load-displacement curve that is easy to match
quantitatively WITHOUT the original mesh -- the reference surfaces are
always redrawn by hand.

Per the P10-8 task notes, when a literature reference is not directly
usable, we fall back to a **self-consistent** reference: we pick a fixed
mesh and parameter set (documented in ``_REFERENCE_*`` constants below),
execute the solve at a "reference" load-step resolution, record the
load-displacement samples, and then require subsequent runs at the same
mesh/parameter set to reproduce them within 10% (the tolerance called out
by the task JSON and by the Lemaitre & Desmorat textbook for damage
problems).  The 10% tolerance detects regressions against our own
baseline; it does NOT claim agreement with a specific published curve.

This choice is aligned with the task risk note: "Damage problems are
notoriously mesh-dependent.  Mitigation: pick a reference that documents
its mesh and use the same density."  Our self-consistent reference IS
that documented mesh.

Acceptance criteria (dev/tasks/PLAN-B/json/P10-8.json)
------------------------------------------------------
1. Load-displacement curve within 10% of reference.
2. Damage localisation at the notch root (same invariant as the
   Phase 6 unit test).
"""

from __future__ import annotations

import importlib.util
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.codegen import compile as mechdsl_compile
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.solver.import_adapter import CGSolver
from mechdsl.verify.benchmarks._core import BenchmarkResult

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NotchedBarMesh:
    """Structured Hex8 mesh for a rectangular bar with a semi-circular notch.

    Attributes
    ----------
    coords : (n_nodes, 3)
        Deformed reference coordinates (nodes under the notch footprint are
        pushed down in y to carve out the semi-circular notch).
    connectivity : (n_elem, 8)
        Hex8 element connectivity.
    notch_root_xyz : (3,)
        Coordinates of the geometric bottom of the notch (on the mid-plane).
    x_left_nodes, x_right_nodes : (M,)
        Node indices on x = 0 and x = L boundary faces respectively.
    L, H, T : float
        Nominal bar length, height, thickness (pre-notch).
    n_len, n_height, n_thick : int
        Element counts along each axis of the underlying structured block.
    """

    coords: NDArray
    connectivity: NDArray
    notch_root_xyz: NDArray
    x_left_nodes: NDArray
    x_right_nodes: NDArray
    L: float
    H: float
    T: float
    n_len: int
    n_height: int
    n_thick: int


def _build_hex8_block(
    nx: int,
    ny: int,
    nz: int,
    Lx: float,
    Ly: float,
    Lz: float,
) -> tuple[NDArray, NDArray]:
    """Structured Hex8 mesh on ``[0,Lx] x [0,Ly] x [0,Lz]``.

    Matches the convention used across the repo (k slowest, j mid, i
    fastest, CCW-bottom + CCW-top element ordering).  Kept private to this
    module to avoid importing from the test tree.
    """
    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)
    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * Lx / nx
                coords[idx, 1] = j * Ly / ny
                coords[idx, 2] = k * Lz / nz
                idx += 1

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)
    e = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                conn[e] = [
                    node_id(i, j, k),
                    node_id(i + 1, j, k),
                    node_id(i + 1, j + 1, k),
                    node_id(i, j + 1, k),
                    node_id(i, j, k + 1),
                    node_id(i + 1, j, k + 1),
                    node_id(i + 1, j + 1, k + 1),
                    node_id(i, j + 1, k + 1),
                ]
                e += 1
    return coords, conn


def build_notched_bar_mesh(
    *,
    n_len: int = 8,
    n_height: int = 4,
    n_thick: int = 1,
    L: float = 8.0,
    H: float = 4.0,
    T: float = 1.0,
    notch_depth: float = 1.0,
    notch_halfwidth: float = 1.0,
) -> NotchedBarMesh:
    """Build a rectangular Hex8 bar with a semi-circular notch on the +y face.

    The undeformed bar spans ``[0, L] x [0, H] x [0, T]``.  A smooth cosine-
    bell profile is subtracted from the y-coordinate of nodes whose x falls
    inside the notch footprint, scaled by ``y / H`` so the bottom face stays
    flat and the top face is pushed down by ``notch_depth``.

    This mirrors the ``_build_notched_bar_mesh`` helper in
    ``tests/test_lemaitre_acceptance.py`` (the P6-3 unit test).  The test-
    tree helper is kept in place so existing tests do not need to be
    modified; both helpers produce identical coordinate arrays for the same
    inputs.

    Parameters
    ----------
    n_len, n_height, n_thick : int
        Element counts along the length, height, and thickness of the
        underlying structured block.
    L, H, T : float
        Bar length, height (pre-notch), and thickness.
    notch_depth : float
        Depth of the notch (how far the +y face is pushed down at the mid-
        plane).
    notch_halfwidth : float
        Half-width of the notch footprint in the x-direction.

    Returns
    -------
    NotchedBarMesh
        Mesh bundle with coordinates, connectivity, boundary node sets, and
        the geometric notch-root point.
    """
    coords, conn = _build_hex8_block(n_len, n_height, n_thick, L, H, T)

    x_centre = L / 2.0
    dx = coords[:, 0] - x_centre
    within = np.abs(dx) < notch_halfwidth
    bell = np.zeros(coords.shape[0], dtype=np.float64)
    bell[within] = 0.5 * (1.0 + np.cos(np.pi * dx[within] / notch_halfwidth))
    push = notch_depth * bell * (coords[:, 1] / H)
    coords[:, 1] -= push

    notch_root_xyz = np.array([x_centre, H - notch_depth, T / 2.0], dtype=np.float64)

    tol = 1e-12
    x_left = np.where(np.abs(coords[:, 0] - 0.0) < tol)[0].astype(np.int64)
    x_right = np.where(np.abs(coords[:, 0] - L) < tol)[0].astype(np.int64)

    return NotchedBarMesh(
        coords=coords,
        connectivity=conn,
        notch_root_xyz=notch_root_xyz,
        x_left_nodes=x_left,
        x_right_nodes=x_right,
        L=L,
        H=H,
        T=T,
        n_len=n_len,
        n_height=n_height,
        n_thick=n_thick,
    )


# ---------------------------------------------------------------------------
# Generated-module helpers
# ---------------------------------------------------------------------------


def _import_generated_module(source: str, tmp_path: Path, name: str) -> Any:
    """Write generated source to a tmp file and import it as a module."""
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        msg = f"Failed to build import spec for {mod_path}"
        raise RuntimeError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_mesh_into_module(mod: Any, coords: NDArray, conn: NDArray) -> None:
    """Allocate fields and push mesh data into the generated Taichi module."""
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]
    mod.allocate_fields(n_nodes, n_elem)
    mod.x_ref.from_numpy(coords)
    for e in range(n_elem):
        for a in range(8):
            mod.elem_nodes[e, a] = int(conn[e, a])


# ---------------------------------------------------------------------------
# Newton driver (Lemaitre, mirrors test_lemaitre_acceptance._newton_step_lemaitre)
# ---------------------------------------------------------------------------


def _newton_step_lemaitre(
    mod: Any,
    u: NDArray,
    bc_mask: NDArray,
    *,
    lam: float,
    mu: float,
    sigma_y0: float,
    K_hard: float,
    n_hard: float,
    S_d: float,
    s_d: float,
    eps_D: float,
    E_mod: float,
    nu_val: float,
    D_crit: float,
    tol: float = 1e-7,
    max_iter: int = 40,
) -> NDArray:
    """Run Newton to convergence for one displacement-controlled Lemaitre step.

    The generated kernel mutates ``alpha`` and ``damage_D`` in place; we
    snapshot them at entry and restore before every residual evaluation so
    intermediate Newton iterates do not corrupt the next step's starting
    point.  This mirrors the driver in the P6-3 unit test exactly (see
    ``tests/test_lemaitre_acceptance.py`` for the same pattern).
    """
    n_nodes = u.shape[0]
    n_dof = n_nodes * 3
    bc_flat = bc_mask.ravel()

    alpha_snapshot = mod.alpha.to_numpy().copy()
    damage_snapshot = mod.damage_D.to_numpy().copy()
    cg = CGSolver()
    R0_norm: float | None = None
    R_norm = float("inf")

    for newton_iter in range(max_iter):
        mod.alpha.from_numpy(alpha_snapshot)
        mod.damage_D.from_numpy(damage_snapshot)
        mod.u.from_numpy(u)
        mod.compute_internal_force(
            lam,
            mu,
            sigma_y0,
            K_hard,
            n_hard,
            S_d,
            s_d,
            eps_D,
            E_mod,
            nu_val,
            D_crit,
        )
        f_int = mod.f_int.to_numpy()
        R = -f_int
        R[bc_mask] = 0.0
        R_flat = R.ravel()
        R_norm = float(np.linalg.norm(R_flat))
        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                break
        assert R0_norm is not None
        if R_norm < tol * max(R0_norm, 1.0):
            break

        def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
            v = v_flat.copy()
            v[bc_flat] = 0.0
            mod.u.from_numpy(_u)
            Kv = mod.tangent_matvec(v, lam, mu, sigma_y0, K_hard, n_hard)
            Kv[bc_flat] = v_flat[bc_flat]
            return np.asarray(Kv, dtype=np.float64)

        du_flat, _, _ = cg.solve(matvec, R_flat, np.zeros(n_dof, dtype=np.float64), 1e-10, 2000)
        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:
        mod.alpha.from_numpy(alpha_snapshot)
        mod.damage_D.from_numpy(damage_snapshot)
        msg = f"Newton did not converge after {max_iter} iters (Lemaitre). Final |R|={R_norm:.3e}"
        raise RuntimeError(msg)

    mod.alpha.from_numpy(alpha_snapshot)
    mod.damage_D.from_numpy(damage_snapshot)
    mod.u.from_numpy(u)
    mod.compute_internal_force(
        lam,
        mu,
        sigma_y0,
        K_hard,
        n_hard,
        S_d,
        s_d,
        eps_D,
        E_mod,
        nu_val,
        D_crit,
    )
    mod.u.from_numpy(u)
    return u


# ---------------------------------------------------------------------------
# Benchmark orchestrator
# ---------------------------------------------------------------------------


def run_notched_bar_benchmark(
    *,
    mesh: NotchedBarMesh,
    material_params: dict[str, float],
    total_displacement: float,
    n_steps: int,
    tmp_path: Path,
    newton_tol: float = 1e-7,
    newton_max_iter: int = 40,
    module_name: str | None = None,
) -> BenchmarkResult:
    """Compile a Lemaitre ProblemIR, solve displacement-controlled tension, record history.

    BCs
    ---
    - Left face (x=0): fully clamped.
    - Right face (x=L): prescribed x-displacement ramped linearly from 0 to
      ``total_displacement`` over ``n_steps`` equal increments.  All y- and
      z-components on the right face are left free (homogeneous Neumann) so
      Poisson contraction is unconstrained -- matches the P6-3 unit-test
      setup.

    Load history extraction
    -----------------------
    At the end of every converged step we sum the x-component of the
    internal force vector at the right-face nodes.  This is the reaction
    force resisting the prescribed displacement (sign-flipped because the
    generated kernel reports ``f_int`` with the convention ``R = -f_int``
    before BC masking; see ``test_lemaitre_acceptance.py`` for the same
    pattern).

    Parameters
    ----------
    mesh : NotchedBarMesh
        Output of :func:`build_notched_bar_mesh`.
    material_params : dict
        Lemaitre material dict, keys:
        ``E``, ``nu``, ``sigma_y0``, ``K``, ``n``, ``S_d``, ``s_d``,
        ``eps_D``, ``D_crit``.  All are required (no silent defaults).
    total_displacement : float
        Final prescribed x-displacement at the right face.
    n_steps : int
        Number of equal displacement increments.
    tmp_path : Path
        Scratch directory for the emitted Taichi module source.
    newton_tol, newton_max_iter : float, int
        Per-step Newton tolerance and iteration cap.  Must accommodate the
        P6-2 Gate B forward-warning that tangent_matvec uses the undamaged
        J2 tangent (sub-linear convergence under active damage); defaults
        match the P6-3 unit-test settings.
    module_name : str, optional
        Override for the generated module's importable name.  Defaults to a
        uuid-based name so repeated runs in the same tmp_path do not
        collide.

    Returns
    -------
    BenchmarkResult
        ``extras`` carries:

        - ``"displacement_history"`` : (n_steps+1,) applied x-displacement
          (includes the zero-load starting point).
        - ``"load_history"``          : (n_steps+1,) reaction force
          (sum of f_int[x_right, 0]) at each step.
        - ``"max_damage"``            : peak D over the whole mesh.
        - ``"damage_elem"``           : (n_elem,) per-element D (max over
          quadrature points) at the final converged state.
        - ``"damage_argmax_element"`` : int, element index of the peak.
        - ``"damage_argmax_centroid"``: (3,) centroid of the peak element.
        - ``"notch_root_xyz"``        : (3,) geometric notch root.
        - ``"notch_root_element"``    : int, element index closest to the
          notch-root point.
        - ``"near_notch_elements"``   : list[int], elements within 1.5*h of
          the notch root (used for the "within one element hop"
          localisation criterion).
    """
    required_keys = {"E", "nu", "sigma_y0", "K", "n", "S_d", "s_d", "eps_D", "D_crit"}
    missing = required_keys - material_params.keys()
    if missing:
        msg = f"material_params is missing Lemaitre keys: {sorted(missing)}"
        raise ValueError(msg)

    E_val = float(material_params["E"])
    nu_val = float(material_params["nu"])
    sigma_y0 = float(material_params["sigma_y0"])
    K_hard = float(material_params["K"])
    n_hard = float(material_params["n"])
    S_d = float(material_params["S_d"])
    s_d = float(material_params["s_d"])
    eps_D = float(material_params["eps_D"])
    D_crit = float(material_params["D_crit"])

    lam = E_val * nu_val / ((1.0 + nu_val) * (1.0 - 2.0 * nu_val))
    mu = E_val / (2.0 * (1.0 + nu_val))

    coords = mesh.coords
    conn = mesh.connectivity
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]

    # --- BCs: clamp x=0 face, prescribe x-disp on x=L face ---
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_mask[mesh.x_left_nodes, :] = True
    bc_mask[mesh.x_right_nodes, 0] = True

    # --- Compile Lemaitre IR ---
    lem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="lemaitre",
            params={
                "E": E_val,
                "nu": nu_val,
                "sigma_y0": sigma_y0,
                "K": K_hard,
                "n": n_hard,
                "S_d": S_d,
                "s_d": s_d,
                "eps_D": eps_D,
                "D_crit": D_crit,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    bundle = mechdsl_compile(lem_ir)
    name = module_name or f"gen_lem_p10_8_notch_{uuid.uuid4().hex[:8]}"
    mod = _import_generated_module(bundle.emitted_source, tmp_path, name)
    _load_mesh_into_module(mod, coords, conn)

    # --- Load stepping ---
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    mod.u.from_numpy(u)

    displacement_history = [0.0]
    load_history = [0.0]
    total_newton_iters = 0

    t0 = time.perf_counter()
    for step in range(1, n_steps + 1):
        frac = step / n_steps
        u[mesh.x_left_nodes, :] = 0.0
        u[mesh.x_right_nodes, 0] = frac * total_displacement
        mod.u.from_numpy(u)
        u = _newton_step_lemaitre(
            mod,
            u,
            bc_mask,
            lam=lam,
            mu=mu,
            sigma_y0=sigma_y0,
            K_hard=K_hard,
            n_hard=n_hard,
            S_d=S_d,
            s_d=s_d,
            eps_D=eps_D,
            E_mod=E_val,
            nu_val=nu_val,
            D_crit=D_crit,
            tol=newton_tol,
            max_iter=newton_max_iter,
        )
        total_newton_iters += 1  # 1 converged step counted; per-iter count not exposed
        # Reaction force = sum of internal forces at the prescribed face.
        # After convergence f_int equals the applied nodal force at Dirichlet
        # nodes (internal equilibrium holds in the rest of the mesh).
        f_int = mod.f_int.to_numpy()
        reaction_x = float(np.sum(f_int[mesh.x_right_nodes, 0]))
        displacement_history.append(frac * total_displacement)
        load_history.append(reaction_x)
    wallclock_s = time.perf_counter() - t0

    # --- Damage post-processing ---
    damage_qp = mod.damage_D.to_numpy()  # (n_elem, n_qp)
    if damage_qp.shape != (n_elem, 8):
        msg = f"Unexpected damage_D shape {damage_qp.shape}; expected ({n_elem}, 8)"
        raise RuntimeError(msg)
    damage_elem = damage_qp.max(axis=1)
    max_damage = float(damage_elem.max())
    damage_argmax = int(np.argmax(damage_elem))

    centroids = coords[conn].mean(axis=1)  # (n_elem, 3)
    d_to_root = np.linalg.norm(centroids - mesh.notch_root_xyz, axis=1)
    notch_root_elem = int(np.argmin(d_to_root))
    h = max(
        mesh.L / mesh.n_len,
        mesh.H / mesh.n_height,
        mesh.T / mesh.n_thick,
    )
    near_notch = np.where(d_to_root <= 1.5 * h)[0].tolist()

    extras: dict[str, Any] = {
        "displacement_history": np.asarray(displacement_history, dtype=np.float64),
        "load_history": np.asarray(load_history, dtype=np.float64),
        "max_damage": max_damage,
        "damage_elem": damage_elem,
        "damage_argmax_element": damage_argmax,
        "damage_argmax_centroid": centroids[damage_argmax].copy(),
        "notch_root_xyz": mesh.notch_root_xyz.copy(),
        "notch_root_element": notch_root_elem,
        "near_notch_elements": near_notch,
        "distance_argmax_to_root": float(d_to_root[damage_argmax]),
        "element_scale_h": float(h),
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=total_newton_iters,
        wallclock_s=wallclock_s,
        extras=extras,
    )
