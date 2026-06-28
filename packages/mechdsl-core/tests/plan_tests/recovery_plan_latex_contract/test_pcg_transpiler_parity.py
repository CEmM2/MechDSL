"""Issue #307 W4 — decision gate: hand-written PCG vs transpiler-generated PCG.

The hand-written ``Algo2CodePCGSolver`` is a line-by-line translation of the
canonical PCG LaTeX. Now that ``algo2code.transpile`` produces a runnable Taichi
PCG (issue #307 F1/F2), this test compares the two numerically to decide whether
the hand-translation can be retired.

Outcome (pinned here):
  * **Converged path** — identical to machine precision (same iterations, same x).
  * **Max-iter-exhaust path** — also identical. The generated
    ``\\For{$k = 1, ..., maxiter$}`` now lowers to the inclusive
    ``range(1, maxiter + 1)`` (issue #307 W6 for-loop fix), matching the
    hand-written ``range(1, max_iter + 1)``. With both paths bit-identical, the
    hand-translation can be retired.
"""

from __future__ import annotations

import importlib.util
import sys
import warnings

import numpy as np
import pytest

pytestmark = [pytest.mark.slow, pytest.mark.e2e]


def _matvec(a_mat: np.ndarray):
    return lambda v: a_mat @ v


def _spd_system(seed: int = 99, n: int = 10):
    rng = np.random.default_rng(seed)
    b_mat = rng.standard_normal((n, n))
    a_mat = b_mat.T @ b_mat + n * np.eye(n)
    rhs = rng.standard_normal(n)
    return a_mat, rhs, 1.0 / np.diag(a_mat)


def _load_generated_pcg(ti, tmp_path):
    from algo2code import transpile
    from algo2code.library.pcg import PCG_ALGORITHM_LATEX

    code = transpile(PCG_ALGORITHM_LATEX).replace("arch=ti.gpu", "arch=ti.cpu")
    code = "\n".join(line for line in code.splitlines() if not line.startswith("ti.init"))
    # pytest's tmp_path is managed (auto-cleaned) yet persists for the whole test,
    # so the generated module's source file is still on disk when Taichi runs
    # inspect.getsource during JIT.
    path = tmp_path / "gen_pcg.py"
    path.write_text(code)
    spec = importlib.util.spec_from_file_location("gen_pcg_parity", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_generated(ti, gen, a_mat, rhs, x0, dinv, tol, maxiter):
    n = len(rhs)
    a_field = ti.field(ti.f64, shape=(n, n))
    a_field.from_numpy(np.ascontiguousarray(a_mat))
    b_field = ti.field(ti.f64, shape=n)
    b_field.from_numpy(np.ascontiguousarray(rhs))
    x_field = ti.field(ti.f64, shape=n)
    x_field.from_numpy(np.ascontiguousarray(x0))

    # The generated driver calls apply_M_inv(r, z) as a plain in-place callback,
    # so a pure-Python function over the fields suffices (no @ti.kernel — which
    # would fail source introspection when nested under pytest).
    def apply_m_inv(r_in, z_out):
        z_out.from_numpy(np.ascontiguousarray(dinv * r_in.to_numpy()))

    x, k, r_norm = gen.pcg(a_field, b_field, x_field, apply_m_inv, tol, maxiter)
    return x.to_numpy(), int(k), float(r_norm)


def test_converged_path_is_identical_to_machine_precision(tmp_path):
    """On a system that converges before maxiter, the two PCGs agree exactly."""
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)
    from mechdsl.solver.import_adapter import Algo2CodePCGSolver

    a_mat, rhs, dinv = _spd_system()
    x0 = np.zeros(len(rhs))

    def jac(v):
        return dinv * v

    gen = _load_generated_pcg(ti, tmp_path)
    x_hand, k_hand, _ = Algo2CodePCGSolver(precond_fn=jac).solve(
        _matvec(a_mat), rhs, x0.copy(), 1e-10, 200
    )
    x_gen, k_gen, _ = _run_generated(ti, gen, a_mat, rhs, x0, dinv, 1e-10, 200)

    assert k_hand == k_gen
    np.testing.assert_allclose(x_gen, x_hand, atol=1e-10, rtol=0)


def test_maxiter_exhaust_path_matches(tmp_path):
    """When maxiter is exhausted the two PCGs match.

    Previously diverged because the generated ``\\For{$k = 1, ..., maxiter$}``
    lowered to exclusive ``range(1, maxiter)`` (one fewer iteration). The
    for-loop range lowering now emits the inclusive ``range(1, maxiter + 1)``,
    so the two are bit-identical on this path too — clearing the way to retire
    the hand-translation.
    """
    ti = pytest.importorskip("taichi")
    ti.init(arch=ti.cpu, default_fp=ti.f64)
    from mechdsl.solver.import_adapter import Algo2CodePCGSolver

    a_mat, rhs, dinv = _spd_system()
    x0 = np.zeros(len(rhs))

    def jac(v):
        return dinv * v

    gen = _load_generated_pcg(ti, tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        x_hand, _, _ = Algo2CodePCGSolver(precond_fn=jac).solve(
            _matvec(a_mat), rhs, x0.copy(), 1e-10, 3
        )
        x_gen, _, _ = _run_generated(ti, gen, a_mat, rhs, x0, dinv, 1e-10, 3)

    np.testing.assert_allclose(x_gen, x_hand, atol=1e-10, rtol=0)
