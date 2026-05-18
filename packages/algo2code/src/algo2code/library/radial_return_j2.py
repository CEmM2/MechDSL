r"""Canonical J2 radial-return algorithm (algo2code interface hook).

post_recovery_plan Phase 5 (P5-1, P5-3). Mirrors the
``algo2code.library.pcg`` pattern but goes one step further:

- :data:`RADIAL_RETURN_J2_LATEX` exposes the verbatim algpseudocode.
- :func:`get_radial_return_j2_latex` returns it (accessor symmetry
  with PCG).
- :func:`transpile_radial_return_j2` runs ``algo2code.transpile`` on
  the source and returns the emitted Python module text. Phase 5's
  parser fixes (multi-letter scratch identifiers; binary ``/`` in
  assignment LHS) and codegen fix (``n = b.shape[0]`` regression for
  scalar-only algorithms) make this work end-to-end.

The mechdsl-core wrapper at ``mechdsl.lib.plasticity`` execs the
transpiled module text into a namespace at import time and consumes
the resulting ``radial_return_j2`` callable inside its dispatcher.

Runtime invariant
-----------------

This module imports **only stdlib** (and ``algo2code`` siblings). The
runtime-free contract holds.
"""

from __future__ import annotations

from pathlib import Path


def _load_canonical_source() -> str:
    """Read the canonical algpseudocode source from
    ``dev/algorithms/radial_return_j2.tex``.

    Walks up from this module to the repo root, then reads the
    file. Single source of truth — the LaTeX file is authoritative.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "dev" / "algorithms" / "radial_return_j2.tex"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "post_recovery_plan Phase 5 (P5-1): canonical algorithm source "
        "not found. Expected at <repo>/dev/algorithms/radial_return_j2.tex."
    )


RADIAL_RETURN_J2_LATEX: str = _load_canonical_source()


def get_radial_return_j2_latex() -> str:
    """Return the canonical J2 radial-return algpseudocode LaTeX source."""
    return RADIAL_RETURN_J2_LATEX


def transpile_radial_return_j2(backend: str = "taichi") -> str:
    """Transpile the canonical algpseudocode to ``backend`` and return
    the emitted Python module source.

    post_recovery_plan Phase 5 lifted the deferral that previously
    blocked this round-trip: the algo2code expr_parser now handles
    multi-letter scratch identifiers (``sy``, ``Hp``, ``ap``) and
    binary ``/`` in assignment LHS contexts, and the Taichi codegen
    no longer emits ``n = b.shape[0]`` for scalar-only algorithms.

    Parameters
    ----------
    backend:
        Target backend name. ``"taichi"`` is the only one consumed by
        ``mechdsl-core`` today.

    Returns
    -------
    str
        Transpiled Python module source. Pass to ``exec`` with a fresh
        namespace dict to load the ``radial_return_j2`` callable.
    """
    # Local import keeps the runtime-free invariant — algo2code itself
    # has no third-party imports beyond stdlib.
    from algo2code import transpile

    return transpile(RADIAL_RETURN_J2_LATEX, backend=backend)


__all__ = [
    "RADIAL_RETURN_J2_LATEX",
    "get_radial_return_j2_latex",
    "transpile_radial_return_j2",
]
