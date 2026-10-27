"""Generated Newmark-beta time integration over the ``ti_runtime`` seam.

The temporal twin of :mod:`mechdsl.solver.seam_solve`: it transpiles the
canonical Newmark-beta step authored in ``algo2code/library/algorithms/newmark.tex`` via
``algo2code`` in *runtime mode*, imports the generated ``newmark_step`` body, and
binds it through the ``ti_runtime`` ``TimeIntegrationContext.set_integrator``
seam. The resulting integrator advances a dynamic state ``(u, v, a)`` over
``ti.Vector.field`` DOF vectors with **no NumPy in the hot path** — every update
is a ``ti_runtime.vector_ops`` AXPBY/copy call, and the only non-primitive call
is the injected acceleration solve ``solve_a`` (the matrix-free seam, the
temporal analogue of the PCG operator ``A``).

Proves the "any algorithm box" claim end-to-end: the *same* Seams & Bodies
pattern that drives the generated linear solver and the dissipative J2 model
also drives a generated *time integrator* — MechDSL owns the stable
``TimeIntegrationContext`` wrapper; algo2code generates the body.

Build mechanism
---------------
Reuses the shared :mod:`mechdsl.solver._seam_runtime` plumbing
(:func:`~mechdsl.solver._seam_runtime.import_generated_module` +
:func:`~mechdsl.solver._seam_runtime.strip_ti_init`; the caller owns Taichi init /
the device), and caches the transpiled-and-imported module once per process so
repeated steps do not leak tempdirs / ``sys.modules`` entries.

Taichi note
-----------
The generated module is written to a real ``.py`` file and imported (not
``exec``'d): Taichi needs ``inspect.getsource`` on the driver, mirroring
``seam_solve``.
"""

# NOTE: no ``from __future__ import annotations`` — downstream callers wire this
# into modules that define ``@ti.kernel`` bodies, and Taichi requires *eager*
# annotation evaluation (PEP 563 stringifies ti.template() and breaks the JIT;
# same constraint as seam_solve).

import functools
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from algo2code import transpile
from algo2code.library.sources import algorithm_source, algorithm_source_path
from mechdsl.solver._seam_runtime import import_generated_module, strip_ti_init

if TYPE_CHECKING:
    from ti_runtime.seams import TimeIntegrationContext

# The canonical Newmark algorithm source ships as package data inside
# ``algo2code`` (``algo2code/library/algorithms/newmark.tex``), so it is
# available from an installed wheel without a source checkout.
_NEWMARK_TEX_NAME = "newmark.tex"


def newmark_tex_path() -> Path:
    """Return the path to the canonical Newmark-beta LaTeX source."""
    return algorithm_source_path(_NEWMARK_TEX_NAME)


def transpile_seam_newmark() -> str:
    """Transpile ``algo2code/library/algorithms/newmark.tex`` to runtime-mode Taichi source.

    The module-level ``ti.init`` line is stripped: the **caller** owns Taichi
    initialisation (device/arch), so the generated body is device-agnostic — it
    runs on whatever arch the caller's ``ti.init`` selected. (Re-init here would
    free already-allocated DOF fields; shared with
    :func:`mechdsl.solver.seam_solve.transpile_seam_pcg`.)

    The emitted ``newmark_step`` body advances ``(u, v, a)`` one step with only
    ``ti_runtime.vector_ops`` AXPBY/copy calls plus the injected in-place
    acceleration solve ``solve_a(u_pred, v_pred, a_out)`` — no NumPy.
    """
    source = algorithm_source(_NEWMARK_TEX_NAME)
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
