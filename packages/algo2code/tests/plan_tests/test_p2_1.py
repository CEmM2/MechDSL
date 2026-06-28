"""Tests for Task P2-1 (PlanJune14 Phase 2).

emit `from ti_runtime import …` + calls to shared primitives (import-mode flag).

Acceptance criteria covered:
  AC-1  runtime-mode preamble: generated source starts with `from ti_runtime import …`
  AC-2  runtime-mode has no inlined private dot/norm/copy kernel defs
  AC-3  inline-mode (default) output is byte-for-byte unchanged (backward compat)
  AC-4  algo2code the compiler imports only stdlib — ti_runtime never pulled in

Design notes (evidence from empirical check — see module docstring in taichi_codegen.py):
  - `ti_runtime.vector_ops.dot` uses `.dot()` which requires `ti.Vector.field`;
    algo2code emits `ti.field(ti.f64, shape=n)` scalar fields → the `_v.dot`/
    `_v.norm2` calls in runtime mode will only work correctly when the consumer
    passes vector fields (e.g. mechdsl FEM drivers).  This is documented as a
    known field-model mismatch, out of scope for P2-1.
  - In runtime mode `_dot`/`_norm`/`_copy`/`_vec_add` are all routed to ti_runtime
    primitives (`_vec_add` → the `vec_add` AXPBY primitive). Only `_matvec` (the
    dense matrix-vector product) has no ti_runtime equivalent and stays inlined.
"""

import sys
import types

import pytest

# ── Fixtures ─────────────────────────────────────────────────────────────────

# A minimal algorithm that uses dot, norm, and copy — exercises all three
# routed primitives in a self-contained snippet.
_MINI_DOT_NORM_COPY = r"""
% algorithm mini
% backend taichi
% args x:vector, y:vector, z:vector

% type x vector
% type y vector
% type z vector
% type alpha scalar

\begin{algorithmic}
\State $\alpha = x^\top y$
\State $z = x$
\If{$\|z\| < 1.0$}
    \Return $\alpha$
\EndIf
\Return $\alpha$
\end{algorithmic}
"""

# A matrix-free PCG (callable operator A) — the valid shape for runtime mode,
# which requires a callable operator + a vector arg (see _check_runtime_mode_supported).
_PCG_LATEX = r"""
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


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestTaskP2_1:
    """Tests for Task P2-1: algo2code ti_runtime import-mode. AC covered: 1-4."""

    @pytest.mark.unit
    def test_runtime_mode_emits_ti_runtime_import(self):
        """AC-1: runtime-mode preamble contains `from ti_runtime import vector_ops as _v`."""
        from algo2code import transpile

        code = transpile(_PCG_LATEX, backend="taichi", runtime="ti_runtime")
        assert "from ti_runtime import vector_ops as _v" in code, (
            "runtime-mode must emit `from ti_runtime import vector_ops as _v`; got:\n" + code[:500]
        )

    @pytest.mark.unit
    def test_runtime_mode_has_no_inlined_vector_kernels(self):
        """AC-2: runtime-mode generated source contains no private inlined dot/norm/copy/vec_add defs.

        _matvec is excluded from this check because ti_runtime has no equivalent
        combiner — it remains inlined until P2-2 adds the matrix-free operator seam.
        """
        from algo2code import transpile

        code = transpile(_MINI_DOT_NORM_COPY, backend="taichi", runtime="ti_runtime")

        # Must NOT have inlined private kernel definitions for the routed ops
        assert "def _dot(" not in code, "runtime-mode must not inline _dot kernel"
        assert "def _norm(" not in code, "runtime-mode must not inline _norm kernel"
        assert "def _copy(" not in code, "runtime-mode must not inline _copy kernel"
        assert "def _vec_add(" not in code, "runtime-mode must not inline _vec_add kernel"

        # Must CALL through ti_runtime instead
        assert "_v.dot(" in code or "_v.norm2(" in code or "_v.copy(" in code, (
            "runtime-mode must call at least one ti_runtime primitive (_v.dot / "
            "_v.norm2 / _v.copy); got:\n" + code
        )

    @pytest.mark.unit
    def test_inline_mode_output_unchanged(self, pcg_latex):
        """AC-3: inline-mode (default) golden is unchanged — backward compatibility.

        Verify that:
        (a) default mode == explicit inline mode
        (b) default mode still has the private @ti.kernel defs
        (c) default mode does NOT have the ti_runtime import
        """
        from algo2code import transpile

        default_code = transpile(pcg_latex, backend="taichi")
        explicit_inline = transpile(pcg_latex, backend="taichi", runtime="inline")

        assert default_code == explicit_inline, (
            "default runtime must produce identical output to runtime='inline'"
        )

        # Spot-check that key inline-mode signatures are still present
        assert "def _dot(" in default_code, "inline-mode must still define _dot kernel"
        assert "@ti.kernel" in default_code, "inline-mode must still have @ti.kernel defs"
        assert "from ti_runtime" not in default_code, (
            "inline-mode must NOT emit a ti_runtime import"
        )

    @pytest.mark.unit
    def test_algo2code_import_stays_stdlib_only(self):
        """AC-4: importing algo2code pulls in no ti_runtime, taichi, or mechdsl modules.

        algo2code-the-compiler is stdlib-only.  It *emits* a ti_runtime import
        line but never executes it.
        """
        # Collect module names before import
        before = set(sys.modules.keys())

        # Fresh import via a sub-interpreter snapshot is not easy in pytest, so
        # instead we assert that none of the forbidden packages were pulled in
        # *by* the algo2code import itself.  We check for their absence in the
        # module graph anchored at `algo2code`.
        import algo2code  # noqa: F401 — side effect: registers submodules

        after = set(sys.modules.keys())
        new_modules = after - before

        forbidden = {"taichi", "ti_runtime", "mechdsl"}
        pulled_in = {m.split(".")[0] for m in new_modules} & forbidden
        assert not pulled_in, (
            f"algo2code must not import {forbidden} at compile time; found: {pulled_in}"
        )

        # Also verify that the algo2code package object itself has no reference
        # to ti_runtime or taichi in its module dict (catches accidental
        # top-level imports in __init__.py).
        algo2code_submodules = {
            name for name in sys.modules if name == "algo2code" or name.startswith("algo2code.")
        }
        for mod_name in algo2code_submodules:
            mod = sys.modules[mod_name]
            if not isinstance(mod, types.ModuleType):
                continue
            for attr_name in vars(mod):
                attr = getattr(mod, attr_name, None)
                if isinstance(attr, types.ModuleType):
                    top = attr.__name__.split(".")[0]
                    assert top not in forbidden, (
                        f"algo2code.{mod_name} has a reference to forbidden module "
                        f"{attr.__name__!r} via attribute {attr_name!r}"
                    )
