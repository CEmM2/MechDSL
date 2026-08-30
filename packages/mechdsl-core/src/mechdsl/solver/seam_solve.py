"""Generated matrix-free PCG over the ``ti_runtime`` seams (PlanJune14 P4-2).

This module is the **all-Taichi on-device seam path** (Option 1): it transpiles
the canonical matrix-free PCG authored in ``dev/algorithms/pcg.tex`` via
``algo2code`` in *runtime mode*, imports the generated ``pcg`` body, and binds it
through the ``ti_runtime`` ``LinearSolveContext.set_solver`` seam.  The resulting
solver solves ``A x = b`` over ``ti.Vector.field`` DOF vectors with **no NumPy in
the hot path** — the operator is the injected matrix-free ``apply_A`` (e.g. the
P3-2 generated SVK tangent), and the preconditioner is the injected
``apply_preconditioner``.

It deliberately does **not** route through the NumPy
``import_adapter.LinearSolverInterface`` / ``newton.py`` matvec callback: that is
the host-NumPy path, whereas this is the on-device Taichi path the spike
(``tests/spike/svk_hex8_taichi.py``) demonstrates and PJ-1 gated.

Productionization template
--------------------------
The PJ-1 spike's hand-written :func:`pcg` body is the template.  P4-2 makes that
body *generated*: :func:`build_seam_pcg` returns the transpiled-and-imported
``pcg`` callable; :func:`bind_generated_pcg_solver` wires it into a
``LinearSolveContext`` so ``ctx.solver.solve(b, x, tol, maxiter)`` runs the
generated PCG against the context's injected operator + preconditioner.

Taichi note
-----------
The generated module is written to a real ``.py`` file and imported (not
``exec``'d): Taichi needs ``inspect.getsource`` on the driver, mirroring
``tests/_e2e_helpers._import_generated_module`` and the P2-2 pattern.
"""

# NOTE: no ``from __future__ import annotations`` — downstream callers wire this
# into modules that define ``@ti.kernel`` bodies, and Taichi requires *eager*
# annotation evaluation (PEP 563 stringifies ti.template() and breaks the JIT).

import functools
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

from algo2code import transpile
from mechdsl.solver._seam_runtime import import_generated_module, strip_ti_init

if TYPE_CHECKING:
    from ti_runtime.seams import LinearSolveContext

# Repo-relative path to the canonical PCG algorithm source.  This file lives at
# packages/mechdsl-core/src/mechdsl/solver/seam_solve.py, so the repo root is
# five parents up.
_PCG_TEX_PATH = Path(__file__).resolve().parents[5] / "dev" / "algorithms" / "pcg.tex"


def pcg_tex_path() -> Path:
    """Return the path to the canonical matrix-free PCG LaTeX source."""
    return _PCG_TEX_PATH


def transpile_seam_pcg() -> str:
    """Transpile ``dev/algorithms/pcg.tex`` to runtime-mode Taichi source.

    The module-level ``ti.init`` line is stripped: the **caller** owns Taichi
    initialisation, and therefore the device/arch. (Re-init here would free
    already-allocated DOF fields — the P2-2 finding.) The generated body is thus
    device-agnostic — it runs on whatever arch the caller's ``ti.init`` selected.

    The emitted ``pcg`` body is matrix-free: it calls the injected operator
    ``A(out, x)`` and preconditioner ``M_inv(r, z)`` plus ``ti_runtime``
    ``vector_ops`` primitives — no dense ``_matvec``, no NumPy.
    """
    source = _PCG_TEX_PATH.read_text(encoding="utf-8")
    code = transpile(source, backend="taichi", runtime="ti_runtime")
    return strip_ti_init(code)


@functools.cache
def _seam_pcg_module() -> ModuleType:
    """Transpile + import the generated PCG once per process.

    The generated body is both problem- and device-agnostic (the device comes
    from the caller's ``ti.init``), so a single cached module + temp file serves
    every solve — avoiding an unbounded tempdir / ``sys.modules`` leak on
    repeated calls. Safe to reuse across ``ti.init`` re-inits: the module holds
    no module-level fields, and its ``@ti.kernel`` bodies re-JIT lazily.
    """
    return import_generated_module(transpile_seam_pcg(), "_generated_seam_pcg")


