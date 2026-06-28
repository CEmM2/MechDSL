"""Kirsch plate-with-hole benchmark harness (P10-5).

Implements a quarter-plate mesh with a circular hole centred at the origin,
loaded by uniform tension on the far ``x = W`` boundary. The benchmark uses
symmetry on ``x = 0`` and ``y = 0`` and compares the peak hole-edge
``sigma_xx`` against the Kirsch analytical stress-concentration factor
``K_t = 3`` for an infinite plate under uniaxial tension.

Scope
-----
This harness is benchmark-local and bypasses the still-Hex8-only lowering /
codegen surface. It builds directly on the Phase 5 element basis/quadrature
support via :class:`mechdsl.ir.element_factory.ElementFactory`, which is
enough for the benchmark's reference-style solve in the ``verify`` layer.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.solver.newton import NewtonConfig, newton_solve
from mechdsl.symbolic.models.svk import SVKMaterial, material_tangent_4th
from mechdsl.verify.benchmarks._core import BenchmarkResult

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.ir.element_ir import ElementIR

_I3 = np.eye(3, dtype=np.float64)
_SQRT_3_OVER_5 = math.sqrt(3.0 / 5.0)
_FACE_GAUSS_PTS = np.array([-_SQRT_3_OVER_5, 0.0, _SQRT_3_OVER_5], dtype=np.float64)
_FACE_GAUSS_WTS = np.array([5.0 / 9.0, 8.0 / 9.0, 5.0 / 9.0], dtype=np.float64)
_EDGE_ORDER_HEX20: tuple[tuple[int, int], ...] = (
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


@dataclass(frozen=True)
class PlateWithHoleParameters:
    """Benchmark parameters for the Kirsch plate-with-hole problem."""

    element_type: Literal["hex8", "hex20"]
    radius: float = 1.0
    half_width: float = 12.0
    thickness: float = 1.0
    n_radial: int = 6
    n_theta: int = 12
    n_z: int = 1
    radial_bias: float = 1.3
    sigma_applied: float = 1.0
    E: float = 1000.0
    nu: float = 0.3
    newton_tol: float = 1e-8
    newton_max_iter: int = 30
    cg_tol: float = 1e-10
    cg_max_iter: int = 3000


@dataclass(frozen=True)
class PlateWithHoleMesh:
    """Quarter-plate mesh and boundary metadata for the Kirsch benchmark."""

    coords: NDArray
    connectivity: NDArray
    n_nodes: int
    n_elem: int
    inner_nodes: NDArray
    x0_nodes: NDArray
    y0_nodes: NDArray
    z0_nodes: NDArray
    z1_nodes: NDArray
    traction_elements: NDArray


def _radial_nodes(radius: float, half_width: float, n_radial: int, radial_bias: float) -> NDArray:
    """Geometric progression in the radial-like mesh coordinate."""
    if abs(radial_bias - 1.0) < 1e-12:
        return np.linspace(radius, half_width, n_radial + 1, dtype=np.float64)

    q = radial_bias
    span = half_width - radius
    s0 = span * (q - 1.0) / (q**n_radial - 1.0)
    r_nodes = np.empty(n_radial + 1, dtype=np.float64)
    r_nodes[0] = radius
    for i in range(1, n_radial + 1):
        r_nodes[i] = r_nodes[i - 1] + s0 * q ** (i - 1)
    r_nodes[-1] = half_width
    return r_nodes


def _ray_to_square(
    radius: float, half_width: float, rho: float, theta: float
) -> tuple[float, float]:
    """Map a radial coordinate ``rho`` and angle ``theta`` to the quarter plate."""
    c = math.cos(theta)
    s = math.sin(theta)
    scale = max(abs(c), abs(s), 1e-14)
    r_outer = half_width / scale
    r = radius + rho * (r_outer - radius)
    return r * c, r * s


def _generate_hex8_plate_with_hole_mesh(
    *,
    radius: float,
    half_width: float,
    thickness: float,
    n_radial: int,
    n_theta: int,
    n_z: int,
    radial_bias: float,
) -> PlateWithHoleMesh:
    """Generate a structured Hex8 quarter-plate mesh with a circular hole."""
    if half_width <= 10.0 * radius:
        raise ValueError(
            f"Kirsch benchmark needs half_width > 10 * radius, got {half_width} and {radius}."
        )
    if n_theta % 4 != 0:
        raise ValueError(
            f"n_theta must be divisible by 4 so theta=pi/4 is a mesh line, got {n_theta}."
        )

    rho_nodes = _radial_nodes(radius, half_width, n_radial, radial_bias)
    theta_nodes = np.linspace(0.0, 0.5 * math.pi, n_theta + 1, dtype=np.float64)
    z_nodes = np.linspace(0.0, thickness, n_z + 1, dtype=np.float64)

    n_nodes = (n_radial + 1) * (n_theta + 1) * (n_z + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)

    def node_id(i: int, j: int, k: int) -> int:
        return k * (n_theta + 1) * (n_radial + 1) + j * (n_radial + 1) + i

    idx = 0
    for k in range(n_z + 1):
        for j in range(n_theta + 1):
            theta = float(theta_nodes[j])
            for i in range(n_radial + 1):
                rho = float((rho_nodes[i] - radius) / (half_width - radius))
                x, y = _ray_to_square(radius, half_width, rho, theta)
                coords[idx] = (x, y, z_nodes[k])
                idx += 1

    n_elem = n_radial * n_theta * n_z
    conn = np.empty((n_elem, 8), dtype=np.int64)
    traction_elements: list[int] = []

    eidx = 0
    tol = 1e-10
    for k in range(n_z):
        for j in range(n_theta):
            for i in range(n_radial):
                n0 = node_id(i, j, k)
                n1 = node_id(i + 1, j, k)
                n2 = node_id(i + 1, j + 1, k)
                n3 = node_id(i, j + 1, k)
                n4 = node_id(i, j, k + 1)
                n5 = node_id(i + 1, j, k + 1)
                n6 = node_id(i + 1, j + 1, k + 1)
                n7 = node_id(i, j + 1, k + 1)
                conn[eidx] = [n0, n1, n2, n3, n4, n5, n6, n7]

                if i == n_radial - 1:
                    outer_face = np.array([n1, n2, n6, n5], dtype=np.int64)
                    if np.all(np.abs(coords[outer_face, 0] - half_width) < tol):
                        traction_elements.append(eidx)
                eidx += 1

    r_coord = np.sqrt(coords[:, 0] ** 2 + coords[:, 1] ** 2)
    inner_nodes = np.where(np.abs(r_coord - radius) < 1e-8)[0].astype(np.int64)
    x0_nodes = np.where(np.abs(coords[:, 0]) < tol)[0].astype(np.int64)
    y0_nodes = np.where(np.abs(coords[:, 1]) < tol)[0].astype(np.int64)
    z0_nodes = np.where(np.abs(coords[:, 2]) < tol)[0].astype(np.int64)
    z1_nodes = np.where(np.abs(coords[:, 2] - thickness) < tol)[0].astype(np.int64)

    return PlateWithHoleMesh(
        coords=coords,
        connectivity=conn,
        n_nodes=n_nodes,
        n_elem=n_elem,
        inner_nodes=inner_nodes,
        x0_nodes=x0_nodes,
        y0_nodes=y0_nodes,
        z0_nodes=z0_nodes,
        z1_nodes=z1_nodes,
        traction_elements=np.asarray(traction_elements, dtype=np.int64),
    )


def _upgrade_hex8_mesh_to_hex20(mesh: PlateWithHoleMesh, radius: float) -> PlateWithHoleMesh:
    """Upgrade a structured Hex8 mesh to Hex20 by adding deduplicated edge midpoints."""
    coords_list = [mesh.coords[i].copy() for i in range(mesh.n_nodes)]
    edge_to_mid: dict[tuple[int, int], int] = {}
    conn20 = np.empty((mesh.n_elem, 20), dtype=np.int64)

    def _midpoint(a: int, b: int) -> NDArray:
        xa = mesh.coords[a]
        xb = mesh.coords[b]
        ra = float(np.hypot(xa[0], xa[1]))
        rb = float(np.hypot(xb[0], xb[1]))

        # Keep the circular hole exact on arc edges.
        if abs(ra - radius) < 1e-8 and abs(rb - radius) < 1e-8 and abs(xa[2] - xb[2]) < 1e-12:
            theta_mid = 0.5 * (math.atan2(xa[1], xa[0]) + math.atan2(xb[1], xb[0]))
            return np.array([radius * math.cos(theta_mid), radius * math.sin(theta_mid), xa[2]])
        return np.asarray(0.5 * (xa + xb), dtype=np.float64)

    for e, nodes8 in enumerate(mesh.connectivity):
        nodes20 = np.empty(20, dtype=np.int64)
        nodes20[:8] = nodes8
        for local_idx, (ia, ib) in enumerate(_EDGE_ORDER_HEX20, start=8):
            a = int(nodes8[ia])
            b = int(nodes8[ib])
            key = (a, b) if a < b else (b, a)
            if key not in edge_to_mid:
                edge_to_mid[key] = len(coords_list)
                coords_list.append(_midpoint(a, b))
            nodes20[local_idx] = edge_to_mid[key]
        conn20[e] = nodes20

    coords20 = np.asarray(coords_list, dtype=np.float64)
    tol = 1e-10
    r_coord = np.sqrt(coords20[:, 0] ** 2 + coords20[:, 1] ** 2)

    return PlateWithHoleMesh(
        coords=coords20,
        connectivity=conn20,
        n_nodes=coords20.shape[0],
        n_elem=mesh.n_elem,
        inner_nodes=np.where(np.abs(r_coord - radius) < 1e-8)[0].astype(np.int64),
        x0_nodes=np.where(np.abs(coords20[:, 0]) < tol)[0].astype(np.int64),
        y0_nodes=np.where(np.abs(coords20[:, 1]) < tol)[0].astype(np.int64),
        z0_nodes=np.where(np.abs(coords20[:, 2]) < tol)[0].astype(np.int64),
        z1_nodes=np.where(np.abs(coords20[:, 2] - float(np.max(mesh.coords[:, 2]))) < tol)[
            0
        ].astype(np.int64),
        traction_elements=mesh.traction_elements.copy(),
    )


def build_plate_with_hole_mesh(params: PlateWithHoleParameters) -> PlateWithHoleMesh:
    """Build either the Hex8 or Hex20 quarter-plate mesh for the benchmark."""
    mesh_hex8 = _generate_hex8_plate_with_hole_mesh(
        radius=params.radius,
        half_width=params.half_width,
        thickness=params.thickness,
        n_radial=params.n_radial,
        n_theta=params.n_theta,
        n_z=params.n_z,
        radial_bias=params.radial_bias,
    )
    if params.element_type == "hex8":
        return mesh_hex8
    if params.element_type == "hex20":
        return _upgrade_hex8_mesh_to_hex20(mesh_hex8, params.radius)
    raise ValueError(f"Unsupported element_type {params.element_type!r}.")


def _shape_grad_reference(
    element_ir: ElementIR,
    X_elem: NDArray,
    xi: float,
    eta: float,
    zeta: float,
) -> tuple[NDArray, float]:
    """Compute shape gradients in the reference configuration."""
    dN_dxi = element_ir.basis.gradient(xi, eta, zeta)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        raise ValueError(
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at ({xi}, {eta}, {zeta})."
        )
    dN_dX = dN_dxi @ np.linalg.inv(J0)
    return dN_dX, detJ0


def _element_internal_force(
    element_ir: ElementIR,
    u_elem: NDArray,
    X_elem: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """SVK internal force for one element of arbitrary supported topology."""
    n_nodes = element_ir.n_nodes
    f_int = np.zeros((n_nodes, 3), dtype=np.float64)

    for q in range(element_ir.quadrature.n_points):
        xi, eta, zeta = (float(v) for v in element_ir.quadrature.points[q])
        w_q = float(element_ir.quadrature.weights[q])
        dN_dX, detJ0 = _shape_grad_reference(element_ir, X_elem, xi, eta, zeta)
        grad_u = u_elem.T @ dN_dX
        F = _I3 + grad_u
        E = 0.5 * (F.T @ F - _I3)
        tr_E = float(np.trace(E))
        S = lam * tr_E * _I3 + 2.0 * mu * E
        P = F @ S
        f_int += w_q * detJ0 * (dN_dX @ P.T)

    return f_int


def _element_tangent_matvec(
    element_ir: ElementIR,
    u_elem: NDArray,
    X_elem: NDArray,
    v_elem: NDArray,
    lam: float,
    mu: float,
    C4: NDArray,
) -> NDArray:
    """Analytical tangent matvec for one SVK element."""
    n_nodes = element_ir.n_nodes
    Kv = np.zeros((n_nodes, 3), dtype=np.float64)

    for q in range(element_ir.quadrature.n_points):
        xi, eta, zeta = (float(v) for v in element_ir.quadrature.points[q])
        w_q = float(element_ir.quadrature.weights[q])
        dN_dX, detJ0 = _shape_grad_reference(element_ir, X_elem, xi, eta, zeta)

        grad_u = u_elem.T @ dN_dX
        F = _I3 + grad_u
        E = 0.5 * (F.T @ F - _I3)
        tr_E = float(np.trace(E))
        S = lam * tr_E * _I3 + 2.0 * mu * E

        grad_v = v_elem.T @ dN_dX
        dE = 0.5 * (F.T @ grad_v + grad_v.T @ F)
        dS = np.einsum("ijkl,kl->ij", C4, dE)
        dP = grad_v @ S + F @ dS
        Kv += w_q * detJ0 * (dN_dX @ dP.T)

    return Kv


def _assemble_internal_force(
    element_ir: ElementIR,
    u: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
) -> NDArray:
    """Assemble the global internal force."""
    f_int = np.zeros_like(u)
    for e in range(conn.shape[0]):
        nodes = conn[e]
        f_e = _element_internal_force(element_ir, u[nodes], coords[nodes], lam, mu)
        for a, node in enumerate(nodes):
            f_int[node] += f_e[a]
    return f_int


def _assemble_tangent_matvec(
    element_ir: ElementIR,
    u: NDArray,
    v: NDArray,
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    C4: NDArray,
) -> NDArray:
    """Assemble the global tangent matvec."""
    Kv = np.zeros_like(v)
    for e in range(conn.shape[0]):
        nodes = conn[e]
        Kv_e = _element_tangent_matvec(element_ir, u[nodes], coords[nodes], v[nodes], lam, mu, C4)
        for a, node in enumerate(nodes):
            Kv[node] += Kv_e[a]
    return Kv


def _element_face_traction(
    element_ir: ElementIR,
    X_elem: NDArray,
    traction: NDArray,
) -> NDArray:
    """Equivalent nodal traction vector on the element's ``xi = +1`` face."""
    f_face = np.zeros((element_ir.n_nodes, 3), dtype=np.float64)

    for i_eta, eta in enumerate(_FACE_GAUSS_PTS):
        for i_zeta, zeta in enumerate(_FACE_GAUSS_PTS):
            xi = 1.0
            w_q = float(_FACE_GAUSS_WTS[i_eta] * _FACE_GAUSS_WTS[i_zeta])
            N = element_ir.basis.evaluate(xi, float(eta), float(zeta))
            G = element_ir.basis.gradient(xi, float(eta), float(zeta))
            dX_deta = X_elem.T @ G[:, 1]
            dX_dzeta = X_elem.T @ G[:, 2]
            detJs = float(np.linalg.norm(np.cross(dX_deta, dX_dzeta)))
            f_face += w_q * detJs * N[:, None] * traction[None, :]

    return f_face


