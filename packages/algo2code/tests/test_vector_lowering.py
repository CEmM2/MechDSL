"""W2 (issue #307, F1) — SSA lowering of compound vector expressions.

A nested vector RHS such as ``r + beta*(p - omega*v)`` must lower to a chain of
single-kernel-call operations writing temporary fields — never to Python
``ti.field`` arithmetic, which is not runnable.

Two layers of tests:
  * fast structural tests — the emitted code is valid Python with no leftover
    field arithmetic, and uses the expected number of scratch fields;
  * ``slow``/``e2e`` numeric tests — the emitted code is compiled and run by
    *real Taichi* (written to a file and imported, because ``@ti.kernel`` needs
    ``inspect.getsource``) and its result is compared to a NumPy reference.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from algo2code import transpile

# A BiCGSTAB-shaped block: scalars are defined first (so they type as scalar),
# then two genuinely-nested compound vector updates.
BICG_UPDATES = r"""% algorithm bicg_updates
% backend taichi
% args A:matrix, b:vector, x:vector, r:vector, p:vector, v:vector, s:vector
\begin{algorithmic}
\State $\alpha = r^\top s$
\State $\omega = r^\top v$
\State $\beta = r^\top p$
\State $p = r + \beta \cdot (p - \omega \cdot v)$
\State $x = x + \alpha \cdot p + \omega \cdot s$
\end{algorithmic}"""


# ── Fast structural tests ────────────────────────────────────────────────────


def test_compound_rhs_emits_only_kernel_calls():
    code = transpile(BICG_UPDATES)
    ast.parse(code)  # must be valid Python
    # No leftover Python field arithmetic (the F1 bug signature).
    for bad in ("(p - ", "(omega * v)", "(alpha * p)", "(x + "):
        assert bad not in code, f"field arithmetic leaked into output: {bad!r}"


def test_compound_rhs_reuses_a_single_temp():
    """The two updates need only one scratch field, reused across statements."""
    code = transpile(BICG_UPDATES)
    assert "_tmp0 = ti.field" in code
    assert "_tmp1" not in code  # peak simultaneous temps is 1


# ── Real-Taichi numeric tests ────────────────────────────────────────────────


def _run_taichi(ti, code: str, entry: str, builder):
    """Compile generated code with real Taichi and run its entry function.

    The code is written to a real ``.py`` file and imported, because Taichi's
    ``@ti.kernel`` AST-transforms the kernel body via ``inspect.getsource`` —
    which fails for an ``exec``'d string. ``builder(make_field)`` returns the
    positional argument list for ``entry``.
    """
    code = code.replace("arch=ti.gpu", "arch=ti.cpu")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / f"gen_{entry}.py"
        path.write_text(code)
        spec = importlib.util.spec_from_file_location(f"gen_{entry}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)  # runs ti.init(arch=cpu)

            def make_field(vals):
                f = ti.field(ti.f64, shape=len(vals))
                f.from_numpy(np.ascontiguousarray(vals, dtype=np.float64))
                return f

            args = builder(make_field)
            getattr(mod, entry)(*args)
            return args
        finally:
            sys.modules.pop(spec.name, None)


@pytest.mark.slow
@pytest.mark.e2e
def test_axpy3_runs_under_taichi_and_matches_numpy():
    """w = a*x + b*y + c*z compiled+run by Taichi equals the NumPy result."""
    ti = pytest.importorskip("taichi")
    src = r"""% algorithm axpy3
% backend taichi
% args a:scalar, b:scalar, c:scalar, x:vector, y:vector, z:vector, w:vector
\begin{algorithmic}
\State $w = a \cdot x + b \cdot y + c \cdot z$
\end{algorithmic}"""

    rng = np.random.default_rng(0)
    xv, yv, zv = (rng.standard_normal(5) for _ in range(3))
    a, b, c = 2.0, -3.0, 0.5

    captured = {}

    def build(make_field):
        w = make_field(np.zeros(5))
        captured["w"] = w
        return [a, b, c, make_field(xv), make_field(yv), make_field(zv), w]

    _run_taichi(ti, transpile(src), "axpy3", build)
    np.testing.assert_allclose(
        captured["w"].to_numpy(), a * xv + b * yv + c * zv, rtol=1e-12, atol=1e-12
    )


@pytest.mark.slow
@pytest.mark.e2e
def test_nested_bicgstab_update_runs_under_taichi():
    """The genuinely-nested p = r + beta*(p - omega*v) update runs correctly."""
    ti = pytest.importorskip("taichi")
    src = r"""% algorithm pupdate
% backend taichi
% args beta:scalar, omega:scalar, r:vector, p:vector, v:vector
\begin{algorithmic}
\State $p = r + \beta \cdot (p - \omega \cdot v)$
\end{algorithmic}"""

    rng = np.random.default_rng(1)
    rv, pv, vv = (rng.standard_normal(6) for _ in range(3))
    beta, omega = 0.7, 1.3

    captured = {}

    def build(make_field):
        p = make_field(pv)
        captured["p"] = p
        return [beta, omega, make_field(rv), p, make_field(vv)]

    _run_taichi(ti, transpile(src), "pupdate", build)
    np.testing.assert_allclose(
        captured["p"].to_numpy(), rv + beta * (pv - omega * vv), rtol=1e-12, atol=1e-12
    )
