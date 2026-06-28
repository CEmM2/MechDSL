"""Generated Newmark-beta time integration over the ``ti_runtime`` seam (PlanJune14 P6-1).

The temporal twin of :mod:`mechdsl.solver.seam_solve`: it transpiles the
canonical Newmark-beta step authored in ``dev/algorithms/newmark.tex`` via
``algo2code`` in *runtime mode*, imports the generated ``newmark_step`` body, and
binds it through the ``ti_runtime`` ``TimeIntegrationContext.set_integrator``
seam. The resulting integrator advances a dynamic state ``(u, v, a)`` over
``ti.Vector.field`` DOF vectors with **no NumPy in the hot path** — every update
is a ``ti_runtime.vector_ops`` AXPBY/copy call, and the only non-primitive call
is the injected acceleration solve ``solve_a`` (the matrix-free seam, the
temporal analogue of the PCG operator ``A``).

Proves the "any algorithm box" claim end-to-end: the *same* Seams & Bodies
pattern that drives the generated linear solver (P4) and the dissipative J2 model
(P5-1) also drives a generated *time integrator* — MechDSL owns the stable
``TimeIntegrationContext`` wrapper; algo2code generates the body.

Build mechanism
---------------
Reuses the shared :mod:`mechdsl.solver._seam_runtime` plumbing
(:func:`~mechdsl.solver._seam_runtime.import_generated_module` +
:func:`~mechdsl.solver._seam_runtime.strip_ti_init`; the caller owns Taichi init /
the device), and caches the transpiled-and-imported module once per process so
repeated steps do not leak tempdirs / ``sys.modules`` entries (the P4-2 minor).

Taichi note
-----------
The generated module is written to a real ``.py`` file and imported (not
``exec``'d): Taichi needs ``inspect.getsource`` on the driver, mirroring the
``seam_solve`` / P2-2 pattern.
"""

# NOTE: no ``from __future__ import annotations`` — downstream callers wire this
# into modules that define ``@ti.kernel`` bodies, and Taichi requires *eager*
# annotation evaluation (PEP 563 stringifies ti.template() and breaks the JIT;
# the PJ-0/PJ-1 finding, shared with seam_solve).

import functools
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from algo2code import transpile
from mechdsl.solver._seam_runtime import import_generated_module, strip_ti_init

if TYPE_CHECKING:
    from ti_runtime.seams import TimeIntegrationContext

# Repo-relative path to the canonical Newmark algorithm source.  This file lives
# at packages/mechdsl-core/src/mechdsl/solver/seam_integrate.py, so the repo root
# is five parents up (same depth as seam_solve.py).
_NEWMARK_TEX_PATH = Path(__file__).resolve().parents[5] / "dev" / "algorithms" / "newmark.tex"


def newmark_tex_path() -> Path:
    """Return the path to the canonical Newmark-beta LaTeX source."""
    return _NEWMARK_TEX_PATH


def transpile_seam_newmark() -> str:
    """Transpile ``dev/algorithms/newmark.tex`` to runtime-mode Taichi source.

    The module-level ``ti.init`` line is stripped: the **caller** owns Taichi
    initialisation (device/arch), so the generated body is device-agnostic — it
    runs on whatever arch the caller's ``ti.init`` selected. (Re-init here would
    free already-allocated DOF fields — the P2-2 finding; shared with
    :func:`mechdsl.solver.seam_solve.transpile_seam_pcg`.)

    The emitted ``newmark_step`` body advances ``(u, v, a)`` one step with only
    ``ti_runtime.vector_ops`` AXPBY/copy calls plus the injected in-place
    acceleration solve ``solve_a(u_pred, v_pred, a_out)`` — no NumPy.
    """
    source = _NEWMARK_TEX_PATH.read_text(encoding="utf-8")
    code = transpile(source, backend="taichi", runtime="ti_runtime")
    return strip_ti_init(code)


@functools.cache
def _seam_newmark_module() -> ModuleType:
    """Transpile + import the generated Newmark step once per process.

    The generated body is both problem- and device-agnostic (the device comes
    from the caller's ``ti.init``), so a single cached module + temp file serves
    every step — avoiding an unbounded tempdir / ``sys.modules`` leak on repeated
    calls. Safe to reuse across ``ti.init`` re-inits: the module holds no
    module-level fields, and its kernel calls re-JIT lazily.
    """
    return import_generated_module(transpile_seam_newmark(), "_generated_seam_newmark")


def build_seam_newmark() -> Callable[..., object]:
    """Return the generated ``newmark_step`` callable (transpiled, cached).

    Signature: ``newmark_step(u, v, a, solve_a, dt, beta, gamma) -> (u, v, a)``
    where ``solve_a(u_pred, v_pred, a_out)`` is the in-place matrix-free
    acceleration solve (the ``ti_runtime`` seam convention, out LAST).
    """
    step_fn: Callable[..., object] | None = getattr(_seam_newmark_module(), "newmark_step", None)
    if step_fn is None:  # pragma: no cover - guarded by the transpile contract
        raise AttributeError(
            "generated Newmark module is missing the `newmark_step` driver function"
        )
    return step_fn


def bind_generated_newmark_integrator(
    ctx: "TimeIntegrationContext",
) -> "TimeIntegrationContext":
    """Bind the generated Newmark-beta step into ``ctx`` via ``set_integrator``.

    After this call ``ctx.step(u, v, a)`` runs the generated ``newmark_step`` body
    against ``ctx``'s injected acceleration solve (``set_accel_solve`` /
    ``apply_accel_solve``) and step controls (``ctx.dt`` / ``ctx.beta`` /
    ``ctx.gamma``), advancing ``(u, v, a)`` one step in place over
    ``ti.Vector.field`` DOF vectors with no NumPy in the hot path.

    Returns ``ctx`` for chaining.
    """
    ctx.set_integrator(build_seam_newmark())
    return ctx


__all__ = [
    "bind_generated_newmark_integrator",
    "build_seam_newmark",
    "newmark_tex_path",
    "transpile_seam_newmark",
]
