"""Live audit for recovery-plan P2-1: introduce the ``compile_latex`` façade.

Asserts that ``mechdsl.compile_latex`` is importable, has the canonical
signature, accepts a minimal LaTeX source, and produces an
:class:`ArtifactBundle` with the right MVP enums baked in.
"""

from __future__ import annotations

import inspect

import pytest

from mechdsl import compile, compile_latex
from mechdsl.codegen.artifact import ArtifactBundle

_MVP_LATEX = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""


class TestTaskP2_1:
    """
    Tests for Task P2-1: Introduce a canonical ``compile_latex`` façade.
    Tier: unit
    """

    @pytest.mark.unit
    def test_compile_latex_exported_from_mechdsl(self) -> None:
        import mechdsl

        assert hasattr(mechdsl, "compile_latex"), (
            "mechdsl must export compile_latex as a public symbol"
        )
        assert "compile_latex" in mechdsl.__all__, "compile_latex must be listed in mechdsl.__all__"
        # The legacy programmatic API must remain available.
        assert hasattr(mechdsl, "compile"), "mechdsl.compile must remain exported"
        assert mechdsl.compile is compile

    @pytest.mark.unit
    def test_signature_matches_canonical_form(self) -> None:
        sig = inspect.signature(compile_latex)
        params = list(sig.parameters.values())
        assert [p.name for p in params] == ["source", "profile"], (
            f"unexpected parameter list: {[p.name for p in params]}"
        )
        # `source` must be positional, `profile` must default to "mvp"
        source_param = sig.parameters["source"]
        profile_param = sig.parameters["profile"]
        assert source_param.default is inspect.Parameter.empty
        assert profile_param.default == "mvp"

    @pytest.mark.unit
    def test_smoke_compile_latex_returns_artifact_bundle(self) -> None:
        bundle = compile_latex(_MVP_LATEX)
        assert isinstance(bundle, ArtifactBundle), (
            f"expected ArtifactBundle, got {type(bundle).__name__}"
        )
        # The MVP enums must round-trip through the bundle's serialisable view.
        ir_dict = bundle.problem_ir_dict
        assert ir_dict["dim"] == 3
        assert ir_dict["formulation"] == "total_lagrangian"
        assert ir_dict["element_type"] == "hex8"
        assert ir_dict["material"]["model"] == "svk"
        assert any(bc["bc_type"] == "dirichlet" for bc in ir_dict["boundaries"])
        assert any(bc["bc_type"] == "neumann" for bc in ir_dict["boundaries"])

    @pytest.mark.unit
    def test_non_mvp_profile_rejected(self) -> None:
        with pytest.raises(ValueError, match="profile="):
            compile_latex(_MVP_LATEX, profile="experimental")
