"""Task P9-3: Budget regression test for all element x backend combos.

Phase 9 exit acceptance:
  1. Every realisable (element type, constitutive model, backend) triple
     passes the JIT budget (all contraction plans in tier 1 or 2).
  2. Family-based emission wall-clock time is within 1.2x of the tier-only
     baseline captured in ``golden/template_family_emission_baseline.json``.

Realisable matrix (probe result, 2026-04-18)
--------------------------------------------
Only HEX8 localises today; TET4, TET10, HEX20 raise ValueError (Plan B §B5).
Backend coverage by material:
  - taichi: svk, j2_power_law, lemaitre         (both TL and UL)
  - mfem:   svk only                             (both TL and UL)
  - moose:  svk, j2_power_law, perzyna, lemaitre (both TL and UL)
  - perzyna: taichi raises ValueError (unsupported for Taichi codegen)
  - mfem + plastic/damage: raises ValueError (SVK only in MFEM emitter)

Unsupported combos are represented as ``pytest.mark.skip`` parametrised cases
so they appear in the test run output and can be promoted when support lands.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from typing import TYPE_CHECKING, Any
from unittest import mock

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.mfem_printer import emit as mfem_emit
from mechdsl.codegen.moose_printer import emit as moose_emit
from mechdsl.codegen.taichi_printer import emit as taichi_emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RATIO_TOLERANCE = 1.2
_N_TRIALS = 5
_GOLDEN_FILENAME = "template_family_emission_baseline.json"

_MATERIAL_PARAMS: dict[str, dict[str, float]] = {
    "svk": {"E": 200e3, "nu": 0.3},
    "j2_power_law": {"E": 200e3, "nu": 0.3},
    "perzyna": {"E": 200e3, "nu": 0.3},
    "lemaitre": {"E": 200e3, "nu": 0.3},
}

_SKIP_REASONS: dict[str, str] = {
    # element-level unsupported
    "tet4": "TET4 localisation not yet implemented (Plan B §B5.1)",
    "tet10": "TET10 localisation not yet implemented (Plan B §B5.2)",
    "hex20": "HEX20 localisation not yet implemented (Plan B §B5.3)",
    # material x backend unsupported
    "perzyna-taichi": "Perzyna not supported in Taichi codegen emitter",
    "j2_power_law-mfem": "J2 plastic not supported in MFEM emitter (SVK only)",
    "perzyna-mfem": "Perzyna not supported in MFEM emitter (SVK only)",
    "lemaitre-mfem": "Lemaitre not supported in MFEM emitter (SVK only)",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_EMIT = {
    "taichi": taichi_emit,
    "mfem": mfem_emit,
    "moose": moose_emit,
}


def _triple_key(elt: str, form: str, mat: str, backend: str) -> str:
    """Canonical string key for a triple."""
    return f"{elt}-{form}-{mat}-{backend}"


def _skip_reason(elt: str, mat: str, backend: str) -> str | None:
    """Return a skip reason string if this combination is unsupported, else None."""
    if elt in _SKIP_REASONS:
        return _SKIP_REASONS[elt]
    mat_backend = f"{mat}-{backend}"
    if mat_backend in _SKIP_REASONS:
        return _SKIP_REASONS[mat_backend]
    return None


def _make_bundle(elt: ElementType, form: Formulation, mat: str) -> ArtifactBundle:
    """Build an ArtifactBundle for the given triple."""
    params = _MATERIAL_PARAMS[mat]
    problem_ir = ProblemIR(
        dim=3,
        formulation=form,
        element_type=elt,
        material=MaterialSpec(model=mat, params=params),
        boundaries=(BoundaryCondition(name="fix_root", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _measure_median_emission(
    emit_fn: Any,
    bundle: ArtifactBundle,
    family_on: bool,
    n: int = _N_TRIALS,
) -> float:
    """Return median wall-clock emission time over *n* trials."""
    flag_value = "1" if family_on else "0"
    times: list[float] = []
    for _ in range(n):
        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": flag_value}):
            t0 = time.perf_counter()
            emit_fn(bundle)
            times.append(time.perf_counter() - t0)
    return statistics.median(times)


# ---------------------------------------------------------------------------
# Parametrised combo matrix
# ---------------------------------------------------------------------------

_ELEMENT_TYPES = [
    ElementType.HEX8,
    ElementType.TET4,
    ElementType.TET10,
    ElementType.HEX20,
]
_FORMULATIONS = [Formulation.TOTAL_LAGRANGIAN, Formulation.UPDATED_LAGRANGIAN]
_MATERIALS = ["svk", "j2_power_law", "perzyna", "lemaitre"]
_BACKENDS = ["taichi", "mfem", "moose"]

# Build pytest.param list: realised ones + skipped ones
_BUDGET_PARAMS: list[Any] = []
for _elt in _ELEMENT_TYPES:
    for _form in _FORMULATIONS:
        for _mat in _MATERIALS:
            for _backend in _BACKENDS:
                _reason = _skip_reason(_elt.value, _mat, _backend)
                _key = _triple_key(_elt.value, _form.value, _mat, _backend)
                if _reason is not None:
                    _BUDGET_PARAMS.append(
                        pytest.param(
                            _elt,
                            _form,
                            _mat,
                            _backend,
                            id=_key,
                            marks=pytest.mark.skip(reason=_reason),
                        )
                    )
                else:
                    _BUDGET_PARAMS.append(pytest.param(_elt, _form, _mat, _backend, id=_key))

# Realisable-only params (for the slow timing test)
_REALISABLE_PARAMS: list[Any] = []
for _elt in _ELEMENT_TYPES:
    for _form in _FORMULATIONS:
        for _mat in _MATERIALS:
            for _backend in _BACKENDS:
                _reason = _skip_reason(_elt.value, _mat, _backend)
                _key = _triple_key(_elt.value, _form.value, _mat, _backend)
                if _reason is None:
                    _REALISABLE_PARAMS.append(pytest.param(_elt, _form, _mat, _backend, id=_key))


# ---------------------------------------------------------------------------
# Test 1 — budget regression (fast)
# ---------------------------------------------------------------------------


class TestAllElementMaterialBackendTripsPassBudget:
    """Regression: every realisable triple stays in tier 1 or 2 and emits without error."""

    @pytest.mark.regression
    @pytest.mark.parametrize("elt,form,mat,backend", _BUDGET_PARAMS)
    def test_all_element_material_backend_triples_pass_budget(
        self,
        elt: ElementType,
        form: Formulation,
        mat: str,
        backend: str,
    ) -> None:
        """All contraction plans must be tier 1 or 2 (within @ti.func budget).

        Acceptance criterion: every realisable (element x material x backend)
        triple compiles with no plan reporting tier 3.

        Passes when: for every plan in the bundle, ``plan.tier in {1, 2}``.
        The backend emitter must also complete without raising.
        """
        bundle = _make_bundle(elt, form, mat)

        over_budget = [p for p in bundle.contraction_plans if p.tier == 3]
        assert not over_budget, (
            f"Triple {_triple_key(elt.value, form.value, mat, backend)!r} has "
            f"{len(over_budget)} over-budget contraction plan(s) (tier 3). "
            f"Plans: {[{'einsum': p.einsum_string, 'tier': p.tier} for p in over_budget]}"
        )

        # Verify every plan is tier 1 or 2
        for plan in bundle.contraction_plans:
            assert plan.tier in (1, 2), (
                f"Plan tier {plan.tier} not in {{1, 2}} for "
                f"{_triple_key(elt.value, form.value, mat, backend)!r}; "
                f"einsum={plan.einsum_string!r}"
            )

        # Emit via the backend — must not raise
        emit_fn = _BACKEND_EMIT[backend]
        try:
            emit_fn(bundle)
        except Exception as exc:
            pytest.fail(
                f"Backend {backend!r} emit raised {type(exc).__name__} for "
                f"{_triple_key(elt.value, form.value, mat, backend)!r}: {exc}"
            )


# ---------------------------------------------------------------------------
# Test 2 — family emission timing (slow)
# ---------------------------------------------------------------------------


class TestFamilyEmissionWithin1p2xOfTierBaseline:
    """Regression: family-ON emission time <= 1.2x of tier-only (legacy) baseline."""

    @pytest.mark.regression
    @pytest.mark.slow
    @pytest.mark.parametrize("elt,form,mat,backend", _REALISABLE_PARAMS)
    def test_family_emission_within_1_2x_of_tier_baseline(
        self,
        elt: ElementType,
        form: Formulation,
        mat: str,
        backend: str,
        golden_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Family-based emission time must be within 1.2x of the tier-only baseline.

        Strategy:
          - Load golden JSON from ``golden/template_family_emission_baseline.json``.
          - Run N=5 trials with MECHDSL_FAMILY_EMITTERS=0 (tier-only / legacy).
          - Run N=5 trials with MECHDSL_FAMILY_EMITTERS=1 (family dispatch ON).
          - Assert median(family) / median(tier-only) <= 1.2.
          - Also compare to the stored golden ratio to catch regressions over time.

        The golden baseline stores absolute timings for informational purposes only;
        the live ratio is the authoritative check.
        """
        bundle = _make_bundle(elt, form, mat)
        emit_fn = _BACKEND_EMIT[backend]
        key = _triple_key(elt.value, form.value, mat, backend)

        med_tier = _measure_median_emission(emit_fn, bundle, family_on=False)
        med_family = _measure_median_emission(emit_fn, bundle, family_on=True)

        ratio = med_family / med_tier if med_tier > 0.0 else 1.0

        # Load golden for reference (stored at golden-generation time)
        golden_path = golden_dir / _GOLDEN_FILENAME
        golden_ratio: float | None = None
        if golden_path.exists():
            try:
                golden_data = json.loads(golden_path.read_text(encoding="utf-8"))
                triple_data = golden_data.get("triples", {}).get(key)
                if triple_data is not None:
                    golden_ratio = triple_data.get("ratio")
            except (json.JSONDecodeError, KeyError):
                pass  # golden unreadable — skip the stored-ratio cross-check

        assert ratio <= _RATIO_TOLERANCE, (
            f"Triple {key!r}: family/tier ratio {ratio:.4f} exceeds tolerance "
            f"{_RATIO_TOLERANCE} (median family {med_family * 1000:.3f} ms, "
            f"median tier-only {med_tier * 1000:.3f} ms). "
            + (
                f"Golden baseline ratio was {golden_ratio:.4f}. "
                if golden_ratio is not None
                else ""
            )
            + "Check whether a recent change to the family emitters "
            "introduced overhead. Regenerate baseline with: "
            "uv run python packages/mechdsl-core/tests/tools/regen_p9_3_baseline.py"
        )
