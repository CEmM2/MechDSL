"""Live audit for recovery-plan P3-2: compatibility constructors / adapters.

P3-2 promotes the previously-private ``_problem_ir_from_context`` adapter
to a first-class :meth:`ProblemIR.from_context` classmethod, with a sibling
:meth:`BoundaryCondition.from_context` for the boundary subschema. Three
private duplicates (in ``mechdsl/__init__.py``, ``test_full_pipeline.py``,
``test_formulation_switching.py``) are retired in the same change.

These tests verify:

1. The classmethods exist and adapt every documented context-dict shape
   (canonical ``name`` / legacy ``region`` / face-tagged ``face`` /
   missing-name fallback) into an equivalent :class:`ProblemIR`.
2. The legacy private symbol ``_problem_ir_from_context`` is gone from
   :mod:`mechdsl` (so re-introducing it is a discoverable regression).
3. The end-to-end :func:`compile_latex` pipeline still works after the
   refactor (the user-visible behaviour is unchanged).
4. The adapter accepts optional context keys (``params``, ``traction``)
   without breaking when omitted.
"""

from __future__ import annotations

from typing import Any

import pytest

from mechdsl import compile_latex
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.frontend import build_context
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    ProblemIR,
)


def _mvp_context(**overrides: Any) -> dict[str, Any]:
    """Build a canonical MVP context dict that downstream tests can perturb."""
    base: dict[str, Any] = dict(
        dim=3,
        cell_type="hex8",
        formulation="total_lagrangian",
        material_type="svk",
        params={"E": 200e3, "nu": 0.3},
        boundaries=[
            {"name": "fix", "type": "dirichlet", "value": 0.0, "components": [0, 1, 2]},
            {"name": "load", "type": "neumann", "traction": "t_bar"},
        ],
    )
    base.update(overrides)
    return base


class TestProblemIRFromContext:
    """`ProblemIR.from_context` is the canonical context-dict adapter."""

    @pytest.mark.unit
    def test_classmethod_exists(self) -> None:
        # Sanity guard against a refactor that silently retires the API.
        assert hasattr(ProblemIR, "from_context")
        assert callable(ProblemIR.from_context)

    @pytest.mark.unit
    def test_canonical_context_round_trips_to_ir(self) -> None:
        ctx = _mvp_context()
        ir = ProblemIR.from_context(ctx)
        assert ir.dim == 3
        assert ir.formulation is Formulation.TOTAL_LAGRANGIAN
        assert ir.element_type is ElementType.HEX8
        assert ir.material.model == "svk"
        assert ir.material.params == {"E": 200e3, "nu": 0.3}
        assert len(ir.boundaries) == 2
        assert ir.boundaries[0].name == "fix"
        assert ir.boundaries[0].bc_type is BCType.DIRICHLET
        assert ir.boundaries[1].name == "load"
        assert ir.boundaries[1].bc_type is BCType.NEUMANN
        assert ir.boundaries[1].traction == "t_bar"

    @pytest.mark.unit
    def test_omitted_params_default_to_empty_dict(self) -> None:
        # The MVP context emitted by build_context always carries `params`,
        # but third-party callers may construct context dicts directly. The
        # adapter must default the optional key to an empty dict (the IR's
        # P3-5 validation surfaces the missing-required-params error from
        # there — that's a separate failure mode from this test).
        ctx = _mvp_context()
        ctx.pop("params")
        # Use a model that does not have required params in the MVP table so
        # this test isolates the adapter behaviour from the P3-5 validation.
        ctx["material_type"] = "neo_hookean"
        ir = ProblemIR.from_context(ctx)
        assert ir.material.params == {}

    @pytest.mark.unit
    def test_build_context_output_round_trips(self) -> None:
        # `build_context` is the documented programmatic entry point; its
        # output must be directly usable by `from_context`. This guards
        # against a future schema drift between the two helpers.
        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params={"E": 200.0e3, "nu": 0.3},
            boundaries=[
                {"name": "fix", "face": "x0", "type": "dirichlet", "dofs": [0, 1, 2]},
                {"name": "load", "face": "x1", "type": "neumann", "traction": "t_bar"},
            ],
        )
        ir = ProblemIR.from_context(ctx)
        assert ir.boundaries[0].components == (0, 1, 2)


class TestBoundaryConditionFromContext:
    """`BoundaryCondition.from_context` covers all three name shapes."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name_keys, expected",
        [
            ({"name": "fix"}, "fix"),
            ({"region": "Omega_d"}, "Omega_d"),
            ({"face": "x0"}, "x0"),
            ({}, "bc_3"),  # fallback uses the index parameter
        ],
    )
    def test_name_priority_chain(self, name_keys: dict[str, Any], expected: str) -> None:
        raw: dict[str, Any] = {"type": "dirichlet"}
        raw.update(name_keys)
        bc = BoundaryCondition.from_context(raw, index=3)
        assert bc.name == expected

    @pytest.mark.unit
    def test_dofs_alias_components(self) -> None:
        # Frontend dicts emitted by older codepaths use `dofs`, not the
        # canonical `components`. The adapter accepts both.
        bc = BoundaryCondition.from_context({"name": "fix", "type": "dirichlet", "dofs": [0, 2]})
        assert bc.components == (0, 2)

    @pytest.mark.unit
    def test_components_takes_priority_over_dofs(self) -> None:
        # If both keys are present, `components` wins (it is the canonical
        # name introduced by P1-1).
        bc = BoundaryCondition.from_context(
            {"name": "fix", "type": "dirichlet", "components": [1], "dofs": [0, 2]}
        )
        assert bc.components == (1,)

    @pytest.mark.unit
    def test_optional_keys_default_correctly(self) -> None:
        # post_recovery_plan P1-1 requires Neumann BCs to carry a traction
        # spec; default-construction now uses Dirichlet so unrelated
        # default-handling assertions still apply.
        bc = BoundaryCondition.from_context({"name": "fix", "type": "dirichlet"})
        assert bc.field_name == "u"
        assert bc.value == 0.0
        assert bc.traction is None
        assert bc.components == (0, 1, 2)

    @pytest.mark.unit
    def test_neumann_without_traction_rejected_post_p1_1(self) -> None:
        # post_recovery_plan P1-1 added validation that rejects Neumann BCs
        # missing a traction. from_context surfaces the same error.
        with pytest.raises(ValueError, match="post_recovery_plan Phase 1"):
            BoundaryCondition.from_context({"name": "load", "type": "neumann"})


class TestPrivateDuplicatesRetired:
    """The three pre-P3-2 private adapters must be gone."""

    @pytest.mark.unit
    def test_mechdsl_module_no_longer_exposes_private_helper(self) -> None:
        import mechdsl

        assert not hasattr(mechdsl, "_problem_ir_from_context"), (
            "P3-2 retired the private `_problem_ir_from_context` helper in "
            "favour of `ProblemIR.from_context`. Re-introducing it would "
            "split the canonical adapter again — extend the classmethod "
            "instead."
        )

    @pytest.mark.unit
    def test_test_modules_no_longer_define_private_helpers(self) -> None:
        # The two pre-existing test files duplicated the adapter logic
        # because there was no canonical home. After P3-2, that home exists
        # — so the duplicates must be removed.
        from tests import test_formulation_switching, test_full_pipeline

        assert not hasattr(test_full_pipeline, "_problem_ir_from_context")
        assert not hasattr(test_full_pipeline, "_boundary_condition_from_context")
        assert not hasattr(test_formulation_switching, "_boundary_condition_from_context")


class TestCompileLatexEndToEndStillWorks:
    """The user-visible `compile_latex` pipeline must be unchanged after P3-2."""

    @pytest.mark.integration
    def test_compile_latex_end_to_end_returns_artifact_bundle(self) -> None:
        source = """
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""
        bundle = compile_latex(source)
        assert isinstance(bundle, ArtifactBundle)
        # The IR carried inside the bundle came from `ProblemIR.from_context`
        # — its acceptance is the integration check that P3-2's refactor did
        # not silently drift from the pre-P3-2 path.
        assert bundle.problem_ir_dict["element_type"] == ElementType.HEX8.value
        assert bundle.problem_ir_dict["material"]["model"] == "svk"
