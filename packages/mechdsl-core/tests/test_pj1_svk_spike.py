"""PlanJune14 **PJ-1** — SVK all-Taichi spike: the architecture gate.

These tests are the gate described in ``dev/plans/PlanJune14.md``:

    The SVK patch solves end-to-end with the generated ``@ti.kernel`` operator +
    injected PCG, **no ``.to_numpy()`` in operator/solve**, and
    ``max|u_gen − u_ref| < 1e-10``. *If this composes, the rest is replication.*

Coverage:

1. Element-level convention parity — the Taichi internal-force / tangent kernels
   reproduce the handwritten NumPy reference element routines (isolates the
   kinematics/quadrature/Voigt conventions from the solver).
2. The architecture gate — a single Hex8 SVK uniaxial-stretch BVP solved fully
   on-device (matrix-free operator injected into the ``ti_runtime`` seams + PCG +
   thin Newton) matches ``ref_hex8_elastic.solve_elastic`` to < 1e-10.
3. No NumPy in the operator/solve hot path (the "all-Taichi" invariant).
"""

import ast
import inspect
import textwrap

import numpy as np
import pytest

from tests.ref.ref_hex8_elastic import (
    element_internal_force,
    element_tangent_matvec,
    generate_hex8_mesh,
    solve_elastic,
)
from tests.spike import svk_hex8_taichi as spike
from tests.spike.svk_hex8_taichi import (
    SVKProblem,
    single_element_internal_force,
    single_element_tangent_matvec,
    solve_svk_hex8,
)

pytestmark = pytest.mark.slow  # every test JIT-compiles Taichi kernels

# Steel-like SVK (matches tests/test_ref_elastic.py).
E_YOUNG = 200.0e3
NU = 0.3
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))

# Gate tolerance from PlanJune14 / 07-CONVENTIONS §6 (generated vs reference).
GATE_TOL = 1e-10


def _unit_cube() -> tuple[np.ndarray, np.ndarray]:
    """Single unit-cube Hex8 element with the reference node ordering."""
    return generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)


# ===========================================================================
# 1. Element-level convention parity (operator kinematics vs reference)
# ===========================================================================


def _local_element_coords() -> np.ndarray:
    """Unit-cube nodes in hex8 *element-local* order (via the mesh connectivity).

    The element-level kernels gather with a trivial ``conn = arange(8)``, so they
    expect the coordinates already in local node order. ``coords[conn[0]]`` maps
    the grid-ordered mesh nodes into that local order — a degenerate (negative
    Jacobian) element results if the grid ordering is used directly.
    """
    coords, conn = _unit_cube()
    return coords[conn[0]]


def test_element_internal_force_matches_ref():
    """Taichi SVK internal-force kernel == NumPy reference (finite displacement)."""
    X = _local_element_coords()
    u = np.zeros((8, 3))
    u[:, 0] = 0.05 * X[:, 0]  # finite uniaxial-ish stretch
    u[:, 1] = -0.012 * X[:, 1]

    f_ti = single_element_internal_force(u, X, LAM, MU)
    f_ref = element_internal_force(u, X, LAM, MU)

    np.testing.assert_allclose(f_ti, f_ref, atol=1e-10, rtol=1e-12)


def test_element_tangent_matvec_matches_ref():
    """Taichi matrix-free tangent matvec == NumPy reference for a random direction."""
    X = _local_element_coords()
    u = np.zeros((8, 3))
    u[:, 0] = 0.05 * X[:, 0]
    v = np.random.default_rng(11).standard_normal((8, 3)) * 1e-2

    Kv_ti = single_element_tangent_matvec(u, X, v, LAM, MU)
    Kv_ref = element_tangent_matvec(u, X, v, LAM, MU)

    np.testing.assert_allclose(Kv_ti, Kv_ref, atol=1e-10, rtol=1e-12)


# ===========================================================================
# 2. The architecture gate — full on-device SVK solve vs reference
# ===========================================================================