def _build_external_force(
    mesh: PlateWithHoleMesh,
    element_ir: ElementIR,
    sigma_applied: float,
) -> NDArray:
    """Assemble the far-field traction on the right boundary."""
    traction = np.array([sigma_applied, 0.0, 0.0], dtype=np.float64)
    f_ext = np.zeros((mesh.n_nodes, 3), dtype=np.float64)

    for e in mesh.traction_elements:
        nodes = mesh.connectivity[int(e)]
        f_face = _element_face_traction(element_ir, mesh.coords[nodes], traction)
        for a, node in enumerate(nodes):
            f_ext[node] += f_face[a]

    return f_ext


def _solve_plate_with_hole(
    mesh: PlateWithHoleMesh,
    element_ir: ElementIR,
    params: PlateWithHoleParameters,
) -> tuple[NDArray, list[float], float]:
    """Solve the TL-SVK Kirsch benchmark for the supplied mesh and topology."""
    mat = SVKMaterial.from_E_nu(params.E, params.nu)
    lam = float(mat.lam)
    mu = float(mat.mu)
    C4 = material_tangent_4th(mat)

    bc_mask = np.zeros((mesh.n_nodes, 3), dtype=bool)
    bc_values = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    bc_mask[mesh.x0_nodes, 0] = True
    bc_mask[mesh.y0_nodes, 1] = True
    bc_mask[:, 2] = True  # Plane-strain surrogate for the 3D solid benchmark.

    f_ext = _build_external_force(mesh, element_ir, params.sigma_applied)
    u0 = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    u0[bc_mask] = bc_values[bc_mask]

    def residual_fn(u_cur: NDArray) -> NDArray:
        residual = f_ext - _assemble_internal_force(
            element_ir,
            u_cur,
            mesh.coords,
            mesh.connectivity,
            lam,
            mu,
        )
        return np.asarray(residual, dtype=np.float64)

    def tangent_fn(u_cur: NDArray, v: NDArray) -> NDArray:
        return _assemble_tangent_matvec(
            element_ir,
            u_cur,
            v,
            mesh.coords,
            mesh.connectivity,
            lam,
            mu,
            C4,
        )

    config = NewtonConfig(
        tol=params.newton_tol,
        max_iter=params.newton_max_iter,
        cg_tol=params.cg_tol,
        cg_max_iter=params.cg_max_iter,
    )

    t0 = time.perf_counter()
    result = newton_solve(
        assemble_residual=residual_fn,
        tangent_matvec=tangent_fn,
        u=u0,
        bc_mask=bc_mask,
        config=config,
    )
    wallclock_s = time.perf_counter() - t0

    if not result.converged:
        raise RuntimeError(
            f"Kirsch plate-with-hole benchmark did not converge after {result.n_iterations} Newton iterations. "
            f"Final |R| = {result.residual_history[-1]:.3e}"
        )
    return u0, result.residual_history, wallclock_s