def build_seam_pcg() -> Callable[..., object]:
    """Return the generated ``pcg`` callable (transpiled from ``pcg.tex``, cached).

    Signature: ``pcg(A, b, x, M_inv, tol, maxiter)
    -> (x, iterations, residual, converged)`` where ``A(out, x)`` is the
    in-place matrix-free operator and ``M_inv(r, z)`` the in-place
    preconditioner apply (the ``ti_runtime`` seam conventions).

    The 4th return value ``converged`` is a hard non-convergence flag (WI-2):
    ``1`` on a tolerance hit (or the ``r0 == 0`` early-out), ``0`` on maxiter
    exhaustion or the ``|pq| < 1e-300`` breakdown. The **raw** callable returned
    here does NOT raise on ``converged == 0`` -- it merely reports the flag (so
    parity tests can exercise the exhausted path). Enforcement of the failure
    contract lives at the seam boundary: see :func:`bind_generated_pcg_solver`,
    whose injected solver raises rather than returning a non-converged ``x``.
    """
    pcg_fn: Callable[..., object] | None = getattr(_seam_pcg_module(), "pcg", None)
    if pcg_fn is None:  # pragma: no cover - guarded by the transpile contract
        raise AttributeError("generated PCG module is missing the `pcg` driver function")
    return pcg_fn


def bind_generated_pcg_solver(ctx: "LinearSolveContext") -> "LinearSolveContext":
    """Bind the generated matrix-free PCG into ``ctx`` via ``set_solver``.

    After this call ``ctx.solver.solve(b, x, tol, maxiter)`` runs the generated
    PCG body against ``ctx``'s injected operator (``set_operator`` / ``apply_A``)
    and preconditioner (``set_preconditioner`` / ``apply_preconditioner``),
    solving ``A x = b`` in place over ``ti.Vector.field`` DOF vectors with no
    NumPy in the hot path.

    The injected solver adapts the seam conventions to the generated body's
    callable arguments:

    * operator     ``A(out, x)``   → ``ctx.apply_A(out, x)``         (out FIRST)
    * preconditioner ``M_inv(r, z)`` → ``ctx.apply_preconditioner(z, r)`` (out LAST)

    Failure contract (WI-2): the generated PCG returns a 4th ``converged`` flag.
    The injected ``_solve`` consumes it and **raises** ``RuntimeError`` when the
    inner solve did not converge (maxiter exhaustion or ``|pq| < 1e-300``
    breakdown) rather than returning a garbage increment for a Newton / time
    step to advance on. This is strictly louder than the host ``PCGSolver`` (a
    ``RuntimeWarning``), per the project's "fail-loud, no silent
    non-convergence" goal. On success it returns the ``(x, iterations,
    residual)`` 3-tuple (``converged`` is then necessarily ``1`` and dropped).

    Returns ``ctx`` for chaining.
    """
    generated_pcg = build_seam_pcg()

    def _solve(b, x, tol, maxiter):
        def operator_A(out, vec):
            ctx.apply_A(out, vec)  # apply_A(out, x): out FIRST (seam contract)

        def precond_M_inv(r_in, z_out):
            ctx.apply_preconditioner(z_out, r_in)  # M^{-1}(r) → z, out LAST

        # The transpiled body returns a dynamically-typed 4-tuple
        # (x, iterations, residual, converged); cast so the unpack type-checks.
        x_out, iterations, residual, converged = cast(
            "tuple[Any, Any, Any, Any]",
            generated_pcg(operator_A, b, x, precond_M_inv, tol, maxiter),
        )
        if converged == 0:
            raise RuntimeError(
                "Seam PCG did not converge: "
                f"{int(iterations)} iterations, residual {float(residual):.3e} "
                f"(relative tol {float(tol):.3e}). The inner linear solve "
                "failed; refusing to return a non-converged increment for an "
                "outer Newton / time step to advance on (fail-loud). Raise "
                "maxiter, loosen tol, or check the injected operator / "
                "preconditioner."
            )
        return x_out, iterations, residual

    ctx.set_solver(_solve)
    return ctx


__all__ = [
    "bind_generated_pcg_solver",
    "build_seam_pcg",
    "pcg_tex_path",
    "transpile_seam_pcg",
]
