"""Tests for the linear solver interface contract (CGSolver / PCGSolver)."""

from __future__ import annotations

import numpy as np

from mechdsl.solver.import_adapter import (
    CGSolver,
    LinearSolverInterface,
    PCGSolver,
    ScipyCGSolver,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_matvec(A: np.ndarray):
    """Return a matvec closure for a dense matrix *A*."""

    def matvec(v: np.ndarray) -> np.ndarray:
        return A @ v

    return matvec


def _random_spd(n: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a random *n x n* symmetric positive-definite matrix."""
    B = rng.standard_normal((n, n))
    return B.T @ B + n * np.eye(n)  # shift ensures well-conditioned SPD


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Known 3x3 SPD system from the task spec.
A_3x3 = np.array(
    [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]],
    dtype=np.float64,
)
b_3x3 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
x_ref_3x3 = np.linalg.solve(A_3x3, b_3x3)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_cg_satisfies_protocol():
    """CGSolver must be structurally compatible with LinearSolverInterface."""
    solver: LinearSolverInterface = CGSolver()
    assert hasattr(solver, "solve")


def test_pcg_satisfies_protocol():
    """PCGSolver (no preconditioner) must also satisfy the protocol."""
    solver: LinearSolverInterface = PCGSolver()
    assert hasattr(solver, "solve")


# ---------------------------------------------------------------------------
# CGSolver — 3x3 system
# ---------------------------------------------------------------------------


class TestCGSolver3x3:
    """CG on the known 3x3 SPD system."""

    solver = CGSolver()
    x0 = np.zeros(3, dtype=np.float64)
    tol = 1e-10

    def test_solution_accuracy(self):
        x, _iters, _res = self.solver.solve(
            _make_matvec(A_3x3), b_3x3, self.x0, self.tol, max_iter=100
        )
        np.testing.assert_allclose(x, x_ref_3x3, atol=1e-10)

    def test_iteration_count(self):
        _x, iters, _res = self.solver.solve(
            _make_matvec(A_3x3), b_3x3, self.x0, self.tol, max_iter=100
        )
        assert iters < 20, f"CG on 3x3 system took {iters} iterations"

    def test_residual_below_tolerance(self):
        _x, _iters, res_norm = self.solver.solve(
            _make_matvec(A_3x3), b_3x3, self.x0, self.tol, max_iter=100
        )
        r0_norm = float(np.linalg.norm(b_3x3))
        assert res_norm < self.tol * r0_norm


# ---------------------------------------------------------------------------
# CGSolver — identity matrix (trivial solve)
# ---------------------------------------------------------------------------


class TestCGSolverIdentity:
    """CG with I as the system matrix should return the RHS immediately."""

    solver = CGSolver()

    def test_identity_solve(self):
        n = 5
        I_n = np.eye(n, dtype=np.float64)
        b = np.arange(1.0, n + 1, dtype=np.float64)
        x0 = np.zeros(n, dtype=np.float64)

        x, iters, res = self.solver.solve(_make_matvec(I_n), b, x0, 1e-12, 100)
        np.testing.assert_allclose(x, b, atol=1e-12)
        assert iters <= 1, "Identity system should converge in at most 1 iteration"
        assert res < 1e-12 * np.linalg.norm(b)


# ---------------------------------------------------------------------------
# CGSolver — larger random SPD system
# ---------------------------------------------------------------------------


class TestCGSolverRandom10x10:
    """CG on a random 10x10 SPD system."""

    def test_random_spd(self):
        rng = np.random.default_rng(42)
        n = 10
        A = _random_spd(n, rng)
        b = rng.standard_normal(n).astype(np.float64)
        x_ref = np.linalg.solve(A, b)

        solver = CGSolver()
        x, iters, res = solver.solve(_make_matvec(A), b, np.zeros(n), 1e-10, 200)

        np.testing.assert_allclose(x, x_ref, atol=1e-8)
        assert iters <= n + 5, f"Expected at most ~n iterations, got {iters}"
        r0_norm = float(np.linalg.norm(b))
        assert res < 1e-10 * r0_norm


# ---------------------------------------------------------------------------
# CGSolver — zero RHS (trivial)
# ---------------------------------------------------------------------------


def test_cg_zero_rhs():
    """Zero RHS should return zero solution in 0 iterations."""
    solver = CGSolver()
    n = 4
    A = np.eye(n)
    b = np.zeros(n)
    x0 = np.zeros(n)

    x, iters, res = solver.solve(_make_matvec(A), b, x0, 1e-12, 100)
    np.testing.assert_allclose(x, np.zeros(n), atol=1e-15)
    assert iters == 0
    assert res == 0.0


# ---------------------------------------------------------------------------
# PCGSolver — no preconditioner (should behave like CG)
# ---------------------------------------------------------------------------


class TestPCGSolverNoPrecond:
    """PCGSolver with precond_fn=None should give the same answer as CG."""

    def test_matches_cg(self):
        solver = PCGSolver(precond_fn=None)
        x0 = np.zeros(3, dtype=np.float64)

        x, iters, _res = solver.solve(_make_matvec(A_3x3), b_3x3, x0, 1e-10, 100)
        np.testing.assert_allclose(x, x_ref_3x3, atol=1e-10)
        assert iters < 20


# ---------------------------------------------------------------------------
# PCGSolver — Jacobi preconditioner
# ---------------------------------------------------------------------------


class TestPCGSolverJacobi:
    """PCGSolver with a diagonal (Jacobi) preconditioner."""

    def test_jacobi_precond(self):
        rng = np.random.default_rng(99)
        n = 10
        A = _random_spd(n, rng)
        b = rng.standard_normal(n).astype(np.float64)
        x_ref = np.linalg.solve(A, b)

        diag_inv = 1.0 / np.diag(A)

        def jacobi_precond(v: np.ndarray) -> np.ndarray:
            return diag_inv * v

        solver = PCGSolver(precond_fn=jacobi_precond)
        x, _iters, res = solver.solve(_make_matvec(A), b, np.zeros(n), 1e-10, 200)

        np.testing.assert_allclose(x, x_ref, atol=1e-8)
        r0_norm = float(np.linalg.norm(b))
        assert res < 1e-10 * r0_norm


# ---------------------------------------------------------------------------
# PCGSolver — zero RHS
# ---------------------------------------------------------------------------


def test_pcg_zero_rhs():
    """Zero RHS should return zero solution in 0 iterations for PCG too."""
    solver = PCGSolver()
    n = 4
    A = np.eye(n)
    b = np.zeros(n)
    x0 = np.zeros(n)

    x, iters, res = solver.solve(_make_matvec(A), b, x0, 1e-12, 100)
    np.testing.assert_allclose(x, np.zeros(n), atol=1e-15)
    assert iters == 0
    assert res == 0.0


# ---------------------------------------------------------------------------
# ScipyCGSolver
# ---------------------------------------------------------------------------


def test_scipy_cg_satisfies_protocol():
    """ScipyCGSolver must be structurally compatible with LinearSolverInterface."""
    solver: LinearSolverInterface = ScipyCGSolver()
    assert hasattr(solver, "solve")


class TestScipyCGSolver3x3:
    """ScipyCGSolver on the known 3x3 SPD system."""

    def test_solution_accuracy(self):
        solver = ScipyCGSolver()
        x, _iters, _res = solver.solve(_make_matvec(A_3x3), b_3x3, np.zeros(3), 1e-12, 100)
        np.testing.assert_allclose(x, x_ref_3x3, atol=1e-10)

    def test_residual_below_tolerance(self):
        solver = ScipyCGSolver()
        _x, _iters, res = solver.solve(_make_matvec(A_3x3), b_3x3, np.zeros(3), 1e-12, 100)
        assert res < 1e-10

    def test_converges_within_n_iterations(self):
        solver = ScipyCGSolver()
        _x, iters, _res = solver.solve(_make_matvec(A_3x3), b_3x3, np.zeros(3), 1e-12, 100)
        assert 0 < iters <= 3


class TestScipyCGSolverIdentity:
    """ScipyCGSolver on identity matrix."""

    def test_identity_solution(self):
        solver = ScipyCGSolver()
        n = 5
        A = np.eye(n)
        b = np.arange(1.0, n + 1)
        x, iters, _res = solver.solve(_make_matvec(A), b, np.zeros(n), 1e-12, 100)
        np.testing.assert_allclose(x, b, atol=1e-12)
        assert iters <= 1


class TestScipyCGSolverRandom10x10:
    """ScipyCGSolver on a random 10x10 SPD system."""

    def test_random_spd_accuracy(self):
        rng = np.random.default_rng(42)
        n = 10
        A = _random_spd(n, rng)
        b = rng.standard_normal(n)
        x_ref = np.linalg.solve(A, b)

        solver = ScipyCGSolver()
        x, iters, _res = solver.solve(_make_matvec(A), b, np.zeros(n), 1e-12, 200)
        np.testing.assert_allclose(x, x_ref, atol=1e-8)
        assert iters <= n


def test_scipy_cg_zero_rhs():
    """Zero RHS should return zero solution for ScipyCGSolver."""
    solver = ScipyCGSolver()
    n = 4
    A = np.eye(n)
    b = np.zeros(n)
    x0 = np.zeros(n)

    x, _iters, res = solver.solve(_make_matvec(A), b, x0, 1e-12, 100)
    np.testing.assert_allclose(x, np.zeros(n), atol=1e-15)
    assert res < 1e-15