def _nodal_sigma_xx(
    mesh: PlateWithHoleMesh,
    element_ir: ElementIR,
    u: NDArray,
    E: float,
    nu: float,
) -> NDArray:
    """Extrapolate ``sigma_xx`` from quadrature points to nodal values."""
    mat = SVKMaterial.from_E_nu(E, nu)
    lam = float(mat.lam)
    mu = float(mat.mu)

    sigma_sum = np.zeros(mesh.n_nodes, dtype=np.float64)
    sigma_count = np.zeros(mesh.n_nodes, dtype=np.int64)

    for e in range(mesh.n_elem):
        nodes = mesh.connectivity[e]
        X_elem = mesh.coords[nodes]
        u_elem = u[nodes]

        n_qp = element_ir.quadrature.n_points
        N_q = np.empty((n_qp, element_ir.n_nodes), dtype=np.float64)
        sigma_q = np.empty(n_qp, dtype=np.float64)

        for q in range(n_qp):
            xi, eta, zeta = (float(v) for v in element_ir.quadrature.points[q])
            dN_dX, _ = _shape_grad_reference(element_ir, X_elem, xi, eta, zeta)
            grad_u = u_elem.T @ dN_dX
            F = _I3 + grad_u
            E_gl = 0.5 * (F.T @ F - _I3)
            tr_E = float(np.trace(E_gl))
            S = lam * tr_E * _I3 + 2.0 * mu * E_gl
            J = float(np.linalg.det(F))
            sigma = (1.0 / J) * (F @ S @ F.T)

            N_q[q] = element_ir.basis.evaluate(xi, eta, zeta)
            sigma_q[q] = float(sigma[0, 0])

        sigma_nodes = np.linalg.lstsq(N_q, sigma_q, rcond=None)[0]
        for a, node in enumerate(nodes):
            sigma_sum[node] += sigma_nodes[a]
            sigma_count[node] += 1

    sigma_count = np.maximum(sigma_count, 1)
    return sigma_sum / sigma_count


