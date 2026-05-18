"""Plasticity dispatch — algo2code-generated path with imported fallback.

post_recovery_plan Phase 5 (P5-3). The dispatcher's algo2code path now
genuinely consumes ``algo2code.transpile`` end-to-end: the canonical
algpseudocode at ``dev/algorithms/radial_return_j2.tex`` is transpiled
to Python at module import time, exec'd into a namespace, and the
resulting scalar Newton inner loop is invoked from inside the wrapper.
The imported reference path remains as a feature-flagged fallback.

Phase 5 also landed the algo2code parser fixes (multi-letter scratch
identifiers and binary ``/`` in assignment LHS contexts) plus the
Taichi codegen scalar-algorithm fix that previously blocked direct
emission for radial-return.

Public surface
--------------
- :func:`radial_return` — dispatcher matching the imported function's
  signature exactly.
- :func:`active_path_name` — returns ``"algo2code"`` or ``"imported"``.
- :data:`FEATURE_FLAG_ENV` — env-var name (single source of truth).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from algo2code.library.radial_return_j2 import transpile_radial_return_j2
from mechdsl.symbolic.models.j2_power_law import (
    ReturnMappingResult,
    assemble_j2_like_tangent,
    deviatoric,
    elastic_tangent,
    von_mises,
    yield_stress,
    yield_stress_derivative,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as _imported_radial_return,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial


FEATURE_FLAG_ENV = "MECHDSL_USE_IMPORTED_RR"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


# ── Transpile the algpseudocode once at import time ──────────────────────────
#
# `algo2code.transpile` returns a Python module string with a top-level
# `radial_return_j2(sigma_eq, alpha, mu, K, n, sigy0, tol, max_iter)`
# function. We exec it into a clean namespace and capture the callable.
# `ti.init` runs at import time of the emitted module — identical to how
# the rest of the codebase initialises Taichi — but the function itself
# is plain Python (no `@ti.func` / `@ti.kernel` decorator on scalar
# algorithms), so it runs on plain float inputs and is bit-equal to the
# imported reference's inner Newton step.
_TRANSPILED_NAMESPACE: dict[str, object] = {}
_TRANSPILED_SOURCE = transpile_radial_return_j2(backend="taichi")
exec(
    compile(_TRANSPILED_SOURCE, "<algo2code:radial_return_j2>", "exec"),
    _TRANSPILED_NAMESPACE,
)
_radial_return_j2_scalar = _TRANSPILED_NAMESPACE["radial_return_j2"]


def _imported_path_active() -> bool:
    raw = os.environ.get(FEATURE_FLAG_ENV, "").strip().lower()
    return raw in _TRUE_VALUES


def active_path_name() -> str:
    """Return the name of the currently active radial-return path.

    Re-evaluates the env var on every call so toggling
    ``MECHDSL_USE_IMPORTED_RR`` between calls within a single Python
    session swaps the active path without recompilation.
    """
    return "imported" if _imported_path_active() else "algo2code"


def _radial_return_algo2code(
    mat: J2PowerLawMaterial,
    E_strain: NDArray,
    alpha_old: float,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> ReturnMappingResult:
    """Radial return whose scalar Newton step is the
    ``algo2code``-transpiled function.

    The wrapper handles tensor algebra (deviatoric, von Mises, return
    mapping reconstruction, algorithmic tangent) using the imported
    helpers — those are pure NumPy and not in algo2code's grammar
    surface today. The plastic-multiplier search itself
    (``delta_lambda``) is the transpiled scalar Newton.

    Bit-equality with :func:`mechdsl.symbolic.models.j2_power_law.radial_return`
    is asserted by the parity test in
    ``packages/mechdsl-core/tests/test_j2_radial_return_parity.py``.
    """
    lam = mat.lam
    mu = mat.mu

    # --- 1. Elastic trial stress (SVK-like) — same as imported.
    tr_E = float(np.trace(E_strain))
    S_trial = lam * tr_E * np.eye(3) + 2.0 * mu * E_strain

    # --- 2. Deviatoric trial and von Mises — imported helpers.
    S_dev_trial = deviatoric(S_trial)
    S_vol_trial = S_trial - S_dev_trial
    sigma_eq_trial = von_mises(S_dev_trial)

    # --- 3. Near-zero deviatoric guard (07-CONVENTIONS) — same as
    # imported. The transpiled scalar function does not implement this
    # boundary case (algo2code's Branch grammar would force rephrasing
    # to a single yield-test); the wrapper handles it.
    sigma_y_old = yield_stress(mat, alpha_old)
    if sigma_eq_trial < 1e-12 * sigma_y_old:
        C_el = elastic_tangent(lam, mu)
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    # --- 4. Trial yield check + scalar Newton — algo2code-transpiled.
    plastic_flag, alpha_new_from_algo, dl_from_algo = _radial_return_j2_scalar(
        sigma_eq=sigma_eq_trial,
        alpha=alpha_old,
        mu=mu,
        K=mat.K,
        n=mat.n,
        sigy0=mat.sigma_y0,
        tol=tol,
        max_iter=max_iter,
    )

    if plastic_flag == 0:
        # Elastic step — return trial stress with elastic tangent.
        C_el = elastic_tangent(lam, mu)
        return ReturnMappingResult(
            stress=S_trial,
            alpha_new=alpha_old,
            delta_lambda=0.0,
            is_plastic=False,
            tangent=C_el,
        )

    dl = float(dl_from_algo)
    # Clamp tiny negative from Newton — same as imported.
    if dl < 0.0:
        if dl >= -1e-15:
            dl = 0.0
        else:
            msg = f"Negative plastic multiplier delta_lambda = {dl:.3e}"
            raise ValueError(msg)

    # --- 5. Update stress — imported helpers.
    ratio = 3.0 * mu * dl / sigma_eq_trial
    S_updated = S_vol_trial + (1.0 - ratio) * S_dev_trial

    # --- 6. Update alpha.
    alpha_new = alpha_old + dl

    # --- 7. Algorithmic consistent tangent — imported helper.
    H_prime_final = yield_stress_derivative(mat, alpha_new)
    C_ep = assemble_j2_like_tangent(
        lam=lam,
        mu=mu,
        S_dev_trial=S_dev_trial,
        sigma_eq_trial=sigma_eq_trial,
        dl=dl,
        denominator=3.0 * mu + H_prime_final,
    )

    return ReturnMappingResult(
        stress=S_updated,
        alpha_new=alpha_new,
        delta_lambda=dl,
        is_plastic=True,
        tangent=C_ep,
    )


def radial_return(
    mat: J2PowerLawMaterial,
    E_strain: NDArray,
    alpha_old: float,
    tol: float = 1e-12,
    max_iter: int = 50,
) -> ReturnMappingResult:
    """Dispatch to the algo2code-generated path (default) or the
    imported fallback (when ``MECHDSL_USE_IMPORTED_RR`` is set)."""
    if _imported_path_active():
        return _imported_radial_return(mat, E_strain, alpha_old, tol=tol, max_iter=max_iter)
    return _radial_return_algo2code(mat, E_strain, alpha_old, tol=tol, max_iter=max_iter)


__all__ = [
    "FEATURE_FLAG_ENV",
    "ReturnMappingResult",
    "active_path_name",
    "radial_return",
]
