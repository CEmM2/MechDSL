r"""J2 mixed-hardening radial-return (algo2code interface hook).

constitutive_latex Phase 6 (P6-3). Mirrors
:mod:`algo2code.library.radial_return_j2` (isotropic power-law) and
:mod:`algo2code.library.radial_return_j2_kinematic` (linear kinematic)
for the MIXED-hardening model — the yield surface BOTH translates
(back-stress ``beta``, Prager) AND expands (power-law radius
``sigma_y(alpha) = sigy0 + K*alpha^n``) simultaneously:

- :data:`RADIAL_RETURN_J2_MIXED_LATEX` exposes the verbatim algpseudocode.
- :func:`get_radial_return_j2_mixed_latex` returns it.
- :func:`transpile_radial_return_j2_mixed` runs ``algo2code.transpile``
  on the source and returns the emitted module text.

The scalar source owns only the plastic-multiplier solve. Yield is on
the trial RELATIVE-stress equivalent ``xi_eq`` (von Mises of
``dev(S) - beta``) against the EXPANDING radius ``sigma_y(alpha)``.
Because the isotropic part is a nonlinear power law in
``alpha = alpha_old + dl``, the consistency condition is nonlinear in
``dl`` and is solved by the same scalar NEWTON loop as the isotropic
variant — but with the kinematic ``(3*mu + H_kin)*dl`` linear term added
to the residual and the Prager modulus folded into the Newton
denominator alongside the isotropic slope.

Runtime invariant
-----------------

This module imports **only stdlib** (and ``algo2code`` siblings). The
runtime-free contract holds.
"""

from __future__ import annotations

from algo2code.library.sources import algorithm_source

# Single source of truth: the bundled ``algorithms/radial_return_j2_mixed.tex``
# (package data shipped in the wheel) is authoritative.
RADIAL_RETURN_J2_MIXED_LATEX: str = algorithm_source("radial_return_j2_mixed.tex")


def get_radial_return_j2_mixed_latex() -> str:
    """Return the canonical J2 mixed radial-return algpseudocode LaTeX."""
    return RADIAL_RETURN_J2_MIXED_LATEX


def transpile_radial_return_j2_mixed(backend: str = "taichi") -> str:
    """Transpile the canonical mixed algpseudocode to ``backend`` and
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
        namespace dict to load the ``radial_return_j2_mixed`` callable.
    """
    # Local import keeps the runtime-free invariant — algo2code itself
    # has no third-party imports beyond stdlib.
    from algo2code import transpile

    return transpile(RADIAL_RETURN_J2_MIXED_LATEX, backend=backend)


__all__ = [
    "RADIAL_RETURN_J2_MIXED_LATEX",
    "get_radial_return_j2_mixed_latex",
    "transpile_radial_return_j2_mixed",
]