def _uniaxial_stretch_problem(stretch: float = 0.1):
    """Single Hex8 patch: left face fixed, right face stretched in x, lateral free."""
    coords, conn = _unit_cube()
    n = coords.shape[0]

    bc_mask = np.zeros((n, 3), dtype=bool)
    bc_values = np.zeros((n, 3), dtype=np.float64)

    left = np.abs(coords[:, 0]) < 1e-12
    right = np.abs(coords[:, 0] - 1.0) < 1e-12
    bc_mask[left, :] = True  # fully fix the x=0 face (kills all rigid-body modes)
    bc_mask[right, 0] = True  # prescribe x-displacement on the x=1 face
    bc_values[right, 0] = stretch  # lateral (y,z) DOFs on the right face stay free

    f_ext = np.zeros((n, 3), dtype=np.float64)
    return coords, conn, bc_mask, bc_values, f_ext


def test_pj1_svk_spike_matches_reference():
    """**Gate**: all-Taichi SVK solve matches the NumPy reference to < 1e-10."""
    coords, conn, bc_mask, bc_values, f_ext = _uniaxial_stretch_problem()

    # Ground truth: handwritten NumPy Newton + ScipyCG.
    u_ref, res_ref = solve_elastic(
        coords,
        conn,
        LAM,
        MU,
        bc_mask,
        bc_values,
        f_ext,
        tol=1e-10,
        cg_tol=1e-12,
    )

    # All-Taichi spike: matrix-free operator + injected PCG + thin Newton.
    prob = SVKProblem(
        coords=coords,
        conn=conn,
        lam=LAM,
        mu=MU,
        bc_mask=bc_mask,
        bc_values=bc_values,
        f_ext=f_ext,
    )
    u_gen, _res_gen = solve_svk_hex8(prob, newton_tol=1e-10, cg_tol=1e-12)

    # Sanity: the problem is nontrivial (finite deformation, Newton iterated).
    assert len(res_ref) >= 2, "expected a nonlinear solve (>=1 Newton step)"
    assert np.max(np.abs(u_gen)) > 1e-3, "expected a nonzero converged displacement"

    max_diff = float(np.max(np.abs(u_gen - u_ref)))
    assert max_diff < GATE_TOL, (
        f"PJ-1 gate failed: max|u_gen - u_ref| = {max_diff:.3e} >= {GATE_TOL:.0e}"
    )


def test_pj1_constrained_dofs_exact():
    """Prescribed/fixed DOFs are reproduced exactly by the on-device solve."""
    coords, conn, bc_mask, bc_values, f_ext = _uniaxial_stretch_problem()
    prob = SVKProblem(
        coords=coords,
        conn=conn,
        lam=LAM,
        mu=MU,
        bc_mask=bc_mask,
        bc_values=bc_values,
        f_ext=f_ext,
    )
    u_gen, _ = solve_svk_hex8(prob, newton_tol=1e-10, cg_tol=1e-12)

    np.testing.assert_allclose(u_gen[bc_mask], bc_values[bc_mask], atol=1e-12)


# ===========================================================================
# 3. No NumPy in the operator / solve hot path
# ===========================================================================


def test_operator_and_solve_are_all_taichi():
    """The operator wrapper and the PCG solver contain no host NumPy / readback.

    ``apply_A`` (built by :func:`make_svk_operator`) and :func:`pcg` are the
    operator/solve hot path. The ``@ti.kernel`` bodies they call are numpy-free by
    construction — Taichi rejects host ``np`` calls in kernel scope, so the fact
    that the gate test compiles and runs them already proves it.
    """
    for fn in (spike.make_svk_operator, spike.pcg):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        # Walk the AST (not the raw text) so docstrings/comments that *mention*
        # ``np`` / ``.to_numpy()`` don't trip the check — only real code does.
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr != "to_numpy", f"{fn.__name__} reads a field back to host"
            if isinstance(node, ast.Name):
                assert node.id != "np", f"{fn.__name__} uses NumPy in the hot path"
