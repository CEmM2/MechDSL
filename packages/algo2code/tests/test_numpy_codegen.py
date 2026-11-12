"""NumPy backend: Taichi-free code generated from the same LaTeX sources.

The NumPy backend exists so algorithms transpiled from LaTeX run on a lean
install (no Taichi). These tests pin three properties:

* the emitted module never mentions Taichi and is valid Python;
* for scalar algorithms (the J2 return maps) the function body is identical
  to the Taichi backend's, so results are bit-identical between backends;
* vector algorithms (PCG, compound vector updates) run on NumPy arrays with
  the same in-place semantics as the Taichi field model.
"""

from __future__ import annotations

import ast

import pytest

from algo2code import transpile
from algo2code.library import algorithm_source

np = pytest.importorskip("numpy")

J2_SOURCES = (
    "radial_return_j2.tex",
    "radial_return_j2_kinematic.tex",
    "radial_return_j2_mixed.tex",
)


def _load(code: str, entry: str):
    ns: dict[str, object] = {}
    exec(compile(code, f"<numpy:{entry}>", "exec"), ns)
    return ns[entry]


def _body(code: str) -> list[str]:
    """Lines from the ``def`` onward, minus the backend docstring line."""
    lines = code.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("def "))
    return [line for line in lines[start:] if "Backend:" not in line]


@pytest.mark.unit
@pytest.mark.parametrize("name", J2_SOURCES)
def test_numpy_output_is_taichi_free_python(name: str) -> None:
    code = transpile(algorithm_source(name), backend="numpy")
    ast.parse(code)
    assert "taichi" not in code
    assert "ti." not in code
    assert code.startswith("import numpy as np")


@pytest.mark.unit
@pytest.mark.parametrize("name", J2_SOURCES)
def test_scalar_body_matches_taichi_backend(name: str) -> None:
    src = algorithm_source(name)
    assert _body(transpile(src, backend="numpy")) == _body(transpile(src, backend="taichi"))


@pytest.mark.unit
def test_radial_return_j2_numpy_converges_to_consistency() -> None:
    f = _load(
        transpile(algorithm_source("radial_return_j2.tex"), backend="numpy"), "radial_return_j2"
    )
    mu, K, n, sigy0 = 76923.0, 500.0, 0.5, 250.0
    plastic, alpha_new, dl = f(
        sigma_eq=600.0, alpha=0.0, mu=mu, K=K, n=n, sigy0=sigy0, tol=1e-12, max_iter=50
    )
    assert plastic == 1
    assert dl > 0
    # Discrete consistency: sigma_eq - 3*mu*dl == sigma_y(alpha_new).
    assert 600.0 - 3 * mu * dl == pytest.approx(sigy0 + K * alpha_new**n, rel=1e-12)
    # Elastic step.
    assert f(100.0, 0.0, mu, K, n, sigy0, 1e-12, 50) == (0, 0.0, 0)


@pytest.mark.unit
def test_radial_return_kinematic_numpy_matches_closed_form() -> None:
    f = _load(
        transpile(algorithm_source("radial_return_j2_kinematic.tex"), backend="numpy"),
        "radial_return_j2_kinematic",
    )
    xi_eq, mu, H, sy = 400.0, 76923.0, 1000.0, 250.0
    plastic, dl = f(xi_eq, mu, H, sy, 1e-12, 5)
    assert plastic == 1
    assert dl == pytest.approx((xi_eq - sy) / (3 * mu + H), rel=1e-14)


@pytest.mark.unit
def test_pcg_numpy_solves_spd_system_in_place() -> None:
    f = _load(transpile(algorithm_source("pcg.tex"), backend="numpy"), "pcg")
    rng = np.random.default_rng(0)
    m = rng.standard_normal((12, 12))
    A_mat = m @ m.T + 12 * np.eye(12)
    b = rng.standard_normal(12)
    x = np.zeros(12)
    d = np.diag(A_mat).copy()

    def A(out, v):
        out[...] = A_mat @ v

    def M_inv(r, out):
        out[...] = r / d

    result = f(A, b, x, M_inv, 1e-12, 200)
    assert result[-1] == 1  # converged flag
    assert result[0] is x  # solution written into the caller's array
    np.testing.assert_allclose(x, np.linalg.solve(A_mat, b), rtol=1e-9, atol=1e-12)


@pytest.mark.unit
def test_compound_vector_update_matches_numpy_reference() -> None:
    src = r"""% algorithm bicg_updates
% args A:matrix, b:vector, x:vector, r:vector, p:vector, v:vector, s:vector
\begin{algorithmic}
\State $\alpha = r^\top s$
\State $\omega = r^\top v$
\State $\beta = r^\top p$
\State $p = r + \beta \cdot (p - \omega \cdot v)$
\State $x = x + \alpha \cdot p + \omega \cdot s$
\end{algorithmic}"""
    f = _load(transpile(src, backend="numpy"), "bicg_updates")
    rng = np.random.default_rng(1)
    A, b, x, r, p, v, s = (rng.standard_normal(5) for _ in range(7))
    A = rng.standard_normal((5, 5))
    alpha, omega, beta = r @ s, r @ v, r @ p
    p_ref = r + beta * (p - omega * v)
    x_ref = x + alpha * p_ref + omega * s
    f(A, b, x, r, p, v, s)
    np.testing.assert_allclose(p, p_ref, rtol=1e-13)
    np.testing.assert_allclose(x, x_ref, rtol=1e-13)


@pytest.mark.unit
def test_dense_matvec_and_norm() -> None:
    src = r"""% algorithm residual
% args A:matrix, b:vector, x:vector
% type r vector
\begin{algorithmic}
\State $r = b - A \cdot x$
\Return $\|r\|$
\end{algorithmic}"""
    f = _load(transpile(src, backend="numpy"), "residual")
    rng = np.random.default_rng(2)
    A, b, x = rng.standard_normal((4, 4)), rng.standard_normal(4), rng.standard_normal(4)
    assert f(A, b, x) == pytest.approx(float(np.linalg.norm(b - A @ x)), rel=1e-13)
