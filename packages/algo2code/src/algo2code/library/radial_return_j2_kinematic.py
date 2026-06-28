r"""J2 kinematic linear-hardening radial-return (algo2code interface hook).

constitutive_latex Phase 6 (P6-2). Mirrors
:mod:`algo2code.library.radial_return_j2` (the isotropic power-law
variant) for the linear-kinematic (Prager) hardening model:

- :data:`RADIAL_RETURN_J2_KINEMATIC_LATEX` exposes the verbatim
  algpseudocode.
- :func:`get_radial_return_j2_kinematic_latex` returns it.
- :func:`transpile_radial_return_j2_kinematic` runs
  ``algo2code.transpile`` on the source and returns the emitted module
  text.

The scalar source owns only the plastic-multiplier solve. The yield
surface for kinematic hardening translates rather than expands, so the
scalar loop operates on the trial RELATIVE-stress equivalent
``xi_eq`` (von Mises of ``dev(S) - beta``) with a constant yield radius
``sigy0``. The closed-form linear consistency condition
``dl = (xi_eq - sigy0) / (3*mu + H_kin)`` is authored as the same
fixed-iteration loop structure as the isotropic variant for
transpile-pattern consistency.

Runtime invariant
-----------------

This module imports **only stdlib** (and ``algo2code`` siblings). The
runtime-free contract holds.
"""

from __future__ import annotations

from pathlib import Path


def _load_canonical_source() -> str:
    """Read the canonical algpseudocode source from
    ``dev/algorithms/radial_return_j2_kinematic.tex``.

    Walks up from this module to the repo root, then reads the file.
    Single source of truth — the LaTeX file is authoritative.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "dev" / "algorithms" / "radial_return_j2_kinematic.tex"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "constitutive_latex Phase 6 (P6-2): canonical kinematic algorithm "
        "source not found. Expected at "
        "<repo>/dev/algorithms/radial_return_j2_kinematic.tex."
    )


RADIAL_RETURN_J2_KINEMATIC_LATEX: str = _load_canonical_source()


def get_radial_return_j2_kinematic_latex() -> str:
    """Return the canonical J2 kinematic radial-return algpseudocode LaTeX."""
    return RADIAL_RETURN_J2_KINEMATIC_LATEX


def transpile_radial_return_j2_kinematic(backend: str = "taichi") -> str:
    """Transpile the canonical kinematic algpseudocode to ``backend`` and
    return the emitted Python module source.

    Parameters
    ----------
    backend:
        Target backend name. ``"taichi"`` is the only one consumed by
        ``mechdsl-core`` today.

    Returns
    -------
    str
        Transpiled Python module source. Pass to ``exec`` with a fresh
        namespace dict to load the ``radial_return_j2_kinematic`` callable.
    """
    # Local import keeps the runtime-free invariant — algo2code itself
    # has no third-party imports beyond stdlib.
    from algo2code import transpile

    return transpile(RADIAL_RETURN_J2_KINEMATIC_LATEX, backend=backend)


__all__ = [
    "RADIAL_RETURN_J2_KINEMATIC_LATEX",
    "get_radial_return_j2_kinematic_latex",
    "transpile_radial_return_j2_kinematic",
]
