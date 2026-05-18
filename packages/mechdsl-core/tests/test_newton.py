"""Tests for Phase 3: Newton-Raphson runtime driver.

Covers tasks P3-T1 (newton_solve implementation), P3-T2 (unit tests),
and P3-T3 (integration with load_stepping + reference comparison).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from mechdsl.solver import (
    NewtonConfig,
    NewtonResult,
    newton_solve,
)
from mechdsl.solver.history_fields import HistoryFields

# Reference solver assembly functions
from tests.ref.ref_hex8_elastic import (
    assemble_internal_force as ref_assemble_f_int,
)
from tests.ref.ref_hex8_elastic import (
    element_tangent_matvec as ref_elem_tangent_matvec,
)
from tests.ref.ref_hex8_elastic import (
    generate_hex8_mesh,
)

# ============================================================================
# Helpers
# ============================================================================


def _raw_global_matvec(
    u: np.ndarray,
    v: np.ndarray,
    coords: np.ndarray,
    conn: np.ndarray,
    lam: float,
    mu: float,
) -> np.ndarray:
    """Global tangent matvec WITHOUT BC enforcement.

    newton_solve applies BC enforcement internally, so the callback
    must provide the raw (no identity-row) assembly.
    """
    n_nodes = coords.shape[0]
    Kv = np.zeros((n_nodes, 3), dtype=np.float64)
    for e in range(conn.shape[0]):
        nodes = conn[e]
        Kv_e = ref_elem_tangent_matvec(u[nodes], coords[nodes], v[nodes], lam, mu)
        for a in range(8):
            Kv[nodes[a]] += Kv_e[a]
    return Kv


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def elastic_setup() -> dict:
    """4x2x1 Hex8 elastic cantilever (matches test_ref_elastic pattern)."""
    coords, conn = generate_hex8_mesh(4, 2, 1, 4.0, 2.0, 1.0)
    n_nodes = coords.shape[0]

    # Material: E=1000, nu=0.3 → Lame parameters
    E_mod, nu = 1000.0, 0.3
    lam = E_mod * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E_mod / (2 * (1 + nu))

    # BC: fix left face (x=0)
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    # Load: small downward force on right-top-front corner
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
    right_top = np.where(
        (np.abs(coords[:, 0] - 4.0) < 1e-12)
        & (np.abs(coords[:, 1] - 2.0) < 1e-12)
        & (np.abs(coords[:, 2] - 1.0) < 1e-12)
    )[0]
    f_ext[right_top[0], 2] = -10.0

    return {
        "coords": coords,
        "conn": conn,
        "lam": lam,
        "mu": mu,
        "bc_mask": bc_mask,
        "f_ext": f_ext,
        "n_nodes": n_nodes,
    }


# ============================================================================
# P3-T1: newton_solve import/smoke
# ============================================================================


class TestNewtonSolveImport:
    """Tests for Task P3-T1: newton_solve is importable with correct interface."""

    def test_import_newton_solve(self):
        """newton_solve is importable from mechdsl.solver."""
        assert callable(newton_solve)

    def test_newton_config_defaults(self):
        """NewtonConfig has sensible defaults."""
        c = NewtonConfig()
        assert c.tol == 1e-8
        assert c.max_iter == 50
        assert c.cg_tol == 1e-10
        assert c.cg_max_iter == 2000

    def test_newton_result_fields(self):
        """NewtonResult has converged, n_iterations, residual_history fields."""
        r = NewtonResult(converged=True, n_iterations=1, residual_history=[1.0, 0.01])
        assert r.converged is True
        assert r.n_iterations == 1
        assert r.residual_history == [1.0, 0.01]


# ============================================================================
# P3-T2: Newton driver unit tests
# ============================================================================


class TestNewtonSolveUnit:
    """Tests for Task P3-T2: Newton driver unit tests."""

    def test_elastic_cantilever_converges(self, elastic_setup: dict):
        """Elastic cantilever converges via newton_solve with reference callbacks.

        This is a nonlinear problem (large displacement, SVK). Newton should
        converge within a reasonable number of iterations (< 20).
        """
        s = elastic_setup
        u = np.zeros((s["n_nodes"], 3), dtype=np.float64)

        def assemble_residual(u_: np.ndarray) -> np.ndarray:
            f_int = ref_assemble_f_int(u_, s["coords"], s["conn"], s["lam"], s["mu"])
            return s["f_ext"] - f_int

        def tangent_mv(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            return _raw_global_matvec(u_, v, s["coords"], s["conn"], s["lam"], s["mu"])

        result = newton_solve(
            assemble_residual=assemble_residual,
            tangent_matvec=tangent_mv,
            u=u,
            bc_mask=s["bc_mask"],
        )

        assert result.converged
        assert result.n_iterations < 20
        # Residual should decrease monotonically (at least eventually)
        assert result.residual_history[-1] < result.residual_history[0]

    def test_divergence_returns_not_converged(self):
        """Divergent system returns NewtonResult(converged=False)."""
        n = 4
        u = np.zeros((n, 3), dtype=np.float64)
        bc_mask = np.zeros((n, 3), dtype=bool)
        bc_mask[0, :] = True

        # Residual that grows each call (divergent)
        call_count = [0]

        def divergent_residual(u_: np.ndarray) -> np.ndarray:
            call_count[0] += 1
            return np.full_like(u_, call_count[0] * 1e6)

        def identity_matvec(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            return v.copy()

        result = newton_solve(
            assemble_residual=divergent_residual,
            tangent_matvec=identity_matvec,
            u=u,
            bc_mask=bc_mask,
            config=NewtonConfig(max_iter=5, tol=1e-8),
        )

        assert not result.converged
        assert result.n_iterations == 5

    def test_dirichlet_dofs_remain_zero(self, elastic_setup: dict):
        """Constrained DOFs are exactly zero after solve."""
        s = elastic_setup
        u = np.zeros((s["n_nodes"], 3), dtype=np.float64)

        def assemble_residual(u_: np.ndarray) -> np.ndarray:
            f_int = ref_assemble_f_int(u_, s["coords"], s["conn"], s["lam"], s["mu"])
            return s["f_ext"] - f_int

        def tangent_mv(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            return _raw_global_matvec(u_, v, s["coords"], s["conn"], s["lam"], s["mu"])

        newton_solve(
            assemble_residual=assemble_residual,
            tangent_matvec=tangent_mv,
            u=u,
            bc_mask=s["bc_mask"],
        )

        # Constrained DOFs must be exactly zero
        assert np.all(u[s["bc_mask"]] == 0.0)

    def test_history_commit_on_convergence(self, elastic_setup: dict):
        """history.commit() called when Newton converges."""
        s = elastic_setup
        u = np.zeros((s["n_nodes"], 3), dtype=np.float64)
        history = MagicMock(spec=HistoryFields)

        def assemble_residual(u_: np.ndarray) -> np.ndarray:
            f_int = ref_assemble_f_int(u_, s["coords"], s["conn"], s["lam"], s["mu"])
            return s["f_ext"] - f_int

        def tangent_mv(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            return _raw_global_matvec(u_, v, s["coords"], s["conn"], s["lam"], s["mu"])

        result = newton_solve(
            assemble_residual=assemble_residual,
            tangent_matvec=tangent_mv,
            u=u,
            bc_mask=s["bc_mask"],
            history=history,
        )

        assert result.converged
        history.commit.assert_called_once()
        history.rollback.assert_not_called()

    def test_history_rollback_on_failure(self):
        """history.rollback() called when Newton fails to converge."""
        n = 4
        u = np.zeros((n, 3), dtype=np.float64)
        bc_mask = np.zeros((n, 3), dtype=bool)
        bc_mask[0, :] = True
        history = MagicMock(spec=HistoryFields)

        call_count = [0]

        def divergent_residual(u_: np.ndarray) -> np.ndarray:
            call_count[0] += 1
            return np.full_like(u_, call_count[0] * 1e6)

        def identity_matvec(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            return v.copy()

        result = newton_solve(
            assemble_residual=divergent_residual,
            tangent_matvec=identity_matvec,
            u=u,
            bc_mask=bc_mask,
            config=NewtonConfig(max_iter=3),
            history=history,
        )

        assert not result.converged
        history.rollback.assert_called_once()
        history.commit.assert_not_called()


# ============================================================================
# P3-T3: Newton + load_stepping integration test
# ============================================================================


class TestNewtonLoadSteppingIntegration:
    """Tests for Task P3-T3: Newton + load_stepping vs reference solver."""

    def test_plastic_cantilever_matches_reference(self):
        """newton_solve with uniform load stepping matches ref_hex8_plastic output.

        Uses the same 2x1x1 plastic cantilever setup as test_ref_plastic.py.
        Runs uniform load stepping with newton_solve and compares final
        displacement against solve_plastic.
        """
        from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
        from tests.ref.ref_hex8_plastic import (
            HistoryFields as RefHistoryFields,
        )
        from tests.ref.ref_hex8_plastic import (
            assemble_internal_force_plastic,
            element_tangent_matvec_plastic,
            solve_plastic,
        )

        # Same setup as test_ref_plastic::TestNewtonConvergence
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]

        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 2.0) < 1e-12)[0]
        for nd in right_nodes:
            f_ext[nd, 0] = 50.0

        mat = J2PowerLawMaterial(E=1000.0, nu=0.3, sigma_y0=30.0, K=100.0, n=1.0)
        n_steps = 10

        # --- Run reference solver ---
        u_ref, _history_ref, _residuals_ref = solve_plastic(
            coords, conn, mat, bc_mask, bc_values, f_ext, n_steps=n_steps
        )

        # --- Run newton_solve with uniform load stepping ---
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        history = RefHistoryFields(n_elem)

        def _raw_plastic_matvec(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            """Raw global tangent matvec WITHOUT BC enforcement."""
            n = coords.shape[0]
            Kv = np.zeros((n, 3), dtype=np.float64)
            for e in range(conn.shape[0]):
                nodes = conn[e]
                Kv_e = element_tangent_matvec_plastic(
                    u_[nodes], coords[nodes], v[nodes], mat, history.alpha_old[e]
                )
                for a in range(8):
                    Kv[nodes[a]] += Kv_e[a]
            return Kv

        for step in range(1, n_steps + 1):
            load_fraction = step / n_steps
            f_ext_step = load_fraction * f_ext

            def assemble_residual(u_: np.ndarray, _f=f_ext_step) -> np.ndarray:
                f_int = assemble_internal_force_plastic(u_, coords, conn, mat, history)
                return _f - f_int

            result = newton_solve(
                assemble_residual=assemble_residual,
                tangent_matvec=_raw_plastic_matvec,
                u=u,
                bc_mask=bc_mask,
                history=history,
            )
            assert result.converged, (
                f"Newton failed at step {step}/{n_steps}: "
                f"iters={result.n_iterations}, "
                f"final ||R||={result.residual_history[-1]:.3e}"
            )

        # Compare final displacement
        max_diff = float(np.max(np.abs(u - u_ref)))
        assert max_diff < 1e-10, f"Displacement mismatch: max |u - u_ref| = {max_diff:.3e}"

    def test_load_stepping_converges(self):
        """Adaptive load stepping converges for plastic problem."""
        from mechdsl.solver import LoadSteppingConfig, adaptive_load_stepping
        from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
        from tests.ref.ref_hex8_plastic import (
            HistoryFields as RefHistoryFields,
        )
        from tests.ref.ref_hex8_plastic import (
            assemble_internal_force_plastic,
            element_tangent_matvec_plastic,
        )

        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]

        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 2.0) < 1e-12)[0]
        for nd in right_nodes:
            f_ext[nd, 0] = 50.0

        mat = J2PowerLawMaterial(E=1000.0, nu=0.3, sigma_y0=30.0, K=100.0, n=1.0)

        u = np.zeros((n_nodes, 3), dtype=np.float64)
        history = RefHistoryFields(n_elem)

        def _raw_plastic_matvec(u_: np.ndarray, v: np.ndarray) -> np.ndarray:
            n = coords.shape[0]
            Kv = np.zeros((n, 3), dtype=np.float64)
            for e in range(conn.shape[0]):
                nodes = conn[e]
                Kv_e = element_tangent_matvec_plastic(
                    u_[nodes], coords[nodes], v[nodes], mat, history.alpha_old[e]
                )
                for a in range(8):
                    Kv[nodes[a]] += Kv_e[a]
            return Kv

        def newton_solve_fn(load_factor: float) -> tuple[bool, int, list[float]]:
            f_ext_step = load_factor * f_ext

            def assemble_residual(u_: np.ndarray) -> np.ndarray:
                f_int = assemble_internal_force_plastic(u_, coords, conn, mat, history)
                return f_ext_step - f_int

            result = newton_solve(
                assemble_residual=assemble_residual,
                tangent_matvec=_raw_plastic_matvec,
                u=u,
                bc_mask=bc_mask,
                history=history,
            )
            return result.converged, result.n_iterations, result.residual_history

        ls_result = adaptive_load_stepping(
            newton_solve_fn,
            LoadSteppingConfig(initial_step_size=0.2, max_step_size=0.5),
        )

        assert ls_result.converged
        assert ls_result.n_total_steps > 0
        assert ls_result.final_load_factor >= 1.0
