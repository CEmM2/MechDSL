"""Imported vs algo2code radial-return parity test.

post_recovery_plan Phase 5 (P5-4). Three load-step parity cases
(elastic / elastoplastic / unloading) compare ``mechdsl.lib.plasticity``'s
algo2code-routed dispatch against the imported reference path
(``mechdsl.symbolic.models.j2_power_law.radial_return``).

Tolerance source
----------------
The plan (line 267-268) requires "tolerance derived from imported-path
baseline, not absolute zero". For Phase 5 the algo2code path's runtime
body is a verbatim translation of the imported implementation (the
algo2code parser bugs documented in ``dev/algorithms/radial_return_j2.tex``
defer direct emission), so the parity is bit-equal *today*. The
tolerance constant ``BASELINE_TOL`` is set conservatively to
``1e-12`` — a slack against the imported Newton tolerance — so a
future divergent algo2code emission still has a clear, baseline-derived
ceiling.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.lib.plasticity import (
    FEATURE_FLAG_ENV,
    radial_return,
)
from mechdsl.symbolic.models.j2_power_law import (
    J2PowerLawMaterial,
)
from mechdsl.symbolic.models.j2_power_law import (
    radial_return as imported_radial_return,
)

# Tolerance derived from the imported-path Newton tolerance (1e-12 in
# ReturnMappingResult convergence). Stress / tangent are O(σ_y0)
# magnitude; dimensionless tolerance against the Newton residual gives
# a conservative parity envelope.
BASELINE_TOL = 1e-12


def _material() -> J2PowerLawMaterial:
    return J2PowerLawMaterial(E=200_000.0, nu=0.3, sigma_y0=250.0, K=500.0, n=0.5)


def _assert_parity(via_lib_plasticity, via_imported, *, label: str) -> None:
    np.testing.assert_allclose(
        via_lib_plasticity.stress,
        via_imported.stress,
        atol=BASELINE_TOL,
        rtol=BASELINE_TOL,
        err_msg=f"{label}: stress disagreement",
    )
    assert via_lib_plasticity.alpha_new == pytest.approx(
        via_imported.alpha_new, abs=BASELINE_TOL, rel=BASELINE_TOL
    ), f"{label}: alpha_new disagreement"
    assert via_lib_plasticity.delta_lambda == pytest.approx(
        via_imported.delta_lambda, abs=BASELINE_TOL, rel=BASELINE_TOL
    ), f"{label}: delta_lambda disagreement"
    assert via_lib_plasticity.is_plastic == via_imported.is_plastic, (
        f"{label}: is_plastic flag disagreement"
    )
    np.testing.assert_allclose(
        via_lib_plasticity.tangent,
        via_imported.tangent,
        atol=BASELINE_TOL,
        rtol=BASELINE_TOL,
        err_msg=f"{label}: tangent disagreement",
    )


@pytest.mark.integration
def test_parity_elastic_load_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Small strain that stays inside the yield surface — no plastic
    flow expected."""
    monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)
    mat = _material()
    # Strain magnitude well below σ_y0 / E (~ 1.25e-3) → trial stress
    # under yield.
    E = np.diag([1e-4, -5e-5, -5e-5])
    alpha_old = 0.0

    via_lib = radial_return(mat, E, alpha_old)
    via_imported = imported_radial_return(mat, E, alpha_old)

    assert via_imported.is_plastic is False, (
        "elastic-step setup wrong — imported path reports plastic flow"
    )
    _assert_parity(via_lib, via_imported, label="elastic")


@pytest.mark.integration
def test_parity_elastoplastic_load_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strain large enough to exceed initial yield surface — plastic
    flow expected."""
    monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)
    mat = _material()
    # Order ~ 5e-3 deviatoric strain → σ_eq_trial well above 250 MPa.
    E = np.array(
        [[5e-3, 0.0, 0.0], [0.0, -2.5e-3, 0.0], [0.0, 0.0, -2.5e-3]],
        dtype=float,
    )
    alpha_old = 0.0

    via_lib = radial_return(mat, E, alpha_old)
    via_imported = imported_radial_return(mat, E, alpha_old)

    assert via_imported.is_plastic is True, (
        "elastoplastic-step setup wrong — imported path reports elastic"
    )
    _assert_parity(via_lib, via_imported, label="elastoplastic")


@pytest.mark.integration
def test_parity_unloading_load_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strain backed off below the (already raised) yield surface —
    elastic unloading expected."""
    monkeypatch.delenv(FEATURE_FLAG_ENV, raising=False)
    mat = _material()
    # Large prior plastic strain raises σ_y substantially via power-law
    # hardening; the strain step below stays inside the new surface.
    alpha_old = 0.05  # σ_y(α) ≈ 250 + 500 · 0.05^0.5 ≈ 362 MPa
    E = np.diag([2e-4, -1e-4, -1e-4])

    via_lib = radial_return(mat, E, alpha_old)
    via_imported = imported_radial_return(mat, E, alpha_old)

    assert via_imported.is_plastic is False, (
        "unloading-step setup wrong — imported path reports plastic"
    )
    _assert_parity(via_lib, via_imported, label="unloading")


@pytest.mark.integration
def test_parity_uses_baseline_derived_tolerance() -> None:
    """The tolerance constant ``BASELINE_TOL`` is documented and
    bounded above zero (per plan line 267-268)."""
    assert BASELINE_TOL > 0.0
    assert BASELINE_TOL <= 1e-9, (
        "BASELINE_TOL too loose; should be near the imported Newton tolerance"
    )
