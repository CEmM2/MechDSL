r"""Tests for Task P2-2 (PlanJune14 Phase 2).

`% type A callable` → matrix-free operator seam (11-ALGO2CODE §8.3): an operator
`A` declared ``callable`` lowers ``A · p`` to an in-place operator call
``A(out, p)`` (the ti_runtime ``apply_A(out, x)`` contract) instead of a dense
``_matvec`` over a stored matrix field.

Acceptance criteria covered:
  AC-1  ``A:callable`` / ``% type A callable`` infers A as ``VarType.CALLABLE``
        and types ``A · p`` as a (matvec) VECTOR result, not a scalar multiply.
  AC-2  ``A · p`` lowers to ``A(out, p)`` and emits NO dense ``_matvec(A, …)``
        (and no ``def _matvec`` kernel) in either runtime mode.
  AC-3  Numeric parity — a generated matrix-free PCG (callable A, ti_runtime
        primitives) solves an injected SPD system to the same answer as
        ``numpy.linalg.solve`` / the PJ-1 spike ``pcg`` body (tol < 1e-9).
  AC-4  Issue #307 suite stays green — the matrix-``A`` codegen path is byte
        stable (verified here; the full suites run in CI / Gate C).

Convention notes (mirrors the ti_runtime seam + the existing generated driver):
  - Operator: the seam contract is ``apply_A(out, x)`` — out FIRST. The generated
    callable matvec emits ``A(out, p)`` accordingly.
  - Preconditioner: the existing generated driver applies ``M_inv(in, out)`` —
    out LAST (the established ``M^{-1}(r)`` callable convention, matching
    ``test_pcg_transpiler_parity.py``). The parity test wires both accordingly.
"""

# NOTE: no ``from __future__ import annotations`` — the parity test defines a
# nested ``@ti.kernel`` whose ``ti.template()`` annotations Taichi must evaluate
# eagerly. PEP 563 would stringify them and break the JIT (the PJ-0/PJ-1
# finding; the spike module omits the future-import for the same reason).

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

# Canonical PCG box with a *callable* operator A (matrix-free seam). Identical to
# the matrix-A conftest PCG except for ``A:callable`` in the % args line.
_CALLABLE_PCG_LATEX = r"""
% algorithm pcg
% backend taichi
% args A:callable, b:vector, x:vector, M_inv:callable, tol:scalar, maxiter:scalar

% type r vector
% type z vector
% type p vector
% type q vector
% type rho scalar
% type alpha scalar
% type beta scalar

\begin{algorithmic}
\State $r = b - A \cdot x$                     % vector
\State $z = M^{-1}(r)$                         % vector
\State $p = z$                                  % vector
\State $\rho = r^\top z$                        % scalar
\For{$k = 0, 1, \ldots, \text{maxiter}$}
    \State $q = A \cdot p$                      % vector
    \State $\alpha = \frac{\rho}{p^\top q}$     % scalar
    \State $x = x + \alpha \, p$                % vector
    \State $r = r - \alpha \, q$                % vector
    \If{$\|r\| < \text{tol}$}
        \Return $x, k$
    \EndIf
    \State $z = M^{-1}(r)$                      % vector
    \State $\rho_{\text{new}} = r^\top z$        % scalar
    \State $\beta = \frac{\rho_{\text{new}}}{\rho}$
    \State $p = z + \beta \, p$                  % vector
    \State $\rho = \rho_{\text{new}}$
\EndFor
\Return $x, \text{maxiter}$
\end{algorithmic}
"""

# A minimal single-statement box: declare A callable via `% type` (not % args)
# and apply it once. Exercises the `% type A callable` directive path directly.
_TYPE_DIRECTIVE_CALLABLE = r"""
% algorithm apply_op
% backend taichi
% args b:vector, x:vector

% type A callable
% type q vector

\begin{algorithmic}
\State $q = A \cdot x$                          % vector
\Return $q$
\end{algorithmic}
"""


