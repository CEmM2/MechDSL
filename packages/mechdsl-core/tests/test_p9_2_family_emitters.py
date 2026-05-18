"""Test stubs for Task P9-2: Refactor einsum_optimizer to emit via template families.

Regression-tier tests: the refactor must not change semantics. Emitted source
may differ in whitespace/helper structure but must produce identical numerical
results. Golden files and cross-backend equivalence tests are the guards.
"""

from __future__ import annotations

import os
import re
from unittest import mock

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.einsum_optimizer import (
    ContractionResult,
    family_emitters_enabled,
    optimize_contraction,
)
from mechdsl.codegen.family_registry import Family
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


def _make_svk_cantilever_bundle() -> ArtifactBundle:
    """Construct the MVP SVK cantilever bundle used as the P9-2 baseline."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="svk",
            params={"E": 200e3, "nu": 0.3},
        ),
        boundaries=(BoundaryCondition(name="fix_root", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


_WHITESPACE_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Collapse whitespace runs so equivalence tests tolerate formatting drift."""
    return _WHITESPACE_RE.sub(" ", text).strip()


class TestTaskP9_2:
    """
    Tests for Task P9-2: Refactor einsum_optimizer to emit via template families.

    Acceptance criteria covered:
      1. All existing contractions classify into a family.
      2. Taichi printer produces equivalent (whitespace-different ok) source before/after.
      3. No semantic regressions (cross-backend equivalence from P8-3 still passes).
      4. Golden files updated and reviewed.
    """

    @pytest.mark.regression
    def test_all_contractions_classified_into_family(self) -> None:
        """
        Verifies: every call to `optimize_contraction` in the codegen pipeline returns
        a ContractionResult whose `family` field is a valid Family enum value, and
        the derived ContractionPlans round-trip the family name.

        Acceptance criterion: All existing contractions classify into a family.
        """
        bundle = _make_svk_cantilever_bundle()
        assert bundle.contraction_plans, "SVK bundle produced no contraction plans"

        valid_family_names = {f.name for f in Family}
        for plan in bundle.contraction_plans:
            assert isinstance(plan.family, str)
            assert plan.family in valid_family_names, (
                f"plan.family {plan.family!r} is not a valid Family enum name; "
                f"expected one of {sorted(valid_family_names)}"
            )

        # Direct smoke: optimize a minimal einsum and confirm Family instance.
        result: ContractionResult = optimize_contraction("ij,jk->ik", [(3, 3), (3, 3)])
        assert isinstance(result.family, Family)

    @pytest.mark.regression
    @pytest.mark.slow
    def test_taichi_emission_numerically_equivalent_after_refactor(self) -> None:
        """
        Verifies: Taichi emission via family_emitters produces source that is
        byte-identical (or whitespace-equivalent) to the legacy tier-only path
        on the MVP reference benchmark (Hex8 SVK cantilever).

        The P9-2 dispatch wraps the legacy inline bodies, so flag-ON and
        flag-OFF should emit identical Taichi source. We assert that here and
        rely on the broader golden-regression suite (``test_e2e_taichi.py``
        and friends) for numerical correctness under the default (flag-ON)
        path.
        """
        bundle = _make_svk_cantilever_bundle()

        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "1"}):
            assert family_emitters_enabled() is True
            source_on = taichi_emit(bundle)

        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "0"}):
            assert family_emitters_enabled() is False
            source_off = taichi_emit(bundle)

        assert _normalise(source_on) == _normalise(source_off), (
            "Taichi emission differs between family-emitter ON and OFF paths "
            "beyond whitespace; the dispatch helpers must preserve legacy "
            "byte-identical output."
        )

    @pytest.mark.regression
    def test_mfem_emission_equivalent_after_refactor(self) -> None:
        """
        Verifies: MFEM printer output under the family-emitter path is
        whitespace-equivalent to the legacy path.

        Acceptance criterion: No semantic regressions.
        """
        bundle = _make_svk_cantilever_bundle()

        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "1"}):
            output_on = mfem_emit(bundle)
        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "0"}):
            output_off = mfem_emit(bundle)

        assert _normalise(output_on) == _normalise(output_off), (
            "MFEM emission differs between family-emitter ON and OFF paths; "
            "dispatch helpers must preserve legacy output."
        )

    @pytest.mark.regression
    def test_moose_emission_equivalent_after_refactor(self) -> None:
        """
        Verifies: MOOSE printer output under the family-emitter path is
        whitespace-equivalent to the legacy path on the SVK cantilever bundle.
        """
        bundle = _make_svk_cantilever_bundle()

        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "1"}):
            output_on = moose_emit(bundle)
        with mock.patch.dict(os.environ, {"MECHDSL_FAMILY_EMITTERS": "0"}):
            output_off = moose_emit(bundle)

        assert set(output_on.keys()) == set(output_off.keys())
        for key in output_on:
            assert _normalise(output_on[key]) == _normalise(output_off[key]), (
                f"MOOSE emission for key {key!r} differs between family-emitter "
                "ON and OFF paths; dispatch helpers must preserve legacy output."
            )