def run_plate_with_hole_benchmark(
    *,
    params: PlateWithHoleParameters,
) -> BenchmarkResult:
    """Run the Kirsch plate-with-hole benchmark for Hex8 or Hex20."""
    mesh = build_plate_with_hole_mesh(params)
    element_ir = ElementFactory.create(params.element_type, formulation="total_lagrangian")
    u, residual_history, wallclock_s = _solve_plate_with_hole(mesh, element_ir, params)
    sigma_xx_nodal = _nodal_sigma_xx(mesh, element_ir, u, params.E, params.nu)

    hole_sigma_xx = sigma_xx_nodal[mesh.inner_nodes]
    peak_idx_local = int(np.argmax(hole_sigma_xx))
    peak_node = int(mesh.inner_nodes[peak_idx_local])
    peak_sigma_xx = float(hole_sigma_xx[peak_idx_local])
    k_t = peak_sigma_xx / params.sigma_applied
    rel_error = abs(k_t - 3.0) / 3.0

    extras = {
        "k_t": k_t,
        "k_t_reference": 3.0,
        "relative_error": rel_error,
        "peak_sigma_xx": peak_sigma_xx,
        "sigma_applied": params.sigma_applied,
        "peak_node": peak_node,
        "peak_node_coords": mesh.coords[peak_node].copy(),
        "sigma_xx_nodal": sigma_xx_nodal,
        "hole_nodes": mesh.inner_nodes.copy(),
        "residual_history": residual_history,
        "traction_elements": mesh.traction_elements.copy(),
        "n_nodes": mesh.n_nodes,
        "n_elem": mesh.n_elem,
        "element_type": params.element_type,
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=max(len(residual_history) - 1, 0),
        wallclock_s=wallclock_s,
        extras=extras,
    )
