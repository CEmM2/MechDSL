"""Convergence rate checker and MMS driver for mesh refinement studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np


@dataclass
class ConvergenceResult:
    """Result of a convergence rate check.

    Attributes
    ----------
    measured_rate:
        The log-log slope of error vs mesh size, fitted via ``np.polyfit``.
    expected_rate:
        The expected (minimum acceptable) convergence rate supplied by the caller.
    passed:
        ``True`` when ``measured_rate >= expected_rate - tol``.
    errors:
        The error values supplied to the check (copy of input array).
    mesh_sizes:
        The mesh-size values supplied to the check (copy of input array).
    tol:
        The tolerance used in the pass/fail comparison.
    """

    measured_rate: float
    expected_rate: float
    passed: bool
    errors: np.ndarray
    mesh_sizes: np.ndarray
    tol: float


def check_convergence_rate(
    errors: np.ndarray | list[float],
    mesh_sizes: np.ndarray | list[float],
    expected_rate: float,
    tol: float = 0.1,
) -> ConvergenceResult:
    """Check that the measured log-log convergence rate meets the expected rate.

    Fits a degree-1 polynomial to ``(log h, log e)`` data using :func:`numpy.polyfit`
    and asserts that the measured slope is at least ``expected_rate - tol``.

    Parameters
    ----------
    errors:
        Sequence of error norms (e.g. L2 or H1), one per mesh refinement level.
        All values must be strictly positive.
    mesh_sizes:
        Sequence of representative mesh sizes *h* corresponding to *errors*.
        All values must be strictly positive.  Typically listed from coarse to
        fine (decreasing order), but the function accepts any ordering.
    expected_rate:
        The minimum acceptable convergence rate.  For Hex8 (p=1):
        * L2 rate ≥ 2.0
        * H1 rate ≥ 1.0
    tol:
        Tolerance subtracted from *expected_rate* to form the pass/fail
        threshold.  Default is 0.1 (per 07-CONVENTIONS.md §6 and
        08-VERIFICATION.md §4.2).

    Returns
    -------
    ConvergenceResult
        Dataclass containing the measured rate, expected rate, pass/fail flag,
        and copies of the input arrays.

    Raises
    ------
    ValueError
        If fewer than 3 data points are supplied (minimum required for a
        meaningful slope fit).
    ValueError
        If *errors* and *mesh_sizes* have different lengths.
    ValueError
        If any error or mesh-size value is not strictly positive.
    """
    errors = np.asarray(errors, dtype=float)
    mesh_sizes = np.asarray(mesh_sizes, dtype=float)

    if errors.ndim != 1 or mesh_sizes.ndim != 1:
        raise ValueError("errors and mesh_sizes must be 1-D arrays.")

    if len(errors) != len(mesh_sizes):
        raise ValueError(
            f"errors and mesh_sizes must have the same length, "
            f"got {len(errors)} and {len(mesh_sizes)}."
        )

    if len(errors) < 3:
        raise ValueError(
            f"At least 3 data points are required for a meaningful convergence rate "
            f"fit, but only {len(errors)} were supplied."
        )

    if np.any(errors <= 0):
        raise ValueError("All error values must be strictly positive.")

    if np.any(mesh_sizes <= 0):
        raise ValueError("All mesh-size values must be strictly positive.")

    log_h = np.log(mesh_sizes)
    log_e = np.log(errors)

    # Degree-1 polyfit: log(e) = rate * log(h) + const
    coeffs = np.polyfit(log_h, log_e, 1)
    measured_rate: float = float(coeffs[0])

    passed = measured_rate >= expected_rate - tol

    return ConvergenceResult(
        measured_rate=measured_rate,
        expected_rate=expected_rate,
        passed=passed,
        errors=errors.copy(),
        mesh_sizes=mesh_sizes.copy(),
        tol=tol,
    )


# ---------------------------------------------------------------------------
# MMS (Method of Manufactured Solutions) driver
# ---------------------------------------------------------------------------


def _compute_mms_body_force_lambdas(
    L_val: float = 1.0,
    A_val: float = 1e-3,
) -> tuple:
    """Symbolically derive the MMS body force and return lambdified functions.

    The manufactured displacement is a *scalar* field multiplied by ``[1, 1, 1]``:

        u*(X) = A * sin(pi*X1/L) * cos(pi*X2/L) * sin(pi*X3/L) * [1, 1, 1]

    From this we compute:

    1.  F* = I + grad(u*)
    2.  C* = F*.T @ F*
    3.  E* = 0.5 * (C* - I)
    4.  S* = lam * tr(E*) * I + 2 * mu * E*   (SVK)
    5.  P* = F* @ S*
    6.  b* = -Div(P*)   (row-wise divergence, b*_i = -dP*_{iJ}/dX_J)

    Parameters
    ----------
    L_val, A_val : float
        Domain length and displacement amplitude (baked into the symbolic
        expression so the returned lambdas depend only on ``(X1, X2, X3,
        lam, mu)``).

    Returns
    -------
    body_force_func : callable(X1, X2, X3, lam, mu) -> (3,) ndarray
        The MMS body force at a single material point.
    u_exact_func : callable(X1, X2, X3) -> (3,) ndarray
        The manufactured displacement at a single material point.
    grad_u_exact_func : callable(X1, X2, X3) -> (3, 3) ndarray
        The gradient of the manufactured displacement, du*_i/dX_J.
    """
    import sympy as sp

    X1, X2, X3 = sp.symbols("X1 X2 X3", real=True)
    lam, mu = sp.symbols("lam mu", positive=True)
    pi = sp.pi
    A = sp.Rational(A_val).limit_denominator(10**12) if A_val != 1e-3 else sp.Rational(1, 1000)
    Lsym = sp.nsimplify(L_val, rational=True)

    # Scalar manufactured field
    phi = A * sp.sin(pi * X1 / Lsym) * sp.cos(pi * X2 / Lsym) * sp.sin(pi * X3 / Lsym)

    # u* = phi * [1, 1, 1]
    u_star = sp.Matrix([phi, phi, phi])

    coords = [X1, X2, X3]

    # grad_u*: (du*_i / dX_J)  -- 3x3
    grad_u = sp.Matrix(3, 3, lambda i, j: sp.diff(u_star[i], coords[j]))

    # F* = I + grad_u*
    I3 = sp.eye(3)
    F_star = I3 + grad_u

    # C* = F*^T @ F*
    C_star = F_star.T * F_star

    # E* = 0.5 * (C* - I)
    E_star = sp.Rational(1, 2) * (C_star - I3)

    # S* = lam * tr(E*) * I + 2*mu*E*  (SVK)
    tr_E = sp.trace(E_star)
    S_star = lam * tr_E * I3 + 2 * mu * E_star

    # P* = F* @ S*
    P_star = F_star * S_star

    # b* = -Div(P*)  =>  b*_i = - sum_J dP*_{iJ}/dX_J
    b_star = sp.Matrix(3, 1, lambda i, _: -sum(sp.diff(P_star[i, J], coords[J]) for J in range(3)))

    # --- Simplify with CSE for speed ---
    b_components = [sp.simplify(b_star[i]) for i in range(3)]

    # Lambdify
    body_force_func = sp.lambdify(
        (X1, X2, X3, lam, mu),
        b_components,
        modules="numpy",
    )

    # Exact displacement (already simple)
    u_components = [u_star[i] for i in range(3)]
    u_exact_func = sp.lambdify(
        (X1, X2, X3),
        u_components,
        modules="numpy",
    )

    # Exact displacement gradient
    grad_components = [[grad_u[i, j] for j in range(3)] for i in range(3)]
    grad_u_exact_func = sp.lambdify(
        (X1, X2, X3),
        grad_components,
        modules="numpy",
    )

    return body_force_func, u_exact_func, grad_u_exact_func


# Module-level cache: keyed by (L, A)
_mms_cache: dict[tuple[float, float], tuple] = {}


def _get_mms_lambdas(L: float = 1.0, A: float = 1e-3) -> tuple:
    """Return cached lambdified MMS functions for given ``(L, A)``."""
    key = (L, A)
    if key not in _mms_cache:
        _mms_cache[key] = _compute_mms_body_force_lambdas(L_val=L, A_val=A)
    return _mms_cache[key]


def mms_body_force(
    X1: float,
    X2: float,
    X3: float,
    lam: float,
    mu: float,
    *,
    L: float = 1.0,
    A: float = 1e-3,
) -> np.ndarray:
    """Evaluate the MMS body force at a single material point.

    Returns shape ``(3,)`` ndarray.
    """
    bf_func, _, _ = _get_mms_lambdas(L, A)
    vals = bf_func(X1, X2, X3, lam, mu)
    return np.array(vals, dtype=np.float64)


def mms_exact_displacement(
    X1: float,
    X2: float,
    X3: float,
    *,
    L: float = 1.0,
    A: float = 1e-3,
) -> np.ndarray:
    """Evaluate the manufactured displacement at a single material point.

    Returns shape ``(3,)`` ndarray.
    """
    _, u_func, _ = _get_mms_lambdas(L, A)
    vals = u_func(X1, X2, X3)
    return np.array(vals, dtype=np.float64)


def mms_exact_displacement_gradient(
    X1: float,
    X2: float,
    X3: float,
    *,
    L: float = 1.0,
    A: float = 1e-3,
) -> np.ndarray:
    """Evaluate grad(u*) at a single material point.

    Returns shape ``(3, 3)`` ndarray where entry ``[i, J]`` is ``du*_i / dX_J``.
    """
    _, _, grad_func = _get_mms_lambdas(L, A)
    vals = grad_func(X1, X2, X3)
    return np.array(vals, dtype=np.float64)


def _identify_boundary_nodes(coords: np.ndarray, L: float, tol_frac: float = 1e-12) -> np.ndarray:
    """Return boolean mask ``(n_nodes,)`` — True for nodes on the domain boundary."""
    tol = tol_frac * L
    on_face = np.zeros(coords.shape[0], dtype=bool)
    for d in range(3):
        on_face |= coords[:, d] < tol
        on_face |= coords[:, d] > L - tol
    return on_face


def _compute_consistent_nodal_forces(
    coords: np.ndarray,
    conn: np.ndarray,
    lam: float,
    mu: float,
    *,
    L: float = 1.0,
    A: float = 1e-3,
) -> np.ndarray:
    """Compute consistent (Gauss-integrated) nodal body forces.

    Integrates ``b*(X) * N_a(X) * det(J0)`` over each element using
    the same 2x2x2 Gauss rule as the solver, then scatters to global DOFs.

    Returns shape ``(n_nodes, 3)``.
    """
    from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature

    basis = hex8_basis()
    quad = hex8_quadrature()
    bf_func, _, _ = _get_mms_lambdas(L, A)

    n_nodes = coords.shape[0]
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

    for e in range(conn.shape[0]):
        nodes = conn[e]
        X_elem = coords[nodes]

        for q in range(quad.n_points):
            xi, eta, zeta = quad.points[q]
            w_q = quad.weights[q]

            # Shape functions at this quad point
            N_vals = basis.evaluate(xi, eta, zeta)

            # Shape function gradients in parametric space -> reference Jacobian
            dN_dxi = basis.gradient(xi, eta, zeta)
            J0 = X_elem.T @ dN_dxi
            detJ0 = float(np.linalg.det(J0))

            # Physical coordinates at this quad point
            X_qp = N_vals @ X_elem

            # Body force at this quad point
            b_vals = bf_func(X_qp[0], X_qp[1], X_qp[2], lam, mu)
            b_vec = np.array(b_vals, dtype=np.float64)

            # Scatter: f_ext[a, :] += w * det(J0) * N_a * b
            for a in range(8):
                f_ext[nodes[a]] += w_q * detJ0 * N_vals[a] * b_vec

    return f_ext


def _compute_l2_h1_errors(
    u_h: np.ndarray,
    coords: np.ndarray,
    conn: np.ndarray,
    *,
    L: float = 1.0,
    A: float = 1e-3,
) -> tuple[float, float]:
    """Compute L2 and H1 error norms over the mesh.

    Uses 2x2x2 Gauss quadrature per element (same as the solver).

    L2 error = sqrt( integral |u_h - u*|^2 dV )
    H1 error = sqrt( integral |grad(u_h) - grad(u*)|^2 dV )

    Returns ``(l2_error, h1_error)``.
    """
    from mechdsl.ir.element_ir import hex8_basis, hex8_quadrature

    basis = hex8_basis()
    quad = hex8_quadrature()
    _, u_func, grad_func = _get_mms_lambdas(L, A)

    l2_sq = 0.0
    h1_sq = 0.0

    for e in range(conn.shape[0]):
        nodes = conn[e]
        X_elem = coords[nodes]
        u_elem = u_h[nodes]

        for q in range(quad.n_points):
            xi, eta, zeta = quad.points[q]
            w_q = quad.weights[q]

            # Shape functions and gradients
            N_vals = basis.evaluate(xi, eta, zeta)
            dN_dxi = basis.gradient(xi, eta, zeta)

            # Reference Jacobian
            J0 = X_elem.T @ dN_dxi
            detJ0 = float(np.linalg.det(J0))
            J0_inv = np.linalg.inv(J0)

            # Shape function gradients in reference coords: dN/dX = dN/dxi @ J0^{-1}
            dN_dX = dN_dxi @ J0_inv

            # Physical coordinates at quad point
            X_qp = N_vals @ X_elem

            # --- L2 error ---
            # Interpolated displacement at quad point
            u_h_qp = N_vals @ u_elem

            # Exact displacement at quad point
            u_exact_vals = u_func(X_qp[0], X_qp[1], X_qp[2])
            u_exact_qp = np.array(u_exact_vals, dtype=np.float64)

            diff_u = u_h_qp - u_exact_qp
            l2_sq += w_q * detJ0 * np.dot(diff_u, diff_u)

            # --- H1 error ---
            # Interpolated displacement gradient: grad(u_h) = u_elem^T @ dN_dX  -> (3, 3)
            grad_u_h = u_elem.T @ dN_dX

            # Exact displacement gradient at quad point
            grad_exact_vals = grad_func(X_qp[0], X_qp[1], X_qp[2])
            grad_u_exact = np.array(grad_exact_vals, dtype=np.float64)

            diff_grad = grad_u_h - grad_u_exact
            h1_sq += w_q * detJ0 * np.sum(diff_grad**2)

    return float(np.sqrt(l2_sq)), float(np.sqrt(h1_sq))


def run_mms_convergence(
    lam: float,
    mu: float,
    mesh_levels: list[int] | None = None,
    L: float = 1.0,
    A: float = 1e-3,
    solver_tol: float = 1e-7,
    solver_max_iter: int = 100,
    cg_tol: float = 1e-12,
    cg_max_iter: int = 5000,
) -> tuple[list[float], list[float], list[float]]:
    """Run MMS convergence study on a sequence of uniform Hex8 meshes.

    Parameters
    ----------
    lam, mu : float
        Lame parameters for the SVK material.
    mesh_levels : list[int], optional
        Number of elements per edge for each refinement level.
        Defaults to ``[2, 4, 8]``.
    L : float
        Domain size ``[0, L]^3``.  Default 1.0.
    A : float
        Amplitude of the manufactured displacement.  Must be small enough
        for the nonlinear solver to converge (default 1e-3).
    solver_tol : float
        Relative Newton tolerance.
    solver_max_iter : int
        Maximum Newton iterations.
    cg_tol : float
        Relative CG tolerance.
    cg_max_iter : int
        Maximum CG iterations.

    Returns
    -------
    l2_errors : list[float]
        L2 error norm for each mesh level.
    h1_errors : list[float]
        H1 error norm for each mesh level.
    mesh_sizes : list[float]
        Characteristic mesh size h = L / n for each level.
    """

    from mechdsl.solver.mesh_io import generate_hex8_mesh as _gen_mesh
    from mechdsl.verify._assembly import solve_svk_elastic

    if mesh_levels is None:
        mesh_levels = [2, 3, 4]

    # Pre-compute the lambdified MMS functions (cached)
    _get_mms_lambdas(L, A)

    l2_errors: list[float] = []
    h1_errors: list[float] = []
    mesh_sizes: list[float] = []

    for n in mesh_levels:
        h = L / n
        mesh_sizes.append(h)

        # 1. Generate mesh
        mesh = _gen_mesh(n, n, n, L, L, L)
        coords, conn = mesh.coords, mesh.connectivity
        n_nodes = coords.shape[0]

        # 2. Compute consistent nodal body forces
        f_ext = _compute_consistent_nodal_forces(coords, conn, lam, mu, L=L, A=A)

        # 3. Identify boundary nodes and apply exact Dirichlet BCs
        on_boundary = _identify_boundary_nodes(coords, L)

        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)

        _, u_func, _ = _get_mms_lambdas(L, A)

        for node_idx in range(n_nodes):
            if on_boundary[node_idx]:
                bc_mask[node_idx, :] = True
                u_vals = u_func(
                    coords[node_idx, 0],
                    coords[node_idx, 1],
                    coords[node_idx, 2],
                )
                bc_values[node_idx, :] = np.array(u_vals, dtype=np.float64)

        # 4. Solve
        u_h, _res_hist = solve_svk_elastic(
            coords,
            conn,
            lam,
            mu,
            bc_mask,
            bc_values,
            f_ext,
            tol=solver_tol,
            max_iter=solver_max_iter,
            cg_tol=cg_tol,
            cg_max_iter=cg_max_iter,
        )

        # 5. Compute errors
        l2_err, h1_err = _compute_l2_h1_errors(u_h, coords, conn, L=L, A=A)
        l2_errors.append(l2_err)
        h1_errors.append(h1_err)

    return l2_errors, h1_errors, mesh_sizes


def verify_mms_body_force_substitution(
    lam: float,
    mu: float,
    *,
    L: float = 1.0,
    A: float = 1e-3,
    n_test_points: int = 5,
    fd_eps: float = 1e-6,
) -> float:
    """Verify MMS body force against finite-difference Div(P*).

    At random interior points computes b*(X) from the symbolic expression
    and -Div(P*)(X) via central finite differences, returning the worst-case
    relative error across all test points and components.
    """
    bf, _, gf = _get_mms_lambdas(L, A)

    def _P(Xpt: np.ndarray) -> np.ndarray:
        gu = np.array(gf(float(Xpt[0]), float(Xpt[1]), float(Xpt[2])), dtype=np.float64)
        I3 = np.eye(3, dtype=np.float64)
        F = I3 + gu
        E = 0.5 * (F.T @ F - I3)
        return cast("np.ndarray", F @ (lam * np.trace(E) * I3 + 2.0 * mu * E))

    rng = np.random.default_rng(42)
    worst = 0.0
    for _ in range(n_test_points):
        Xpt = rng.uniform(0.1 * L, 0.9 * L, size=3)
        b_sym = np.array(bf(Xpt[0], Xpt[1], Xpt[2], lam, mu), dtype=np.float64)
        neg_div = np.zeros(3, dtype=np.float64)
        for J in range(3):
            Xp, Xm = Xpt.copy(), Xpt.copy()
            Xp[J] += fd_eps
            Xm[J] -= fd_eps
            neg_div -= (_P(Xp)[:, J] - _P(Xm)[:, J]) / (2.0 * fd_eps)
        re = float(np.max(np.abs(b_sym - neg_div) / (np.abs(neg_div) + 1e-30)))
        worst = max(worst, re)
    return worst
