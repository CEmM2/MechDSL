"""Thick-walled internally-pressurised cylinder benchmark (P10-4).

Implements:
  - Quarter-cylinder structured Hex8 mesh generator (theta in [0, pi/2])
  - Inner-pressure loader via 2x2 Gauss quadrature on quad faces
  - Lame plane-strain closed-form solution
  - Full benchmark orchestrator (mesh -> BCs -> solve -> post-process)

Lame formulae (plane-strain, internal pressure p_i, external p_o)
------------------------------------------------------------------
Constants:
    A = (p_i r_i^2 - p_o r_o^2) / (r_o^2 - r_i^2)
    B = (p_i - p_o) r_i^2 r_o^2   / (r_o^2 - r_i^2)

Stress:
    sigma_rr(r)   = A - B/r^2
    sigma_theta_theta(r)   = A + B/r^2

Radial displacement (plane-strain, epsilon_zz = 0):
    u_r(r) = [(1+nu)/E] * [(1-2nu) A r + B/r]

Sanity checks:
    sigma_rr(r_i) = -p_i   (tension-positive convention, inward pressure)
    sigma_rr(r_o) = -p_o   (zero for p_o = 0)

Reference
---------
Timoshenko & Goodier, "Theory of Elasticity", section 28; also Sadd, "Elasticity".
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.verify.benchmarks._core import BenchmarkResult, element_cauchy_stress

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Type alias for the solve_elastic callable (matches ref_hex8_elastic signature)
_SolveElasticFn = Callable[..., tuple["NDArray", list[float]]]

# 1-D Gauss points and weights on [-1, 1]
_G2_PTS = np.array([-1.0 / np.sqrt(3.0), 1.0 / np.sqrt(3.0)])
_G2_WTS = np.array([1.0, 1.0])


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuarterCylinderMesh:
    """Structured Hex8 mesh for a quarter-cylinder (theta in [0, pi/2]).

    Attributes
    ----------
    coords : NDArray, shape (n_nodes, 3)
        Nodal reference coordinates (x, y, z) = (r cos(theta), r sin(theta), z).
    connectivity : NDArray, shape (n_elem, 8)
        Element connectivity (0-based node indices).  Local ordering:
        bottom face (lower z) CCW when viewed from -z, then top face.
    n_nodes : int
    n_elem : int
    inner_nodes : NDArray  - node indices on inner cylindrical surface (r = r_inner)
    outer_nodes : NDArray  - node indices on outer cylindrical surface (r = r_outer)
    theta_0_nodes : NDArray  - symmetry face at theta = 0 (y = 0 plane)
    theta_pi2_nodes : NDArray  - symmetry face at theta = pi/2 (x = 0 plane)
    z0_nodes : NDArray  - face at z = 0
    z1_nodes : NDArray  - face at z = height
    inner_faces : list[tuple[int, int, int, int]]
        Quad faces on the inner surface, each as (n0, n1, n2, n3) global node
        indices in CCW order when viewed from outside (i.e. from the fluid).
    """

    coords: NDArray  # (n_nodes, 3)
    connectivity: NDArray  # (n_elem, 8)
    n_nodes: int
    n_elem: int
    inner_nodes: NDArray
    outer_nodes: NDArray
    theta_0_nodes: NDArray
    theta_pi2_nodes: NDArray
    z0_nodes: NDArray
    z1_nodes: NDArray
    inner_faces: list[tuple[int, int, int, int]] = field(default_factory=list)


@dataclass(frozen=True)
class LameSolution:
    """Closed-form plane-strain Lame solution evaluated at sample radii.

    Attributes
    ----------
    r : NDArray  - sample radii at which solution is evaluated
    u_r : NDArray  - radial displacement u_r(r)
    sigma_rr : NDArray  - radial stress sigma_rr(r)
    sigma_theta_theta : NDArray  - hoop stress sigma_theta_theta(r)
    """

    r: NDArray
    u_r: NDArray
    sigma_rr: NDArray
    sigma_theta_theta: NDArray


# ---------------------------------------------------------------------------
# Mesh generator
# ---------------------------------------------------------------------------


def generate_quarter_cylinder_mesh(
    r_inner: float,
    r_outer: float,
    height: float,
    nr: int,
    ntheta: int,
    nz: int,
    *,
    radial_bias: float = 1.0,
) -> QuarterCylinderMesh:
    """Generate a structured Hex8 quarter-cylinder mesh.

    Node ordering in the parametric space (i, j, k):
      i in [0, nr]     - radial index (r_inner -> r_outer)
      j in [0, ntheta] - angular index (0 -> pi/2)
      k in [0, nz]     - axial index  (0 -> height)

    Node numbering: k varies slowest, j next, i fastest:
        node_id(i, j, k) = k * (ntheta+1) * (nr+1) + j * (nr+1) + i

    Each Hex8 element connects the eight corners of one (i, j, k) cell.
    Local element node ordering follows the standard convention:
        bottom face (k, k): nodes in CCW order viewed from -z
        top face (k+1):     nodes in CCW order viewed from -z

        local 0: (i,   j,   k  )
        local 1: (i+1, j,   k  )
        local 2: (i+1, j+1, k  )
        local 3: (i,   j+1, k  )
        local 4: (i,   j,   k+1)
        local 5: (i+1, j,   k+1)
        local 6: (i+1, j+1, k+1)
        local 7: (i,   j+1, k+1)

    Here "i" is the radial direction (varying r), "j" is the angular
    direction (varying theta), and "k" is the axial direction (varying z).

    Parameters
    ----------
    r_inner, r_outer : float
        Inner and outer radii.
    height : float
        Cylinder height.
    nr, ntheta, nz : int
        Number of elements in radial, angular, and axial directions.
    radial_bias : float
        Geometric progression ratio for radial node spacing.  ratio=1
        gives uniform spacing; ratio > 1 clusters nodes near r_inner
        (recommended for capturing hoop-stress gradient near the inner wall).
        The n+1 radii satisfy r[i] = r_inner + (r_outer - r_inner) * f(i/nr)
        where f is derived from a geometric series with the given ratio.

    Returns
    -------
    QuarterCylinderMesh
    """
    if r_inner <= 0 or r_outer <= r_inner:
        msg = f"Need 0 < r_inner < r_outer, got {r_inner}, {r_outer}"
        raise ValueError(msg)
    if nr < 1 or ntheta < 1 or nz < 1:
        msg = f"Need nr, ntheta, nz >= 1, got {nr}, {ntheta}, {nz}"
        raise ValueError(msg)

    # --- Build radial node positions (geometric progression if bias != 1) ---
    if abs(radial_bias - 1.0) < 1e-12:
        # Uniform spacing
        r_nodes = np.linspace(r_inner, r_outer, nr + 1)
    else:
        q = radial_bias
        # Geometric series: spacings s_0, s_0*q, ..., s_0*q^(nr-1)
        # sum = s_0 * (q^nr - 1) / (q - 1) = r_outer - r_inner
        s0 = (r_outer - r_inner) * (q - 1.0) / (q**nr - 1.0)
        r_nodes = np.empty(nr + 1)
        r_nodes[0] = r_inner
        for i in range(1, nr + 1):
            r_nodes[i] = r_nodes[i - 1] + s0 * q ** (i - 1)
        r_nodes[-1] = r_outer  # clamp to avoid float drift

    theta_nodes = np.linspace(0.0, np.pi / 2.0, ntheta + 1)
    z_nodes = np.linspace(0.0, height, nz + 1)

    # --- Build coords ---
    n_nodes = (nr + 1) * (ntheta + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ntheta + 1) * (nr + 1) + j * (nr + 1) + i

    idx = 0
    for k in range(nz + 1):
        for j in range(ntheta + 1):
            for i in range(nr + 1):
                r = r_nodes[i]
                th = theta_nodes[j]
                coords[idx, 0] = r * np.cos(th)
                coords[idx, 1] = r * np.sin(th)
                coords[idx, 2] = z_nodes[k]
                idx += 1

    # --- Build connectivity ---
    n_elem = nr * ntheta * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)

    eidx = 0
    for k in range(nz):
        for j in range(ntheta):
            for i in range(nr):
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

    # --- Boundary node sets ---
    tol = 1e-10

    # Radial boundaries: identify by |r - r_ref| < tol
    r_coord = np.sqrt(coords[:, 0] ** 2 + coords[:, 1] ** 2)
    inner_nodes = np.where(np.abs(r_coord - r_inner) < tol)[0].astype(np.int64)
    outer_nodes = np.where(np.abs(r_coord - r_outer) < tol)[0].astype(np.int64)

    # Angular boundaries: theta=0 <-> y~=0 (sin(theta)=0), theta=pi/2 <-> x~=0 (cos(theta)=0)
    theta_0_nodes = np.where(np.abs(coords[:, 1]) < tol)[0].astype(np.int64)
    theta_pi2_nodes = np.where(np.abs(coords[:, 0]) < tol)[0].astype(np.int64)

    # Axial boundaries
    z0_nodes = np.where(np.abs(coords[:, 2] - 0.0) < tol)[0].astype(np.int64)
    z1_nodes = np.where(np.abs(coords[:, 2] - height) < tol)[0].astype(np.int64)

    # --- Inner face quads ---
    # Each element with i=0 has a quad face on the inner surface.
    # The face consists of local nodes {0, 3, 7, 4} (the j- and k-varying
    # nodes at i=0).  We list them so their outward normal points toward
    # the cylinder axis (inward radially - INTO the fluid), which means
    # the face normal computed via cross product will point inward (-r_hat).
    # The traction on the SOLID is +p*r_hat, which is -(-p*n_hat).
    # We enumerate the face with nodes CCW when viewed from outside
    # (from the fluid side, looking toward +r_hat):
    #   bottom-left=(i=0,j,k), bottom-right=(i=0,j+1,k),
    #   top-right=(i=0,j+1,k+1), top-left=(i=0,j,k+1)
    # This gives outward normal pointing IN -r_hat direction (outward from solid
    # into fluid), which is the convention we want.
    inner_faces: list[tuple[int, int, int, int]] = []
    for k in range(nz):
        for j in range(ntheta):
            n_bl = node_id(0, j, k)
            n_br = node_id(0, j + 1, k)
            n_tr = node_id(0, j + 1, k + 1)
            n_tl = node_id(0, j, k + 1)
            inner_faces.append((n_bl, n_br, n_tr, n_tl))

    return QuarterCylinderMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        inner_nodes=inner_nodes,
        outer_nodes=outer_nodes,
        theta_0_nodes=theta_0_nodes,
        theta_pi2_nodes=theta_pi2_nodes,
        z0_nodes=z0_nodes,
        z1_nodes=z1_nodes,
        inner_faces=inner_faces,
    )


# ---------------------------------------------------------------------------
# Pressure loader
# ---------------------------------------------------------------------------


def apply_inner_pressure_as_nodal_forces(
    mesh: QuarterCylinderMesh,
    pressure: float,
) -> NDArray:
    """Integrate internal pressure into equivalent nodal forces.

    For each quad face on the inner cylindrical surface, computes the
    traction integral using 2x2 Gauss quadrature:

        f_a = integral (p * r_hat) N_a dA

    where r_hat is the outward unit normal of the SOLID (pointing away from the
    cylinder axis, i.e. +r_hat), and N_a is the bilinear shape function for
    face node a.

    The four-node bilinear face shape functions on the reference face
    [-1,1]^2 are:
        N_0(s,t) = (1-s)(1-t)/4
        N_1(s,t) = (1+s)(1-t)/4
        N_2(s,t) = (1+s)(1+t)/4
        N_3(s,t) = (1-s)(1+t)/4

    The physical traction is p * n_hat_solid = p * (+r_hat).  Applied to the
    inner surface, r_hat points outward from the axis, so the force on the
    solid is compressive in the usual sense but positive in the r-direction.

    Parameters
    ----------
    mesh : QuarterCylinderMesh
    pressure : float
        Internal pressure magnitude (positive = compressive on inner wall).

    Returns
    -------
    f_ext : NDArray, shape (n_nodes, 3)
        Equivalent nodal force array.
    """
    f_ext = np.zeros((mesh.n_nodes, 3), dtype=np.float64)

    # Reference face shape functions and their derivatives on [-1,1]^2
    def face_N(s: float, t: float) -> NDArray:
        return 0.25 * np.array(
            [
                (1.0 - s) * (1.0 - t),
                (1.0 + s) * (1.0 - t),
                (1.0 + s) * (1.0 + t),
                (1.0 - s) * (1.0 + t),
            ]
        )

    def face_dN_ds(s: float, t: float) -> NDArray:
        return 0.25 * np.array([-(1.0 - t), (1.0 - t), (1.0 + t), -(1.0 + t)])

    def face_dN_dt(s: float, t: float) -> NDArray:
        return 0.25 * np.array([-(1.0 - s), -(1.0 + s), (1.0 + s), (1.0 - s)])

    for face in mesh.inner_faces:
        # face is (n0, n1, n2, n3) - four corner node global indices
        X_face = mesh.coords[list(face)]  # (4, 3)

        for si, wi in zip(_G2_PTS, _G2_WTS, strict=True):
            for ti, wt in zip(_G2_PTS, _G2_WTS, strict=True):
                N = face_N(si, ti)  # (4,)
                dN_ds = face_dN_ds(si, ti)  # (4,)
                dN_dt = face_dN_dt(si, ti)  # (4,)

                # Physical tangent vectors
                dx_ds = X_face.T @ dN_ds  # (3,)
                dx_dt = X_face.T @ dN_dt  # (3,)

                # Face node ordering (bl, br, tr, tl) gives s varying in +theta_hat
                # and t varying in +z_hat, so cross(dx_ds, dx_dt) = theta_hat x z_hat = +r_hat.
                # This is the direction from fluid (r < r_inner) into solid,
                # and hence the direction of the surface traction under internal
                # pressure p (force on solid per unit area = p * r_hat).
                normal_raw = np.cross(dx_ds, dx_dt)  # points in +r_hat
                dA = np.linalg.norm(normal_raw)
                n_hat = normal_raw / dA  # unit normal in +r_hat direction

                # Traction on solid: p * n_hat (pushes shell outward under
                # internal pressure, per Cauchy stress convention)
                traction = pressure * n_hat  # (3,)

                # Nodal force contributions: f_a += w_s * w_t * N_a * traction * dA
                for a in range(4):
                    f_ext[face[a]] += wi * wt * N[a] * traction * dA

    return f_ext


# ---------------------------------------------------------------------------
# Lame closed-form solution
# ---------------------------------------------------------------------------


def lame_solution(
    r: float | NDArray,
    r_inner: float,
    r_outer: float,
    p_inner: float,
    p_outer: float,
    E: float,
    nu: float,
) -> LameSolution:
    """Plane-strain Lame solution for a thick-walled cylinder.

    Parameters
    ----------
    r : float or array
        Radii at which to evaluate the solution.
    r_inner, r_outer : float
        Inner and outer radii.
    p_inner, p_outer : float
        Applied pressures (positive = compressive, outward convention).
        With tension-positive stress convention: sigma_rr(r_inner) = -p_inner.
    E, nu : float
        Young's modulus and Poisson's ratio.

    Returns
    -------
    LameSolution
        Radial displacement, radial stress, and hoop stress at each r.
    """
    r_arr = np.atleast_1d(np.asarray(r, dtype=np.float64))
    ri2 = r_inner**2
    ro2 = r_outer**2
    denom = ro2 - ri2

    # Lame constants for the stress field
    A = (p_inner * ri2 - p_outer * ro2) / denom
    B = (p_inner - p_outer) * ri2 * ro2 / denom

    sigma_rr = A - B / r_arr**2
    sigma_tt = A + B / r_arr**2

    # Plane-strain radial displacement
    # u_r(r) = [(1+nu)/E] * [(1-2nu)*A*r + B/r]
    u_r = ((1.0 + nu) / E) * ((1.0 - 2.0 * nu) * A * r_arr + B / r_arr)

    return LameSolution(
        r=r_arr,
        u_r=u_r,
        sigma_rr=sigma_rr,
        sigma_theta_theta=sigma_tt,
    )


# ---------------------------------------------------------------------------
# Benchmark orchestrator
# ---------------------------------------------------------------------------


def run_thick_cylinder_benchmark(
    *,
    r_inner: float,
    r_outer: float,
    height: float,
    nr: int,
    ntheta: int,
    nz: int,
    pressure: float,
    E: float,
    nu: float,
    solve_elastic: _SolveElasticFn,
    sample_radii: NDArray | None = None,
    tol: float = 1e-8,
    max_iter: int = 50,
    radial_bias: float = 1.0,
) -> BenchmarkResult:
    """Orchestrate the thick cylinder benchmark.

    Parameters
    ----------
    r_inner, r_outer : float
    height : float
        Cylinder height (axial extent).
    nr, ntheta, nz : int
        Mesh refinement in radial, angular, and axial directions.
    pressure : float
        Internal pressure.
    E, nu : float
        Young's modulus and Poisson's ratio.
    solve_elastic : callable
        The Newton-CG solver, injected by the caller.  Signature must match
        ``tests.ref.ref_hex8_elastic.solve_elastic``.  This keeps the harness
        module free of a hard dependency on the ``tests`` tree.
    sample_radii : array-like, optional
        Radii at which to compare FEM vs Lame.  Defaults to 5 evenly-
        spaced radii strictly inside [r_inner, r_outer].
    tol : float
        Newton convergence tolerance (relative residual).
    max_iter : int
        Maximum Newton iterations.
    radial_bias : float
        Geometric bias for radial node spacing (>1 = cluster near inner wall).

    Returns
    -------
    BenchmarkResult
        ``extras`` contains:
        - ``"sample_radii"``      : (M,) array of query radii
        - ``"u_r_fem"``           : (M,) FEM radial displacement at sample radii
        - ``"u_r_lame"``          : (M,) Lame radial displacement
        - ``"u_r_rel_err"``       : (M,) |FEM - Lame| / |Lame|
        - ``"sigma_tt_fem"``      : (M,) FEM hoop stress at sample radii
        - ``"sigma_tt_lame"``     : (M,) Lame hoop stress
        - ``"sigma_tt_rel_err"``  : (M,) relative hoop-stress error
    """
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E / (2.0 * (1.0 + nu))

    mesh = generate_quarter_cylinder_mesh(
        r_inner, r_outer, height, nr, ntheta, nz, radial_bias=radial_bias
    )

    # --- Dirichlet BCs ---
    n_nodes = mesh.n_nodes
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)

    # Symmetry at theta=0 (y=0 face): constrain u_y = 0
    bc_mask[mesh.theta_0_nodes, 1] = True

    # Symmetry at theta=pi/2 (x=0 face): constrain u_x = 0
    bc_mask[mesh.theta_pi2_nodes, 0] = True

    # Plane-strain: constrain u_z = 0 on both z-faces
    bc_mask[mesh.z0_nodes, 2] = True
    bc_mask[mesh.z1_nodes, 2] = True

    # --- External forces: internal pressure ---
    f_ext = apply_inner_pressure_as_nodal_forces(mesh, pressure)

    # --- Solve ---
    t0 = time.perf_counter()
    u, residuals = solve_elastic(
        mesh.coords,
        mesh.connectivity,
        lam,
        mu,
        bc_mask,
        bc_values,
        f_ext,
        tol=tol,
        max_iter=max_iter,
    )
    wallclock_s = time.perf_counter() - t0

    # --- Sample radii ---
    if sample_radii is None:
        sample_radii = np.array([1.1, 1.25, 1.5, 1.75, 1.9])

    sample_radii = np.asarray(sample_radii, dtype=np.float64)

    # --- Extract FEM radial displacements at nodal points closest to sample r ---
    # For each sample radius, pick the node with |r_node - r_sample| minimised
    # that is NOT on the symmetry planes (to avoid BC-constrained nodes).
    # Use nodes at mid-height (z ~= height/2) and mid-angle (theta ~= pi/4).
    coords = mesh.coords
    r_coord = np.sqrt(coords[:, 0] ** 2 + coords[:, 1] ** 2)

    # Prefer nodes away from symmetry planes: require both x > 0 and y > 0
    free_mask = (coords[:, 0] > 1e-8) & (coords[:, 1] > 1e-8)
    # Also prefer mid-height nodes
    mid_z = height / 2.0
    z_weight = np.abs(coords[:, 2] - mid_z)

    u_r_fem = np.empty(len(sample_radii))
    for idx, rs in enumerate(sample_radii):
        radial_dist = np.abs(r_coord - rs)
        # Combined score: prefer free nodes, penalise z-distance slightly
        score = radial_dist.copy()
        score[~free_mask] += 1e6  # exclude boundary nodes
        score += z_weight * 1e-3  # soft preference for mid-height
        node = int(np.argmin(score))
        # Radial direction at that node
        x_n, y_n = coords[node, 0], coords[node, 1]
        th_n = np.arctan2(y_n, x_n)
        r_hat = np.array([np.cos(th_n), np.sin(th_n), 0.0])
        u_r_fem[idx] = float(u[node] @ r_hat)

    # --- Extract FEM hoop stress at element centroids near sample radii ---
    # Compute centroid radius for each element; skip symmetry-plane elements
    n_elem = mesh.n_elem
    elem_r_centroid = np.empty(n_elem)
    elem_theta_centroid = np.empty(n_elem)
    for e in range(n_elem):
        nodes = mesh.connectivity[e]
        xc = float(np.mean(coords[nodes, 0]))
        yc = float(np.mean(coords[nodes, 1]))
        elem_r_centroid[e] = np.sqrt(xc**2 + yc**2)
        elem_theta_centroid[e] = np.arctan2(yc, xc)

    # Symmetry-plane elements: theta_c < 0.05 or theta_c > pi/2 - 0.05
    sym_plane = (elem_theta_centroid < 0.05) | (elem_theta_centroid > np.pi / 2.0 - 0.05)

    sigma_tt_fem = np.empty(len(sample_radii))
    for idx, rs in enumerate(sample_radii):
        radial_dist_e = np.abs(elem_r_centroid - rs)
        score_e = radial_dist_e.copy()
        score_e[sym_plane] += 1e6
        e_best = int(np.argmin(score_e))

        nodes_e = mesh.connectivity[e_best]
        sigma = element_cauchy_stress(u[nodes_e], coords[nodes_e], lam, mu)  # (3, 3) Cauchy

        # Hoop stress: sigma_theta_theta = e_theta * sigma * e_theta  at element centroid
        th_e = elem_theta_centroid[e_best]
        e_theta = np.array([-np.sin(th_e), np.cos(th_e), 0.0])
        sigma_tt_fem[idx] = float(e_theta @ sigma @ e_theta)

    # --- Lame reference ---
    lame = lame_solution(sample_radii, r_inner, r_outer, pressure, 0.0, E, nu)

    # --- Relative errors ---
    u_r_rel_err = np.abs(u_r_fem - lame.u_r) / np.abs(lame.u_r)
    sigma_tt_rel_err = np.abs(sigma_tt_fem - lame.sigma_theta_theta) / np.abs(
        lame.sigma_theta_theta
    )

    extras: dict = {
        "sample_radii": sample_radii,
        "u_r_fem": u_r_fem,
        "u_r_lame": lame.u_r,
        "u_r_rel_err": u_r_rel_err,
        "sigma_tt_fem": sigma_tt_fem,
        "sigma_tt_lame": lame.sigma_theta_theta,
        "sigma_tt_rel_err": sigma_tt_rel_err,
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=len(residuals),
        wallclock_s=wallclock_s,
        extras=extras,
    )
