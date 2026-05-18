"""Tests targeting the array-like cast path in mechdsl.verify._assembly.

Why this file exists
--------------------
Phase 6 added ``cast("NDArray", ...)`` to the Newton residual closure in
``_assembly.solve_svk_elastic`` as a mypy annotation fix::

    def residual_fn(u_cur: NDArray) -> NDArray:
        return cast("NDArray", f_ext - assemble_internal_force(u_cur, ...))

``typing.cast`` is a **runtime no-op** — it changes nothing at execution time.
However, the surrounding subtraction relies on NumPy broadcasting to accept
any array-like ``f_ext``, not just an ``np.ndarray``.  If the upstream type
of ``f_ext`` changes (e.g. to a plain Python list or another array subclass
in Plan B), the cast would silently annotate the wrong type while NumPy's
coercion masks the real type error.

These tests verify two things:

1. ``assemble_internal_force`` always returns an ``np.ndarray`` (so the
   right-hand side of the subtraction is always typed correctly).
2. ``solve_svk_elastic`` produces identical converged solutions whether
   ``f_ext`` is supplied as an ``np.ndarray`` or as a Python ``list`` —
   i.e. NumPy's coercion handles the array-like input correctly and the
   cast does not hide a breakage.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.verify._assembly import assemble_internal_force, solve_svk_elastic

# ---------------------------------------------------------------------------
# Minimal test mesh — single Hex8 unit cube
# ---------------------------------------------------------------------------


def _unit_cube_mesh() -> tuple[np.ndarray, np.ndarray]:
    """Return (coords, conn) for a single Hex8 element on [0,1]^3.

    Node ordering follows the standard right-hand Hex8 convention used
    throughout the codebase (see 07-CONVENTIONS.md).
    """
    coords = np.array(
        [
            [0.0, 0.0, 0.0],  # node 0
            [1.0, 0.0, 0.0],  # node 1
            [1.0, 1.0, 0.0],  # node 2
            [0.0, 1.0, 0.0],  # node 3
            [0.0, 0.0, 1.0],  # node 4
            [1.0, 0.0, 1.0],  # node 5
            [1.0, 1.0, 1.0],  # node 6
            [0.0, 1.0, 1.0],  # node 7
        ],
        dtype=np.float64,
    )
    conn = np.array([[0, 1, 2, 3, 4, 5, 6, 7]], dtype=np.int32)
    return coords, conn


def _svk_params() -> tuple[float, float]:
    """Lamé parameters for E=200e3, nu=0.3."""
    E, nu = 200e3, 0.3
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    return lam, mu


def _dirichlet_setup(
    coords: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Clamp x=0 face (nodes 0,3,4,7) and apply small uniform traction on x=1.

    Returns
    -------
    bc_mask : (n_nodes, 3) bool
        True where Dirichlet is prescribed.
    bc_values : (n_nodes, 3) float
        Prescribed displacements (zero for clamped nodes).
    f_ext : (n_nodes, 3) float  as ndarray
        External force vector (small traction on x=1 face).
    """
    n = coords.shape[0]
    bc_mask = np.zeros((n, 3), dtype=bool)
    bc_values = np.zeros((n, 3), dtype=np.float64)

    # Clamp the x=0 face
    x0_nodes = [i for i, c in enumerate(coords) if c[0] < 1e-12]
    for nd in x0_nodes:
        bc_mask[nd, :] = True

    # Uniform traction on x=1 face (nodes 1,2,5,6) — small load
    f_ext = np.zeros((n, 3), dtype=np.float64)
    x1_nodes = [i for i, c in enumerate(coords) if c[0] > 1 - 1e-12]
    for nd in x1_nodes:
        f_ext[nd, 0] = 0.25  # distribute unit traction across 4 nodes

    return bc_mask, bc_values, f_ext


# ---------------------------------------------------------------------------
# 1. assemble_internal_force always returns np.ndarray
# ---------------------------------------------------------------------------


class TestAssembleInternalForceReturnType:
    """assemble_internal_force must return np.ndarray regardless of u input."""

    def test_returns_ndarray_for_zero_displacement(self) -> None:
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        u = np.zeros_like(coords)
        result = assemble_internal_force(u, coords, conn, lam, mu)
        assert isinstance(result, np.ndarray), (
            f"Expected np.ndarray, got {type(result)}. "
            "If this fails after a Plan B refactor, check the cast in residual_fn."
        )

    def test_returns_ndarray_for_nonzero_displacement(self) -> None:
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        rng = np.random.default_rng(42)
        u = rng.uniform(-0.01, 0.01, size=coords.shape)
        result = assemble_internal_force(u, coords, conn, lam, mu)
        assert isinstance(result, np.ndarray)

    def test_result_shape_matches_coords(self) -> None:
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        u = np.zeros_like(coords)
        result = assemble_internal_force(u, coords, conn, lam, mu)
        assert result.shape == coords.shape

    def test_zero_displacement_gives_zero_internal_force(self) -> None:
        """Undeformed reference config: no strain → no stress → zero f_int."""
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        u = np.zeros_like(coords)
        f_int = assemble_internal_force(u, coords, conn, lam, mu)
        np.testing.assert_allclose(f_int, 0.0, atol=1e-14)


# ---------------------------------------------------------------------------
# 2. solve_svk_elastic: ndarray vs list f_ext produce identical results
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestResidualFnCastPath:
    """Verify that the residual_fn cast path works for array-like f_ext.

    These tests are marked ``slow`` because they run a full Newton solve.
    """

    def test_ndarray_f_ext_converges(self) -> None:
        """Baseline: standard ndarray f_ext should converge without error."""
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        bc_mask, bc_values, f_ext = _dirichlet_setup(coords)
        u, residuals = solve_svk_elastic(
            coords=coords,
            conn=conn,
            lam=lam,
            mu=mu,
            bc_mask=bc_mask,
            bc_values=bc_values,
            f_ext=f_ext,
            tol=1e-10,
            max_iter=30,
        )
        assert isinstance(u, np.ndarray)
        assert len(residuals) > 0
        assert residuals[-1] < 1e-9

    def test_list_f_ext_matches_ndarray_f_ext(self) -> None:
        """Passing f_ext as a Python list must produce the same solution.

        This exercises the cast path: ``f_ext - assemble_internal_force(...)``
        where ``f_ext`` is a list.  NumPy's broadcasting coerces the list to
        an array; the typing.cast annotates the result as NDArray.  If Plan B
        changes something upstream that breaks this coercion, this test will
        catch it.
        """
        coords, conn = _unit_cube_mesh()
        lam, mu = _svk_params()
        bc_mask, bc_values, f_ext_arr = _dirichlet_setup(coords)

        # Convert f_ext to a nested Python list — array-like but not ndarray
        f_ext_list = f_ext_arr.tolist()

        u_arr, _ = solve_svk_elastic(
            coords=coords,
            conn=conn,
            lam=lam,
            mu=mu,
            bc_mask=bc_mask,
            bc_values=bc_values,
            f_ext=f_ext_arr,
            tol=1e-10,
            max_iter=30,
        )
        u_list, _ = solve_svk_elastic(
            coords=coords,
            conn=conn,
            lam=lam,
            mu=mu,
            bc_mask=bc_mask,
            bc_values=bc_values,
            f_ext=f_ext_list,  # type: ignore[arg-type]
            tol=1e-10,
            max_iter=30,
        )

        np.testing.assert_array_equal(
            u_arr,
            u_list,
            err_msg=(
                "solve_svk_elastic produced different results for ndarray vs list f_ext. "
                "Check the cast in residual_fn inside _assembly.solve_svk_elastic."
            ),
        )
