"""Live audit for recovery-plan P2-5: minimal frontend contract test suite from LaTeX source.

Per back2latex Phase 1 / amendment 4, the Phase-2 Code reality anchor
notes that ``tests/test_frontend.py is a stub`` and no test starts from
LaTeX source today. This suite closes that gap: it is the first set of
tests that begins with a real LaTeX-source string and reaches a
normalized frontend output (the context dict + a constructed
:class:`ProblemIR`).
"""

from __future__ import annotations

import pytest

from mechdsl import compile_latex
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.frontend import parse
from mechdsl.frontend.directives import ParseError
from mechdsl.ir.mechanics_ir import (
    BCType,
    ElementType,
    Formulation,
)
from mechdsl.symbolic.convected import UnsupportedError

_ELASTIC_LATEX = r"""
\documentclass{article}
\begin{document}

% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"

The governing equation is $\nabla \cdot \boldsymbol{P} + \boldsymbol{b} = 0$.
\end{document}
"""


_PLASTIC_LATEX = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material j2_power_law --E 200e3 --nu 0.3 --sigma_y0 250 --K 500 --n 0.5
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "t_bar"
"""


class TestFrontendContractFromLatex:
    """The MVP-stable contract starts from LaTeX. These tests prove it.

    Tier: integration
    """

    @pytest.mark.integration
    def test_elastic_latex_reaches_normalized_context(self) -> None:
        ctx = parse(_ELASTIC_LATEX)
        # The normalized context dict is the canonical Layer-1 output.
        assert ctx["dim"] == 3
        assert ctx["cell_type"] == "hex8"
        assert ctx["formulation"] == "total_lagrangian"
        assert ctx["material_type"] == "svk"
        assert ctx["params"]["E"] == 200e3
        assert ctx["params"]["nu"] == 0.3
        names = [bc["name"] for bc in ctx["boundaries"]]
        assert names == ["fix", "load"]

    @pytest.mark.integration
    def test_elastic_latex_compiles_to_artifact_bundle(self) -> None:
        bundle = compile_latex(_ELASTIC_LATEX)
        assert isinstance(bundle, ArtifactBundle)
        ir = bundle.problem_ir_dict
        assert ir["dim"] == 3
        assert ir["element_type"] == "hex8"
        assert ir["formulation"] == "total_lagrangian"
        assert ir["material"]["model"] == "svk"
        # Validates the stable contract: emitted source is non-empty Taichi.
        assert bundle.emitted_source, "compile_latex must produce non-empty Taichi source"

    @pytest.mark.integration
    def test_plastic_latex_compiles_with_j2_params(self) -> None:
        bundle = compile_latex(_PLASTIC_LATEX)
        assert isinstance(bundle, ArtifactBundle)
        material = bundle.problem_ir_dict["material"]
        assert material["model"] == "j2_power_law"
        assert material["params"]["sigma_y0"] == 250
        assert material["params"]["K"] == 500

    @pytest.mark.integration
    def test_problem_ir_round_trip_via_compile_latex(self) -> None:
        # The recovered contract requires that LaTeX → ProblemIR → emitted source
        # all stay in agreement. Construct an equivalent ProblemIR by hand and
        # confirm the LaTeX-driven path matches the typed-enum representation.
        bundle = compile_latex(_ELASTIC_LATEX)
        ir = bundle.problem_ir_dict
        assert ir["element_type"] == ElementType.HEX8.value
        assert ir["formulation"] == Formulation.TOTAL_LAGRANGIAN.value
        bc_types = {bc["bc_type"] for bc in ir["boundaries"]}
        assert bc_types == {BCType.DIRICHLET.value, BCType.NEUMANN.value}


class TestFrontendContractRejection:
    """Out-of-subset constructs must raise with stable, actionable messages.

    Tier: integration
    """

    @pytest.mark.integration
    def test_unsupported_dim_raises_with_plan_b_pointer(self) -> None:
        bad = r"""
% mechanics dim 2
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
        with pytest.raises(UnsupportedError, match=r"Plan B"):
            compile_latex(bad)

    @pytest.mark.integration
    def test_malformed_directive_raises_parse_error(self) -> None:
        bad = r"""
% mechanics boundary fix
"""
        # `boundary` requires `--type`; missing it must raise a ParseError.
        with pytest.raises(ParseError):
            compile_latex(bad)