def _import_generated(source: str, name: str):
    """Write generated Taichi source to a real ``.py`` file and import it.

    Taichi needs ``inspect.getsource`` on the driver, so the code must live in a
    real module file (not ``exec``'d) — the
    ``mechdsl-core/tests/_e2e_helpers._import_generated_module`` pattern.
    """
    tmp = Path(tempfile.mkdtemp())
    path = tmp / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestTaskP2_2:
    """Tests for Task P2-2: matrix-free operator seam. AC covered: 1-3 (+ #307 regression)."""

    @pytest.mark.unit
    def test_type_a_callable_parses_to_callable(self):
        """AC-1: `% type A callable` / `A:callable` → CALLABLE, and `A · p` types VECTOR.

        Both directive forms must put A into the type system as CALLABLE, and
        type inference must resolve ``A · p`` to a (matvec) VECTOR result — not
        fall through to a scalar multiply.
        """
        from algo2code.algo_parser import parse_algorithm
        from algo2code.ast_nodes import Assign, BinOp, Var, VarType
        from algo2code.type_inference import infer_types

        # Form (a): `% args A:callable`
        algo_args = parse_algorithm(_CALLABLE_PCG_LATEX)
        assert ("A", VarType.CALLABLE) in algo_args.args, (
            f"`A:callable` in % args must parse to CALLABLE; got {algo_args.args}"
        )

        # Form (b): `% type A callable`
        algo_type = parse_algorithm(_TYPE_DIRECTIVE_CALLABLE)
        assert algo_type.type_annotations.get("A") == VarType.CALLABLE, (
            "`% type A callable` must register A as CALLABLE; got "
            f"{algo_type.type_annotations.get('A')!r}"
        )

        # Inference: `A · x` must become a matvec producing a VECTOR.
        infer_types(algo_type)
        assign = algo_type.body[0]
        assert isinstance(assign, Assign)
        value = assign.value
        assert isinstance(value, BinOp)
        assert value.op == "matvec", (
            f"callable A applied to a vector must resolve to op='matvec'; got {value.op!r}"
        )
        assert value.inferred_type == VarType.VECTOR, (
            f"`A · x` (callable A) must be VECTOR-typed; got {value.inferred_type}"
        )
        assert isinstance(value.left, Var) and value.left.inferred_type == VarType.CALLABLE

    @pytest.mark.unit
    def test_matvec_lowers_to_callable_apply(self):
        """AC-2: `A · p` → in-place `A(out, p)`; NO dense `_matvec(A, …)` or kernel def.

        Checked in both runtime modes. The matrix-free callable operator must
        never request or call the dense ``_matvec`` template.
        """
        from algo2code import transpile

        for runtime in ("inline", "ti_runtime"):
            code = transpile(_CALLABLE_PCG_LATEX, backend="taichi", runtime=runtime)

            assert "def _matvec(" not in code, (
                f"[{runtime}] callable-A PCG must NOT define the dense _matvec kernel:\n{code}"
            )
            assert "_matvec(" not in code, (
                f"[{runtime}] callable-A PCG must NOT call _matvec:\n{code}"
            )
            # Both `A · x` (in residual) and `A · p` (in the loop) lower to
            # in-place operator calls `A(out, …)`.
            assert "A(q, p)" in code, (
                f"[{runtime}] `q = A · p` must lower to in-place `A(q, p)`:\n{code}"
            )
            a_calls = [ln.strip() for ln in code.splitlines() if ln.strip().startswith("A(")]
            assert len(a_calls) == 2, (
                f"[{runtime}] expected two in-place A(out, x) operator calls; got {a_calls}"
            )

    @pytest.mark.unit
    def test_matrix_mode_a_unchanged(self):
        """AC-4 (structural): matrix-`A` PCG still emits the dense _matvec — backward compatible."""
        from algo2code import transpile

        matrix_pcg = _CALLABLE_PCG_LATEX.replace("A:callable", "A:matrix")
        code = transpile(matrix_pcg, backend="taichi", runtime="inline")
        assert "def _matvec(" in code, "matrix-A inline PCG must still define _matvec"
        assert "_matvec(" in code, "matrix-A inline PCG must still call _matvec"

    @pytest.mark.unit
    def test_matrix_operator_rejected_in_runtime_mode(self):
        """Guard: ``runtime='ti_runtime'`` with a matrix (non-callable) operator fails loud.

        A matrix-typed ``A`` lowers to a dense scalar-indexed ``_matvec``,
        incompatible with the ``ti.Vector.field`` layout and ti_runtime
        ``dot``/``norm2`` reductions runtime mode uses — so the backend must raise
        ``UnsupportedConstructError`` rather than silently emit non-runnable code.
        Inline mode (the legacy dense path) is unaffected.
        """
        from algo2code import UnsupportedConstructError, transpile

        matrix_pcg = _CALLABLE_PCG_LATEX.replace("A:callable", "A:matrix")
        # inline mode is fine — the dense matvec is the supported legacy path...
        transpile(matrix_pcg, backend="taichi", runtime="inline")
        # ...but runtime mode must reject the matrix operator loudly.
        with pytest.raises(UnsupportedConstructError, match="callable operator"):
            transpile(matrix_pcg, backend="taichi", runtime="ti_runtime")

    @pytest.mark.slow
    @pytest.mark.integration
    def test_generated_matrix_free_pcg_parity(self):
        """AC-3: generated matrix-free PCG solves an injected SPD system to spike/NumPy parity.

        Transpile the callable-A PCG in ``ti_runtime`` mode, write it to a real
        ``.py`` file, import it under real Taichi, and drive it with
        ``ti.Vector.field`` DOF vectors and an injected block-SPD operator (the
        ``test_seams.py`` operator). Assert the generated solver's answer matches
        ``numpy.linalg.solve`` and the PJ-1 spike ``pcg`` to < 1e-9.
        """
        ti = pytest.importorskip("taichi")
        import numpy as np

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        from ti_runtime import vector_ops as vops
        from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

        # Block-diagonal SPD operator (mirrors ti-runtime/tests/test_seams.py):
        # out[i] = M @ x[i] with a fixed SPD 3x3 M, over ti.Vector.field DOFs.
        m_np = np.array([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]])

        @ti.kernel
        def apply_M(out: ti.template(), x: ti.template()):
            mat = ti.Matrix([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]], dt=ti.f64)
            for i in out:
                out[i] = mat @ x[i]

        # ── Generate + import the matrix-free PCG (ti_runtime mode) ──────────
        from algo2code import transpile

        code = transpile(_CALLABLE_PCG_LATEX, backend="taichi", runtime="ti_runtime")
        code = code.replace("arch=ti.gpu", "arch=ti.cpu")
        # Drop the generated module-level ti.init — Taichi is already initialised
        # by this test, and re-init would drop the fields allocated below.
        code = "\n".join(ln for ln in code.splitlines() if not ln.startswith("ti.init"))
        gen = _import_generated(code, "gen_pcg_p2_2")

        # ── Build the SPD system over vector fields ──────────────────────────
        rng = np.random.default_rng(7)
        n = 5
        b_np = rng.standard_normal((n, 3))

        def _vfield(vals: np.ndarray):
            vals = np.ascontiguousarray(vals, dtype=np.float64)
            f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
            f.from_numpy(vals)
            return f

        b = _vfield(b_np)
        x = ti.Vector.field(3, ti.f64, shape=n)  # zero initial guess

        # ── Operator seam: A(out, x) ⇒ apply_A; preconditioner M_inv(in, out) ─
        ctx = LinearSolveContext().set_operator(apply_M)
        ctx.set_preconditioner(IdentityPreconditioner())

        def operator_A(out, vec):
            ctx.apply_A(out, vec)  # apply_A(out, x): out FIRST (seam contract)

        def precond_M_inv(r_in, z_out):
            ctx.apply_preconditioner(z_out, r_in)  # M^{-1}(r) → z, out LAST in the call

        x_out, _k = gen.pcg(operator_A, b, x, precond_M_inv, 1e-12, 200)
        x_gen = x_out.to_numpy()

        # ── Oracles: per-node M^{-1} b, and the PJ-1 spike pcg body ──────────
        expected = np.linalg.solve(m_np, b_np.T).T
        np.testing.assert_allclose(x_gen, expected, atol=1e-9, rtol=0)

        # Spike-pcg parity: drive the hand-written PJ-1 PCG body over the SAME
        # injected operator and fields; the generated solver must match it.
        spike = _import_spike_pcg()
        x_spike_field = ti.Vector.field(3, ti.f64, shape=n)
        ws = spike._PCGWorkspace.alloc(n)
        spike_ctx = LinearSolveContext().set_operator(apply_M)
        spike_ctx.set_preconditioner(IdentityPreconditioner())
        spike.pcg(spike_ctx, ws, b, x_spike_field, 1e-12, 200)
        np.testing.assert_allclose(x_gen, x_spike_field.to_numpy(), atol=1e-9, rtol=0)

        # Residual sanity: ||A x - b|| ≈ 0 on device (no NumPy in the solve path).
        ax = ti.Vector.field(3, ti.f64, shape=n)
        apply_M(ax, x_out)
        vops.axpy(ax, -1.0, b)
        assert vops.norm2(ax) < 1e-9


def _import_spike_pcg():
    """Import the PJ-1 spike module (the hand-written PCG parity oracle).

    The spike lives in ``mechdsl-core/tests/spike/svk_hex8_taichi.py`` and
    imports ``numpy``/``taichi`` eagerly — fine here, since the parity test
    already requires Taichi. Loaded by absolute file path so the cross-package
    location is robust to the test's working directory.
    """
    spike_path = (
        Path(__file__).resolve().parents[3]
        / "mechdsl-core"
        / "tests"
        / "spike"
        / "svk_hex8_taichi.py"
    )
    spec = importlib.util.spec_from_file_location("svk_hex8_taichi_p2_2", spike_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod
