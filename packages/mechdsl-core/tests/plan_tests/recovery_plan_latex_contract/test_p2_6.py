"""Live audit for recovery-plan P2-6: contract-level errors from the canonical façade.

Per recovery R1.6, frontend failures must produce contract-level errors
(``ParseError`` for malformed LaTeX, ``UnsupportedError`` for out-of-subset
constructs) with stable messages and Plan B / recovery-plan phase pointers
where relevant. These tests exercise the canonical entry point
:func:`mechdsl.compile_latex` and assert on the error type + message
shape — *not* on internal parser details — so the contract surface is
what's covered.
"""

from __future__ import annotations

import pytest

from mechdsl import compile_latex
from mechdsl.frontend.directives import ParseError
from mechdsl.symbolic.convected import UnsupportedError

# ---------------------------------------------------------------------------
# Out-of-subset constructs (must raise UnsupportedError with a phase pointer)
# ---------------------------------------------------------------------------


class TestUnsupportedConstructs:
    """Constructs outside the MVP-supported subset must raise ``UnsupportedError``."""

    @pytest.mark.integration
    def test_dim_2_raises_with_plan_b_pointer(self) -> None:
        with pytest.raises(UnsupportedError, match=r"Plan B phase B2"):
            compile_latex(
                r"""
% mechanics dim 2
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )

    @pytest.mark.integration
    def test_unsupported_material_raises_with_plan_b_pointer(self) -> None:
        with pytest.raises(UnsupportedError) as excinfo:
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material moonshine --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )
        msg = str(excinfo.value)
        assert "moonshine" in msg, "error must echo the offending material name"
        assert "supported models" in msg, (
            "error must list the supported set so users can self-correct"
        )

    @pytest.mark.integration
    def test_unsupported_formulation_raises(self) -> None:
        with pytest.raises(UnsupportedError, match=r"formulation"):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation eulerian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )

    @pytest.mark.integration
    def test_unsupported_coord_system_raises_with_plan_b_pointer(self) -> None:
        # The frontend handler doesn't accept `--coord_system spherical`; the
        # build_context validator rejects it with a Plan B B2 pointer.
        # We reach the validator by passing through build_context directly,
        # since the directive parser itself only sets `coord_system="cartesian"`.
        from mechdsl.frontend import build_context

        with pytest.raises(UnsupportedError, match=r"Plan B phase B2"):
            build_context(
                dim=3,
                cell_type="hex8",
                formulation="total_lagrangian",
                material_type="svk",
                params={"E": 200e3, "nu": 0.3},
                boundaries=[{"name": "fix", "type": "dirichlet", "value": 0.0}],
                coord_system="spherical",
            )


# ---------------------------------------------------------------------------
# Malformed LaTeX (must raise ParseError, not crash the pipeline)
# ---------------------------------------------------------------------------


class TestMalformedLatex:
    """Syntactically broken ``% mechanics`` directives must raise ``ParseError``."""

    @pytest.mark.integration
    def test_boundary_missing_required_type_option_raises(self) -> None:
        with pytest.raises(ParseError, match=r"--type"):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix
"""
            )

    @pytest.mark.integration
    def test_boundary_too_many_positional_args_raises(self) -> None:
        with pytest.raises(ParseError, match=r"positional"):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix extra --type dirichlet --value 0
"""
            )

    @pytest.mark.integration
    def test_unknown_directive_raises(self) -> None:
        # `% mechanics nonsense` is not in the handler set.
        with pytest.raises(ParseError):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics nonsense foo --bar baz
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )

    @pytest.mark.integration
    def test_deferred_directive_rejected_with_plan_b_pointer(self) -> None:
        # `field`, `weak_form`, `constitutive`, `codegen`, `verify` are all
        # documented in 02-LATEX-DSL.md but not part of the MVP subset.
        with pytest.raises(ParseError) as excinfo:
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics field u --type vector
% mechanics boundary fix --type dirichlet --value 0
"""
            )
        msg = str(excinfo.value)
        assert "Plan B" in msg or "deferred" in msg.lower(), (
            "deferred-directive rejection must mention Plan B or 'deferred' so "
            "users know the construct is planned, not unknown"
        )


# ---------------------------------------------------------------------------
# Index semantics (recovery R1.6 calls out invalid index typing)
# ---------------------------------------------------------------------------


class TestIndexSemantics:
    """Index-typing errors must surface as ``ParseError`` with stable messages."""

    @pytest.mark.integration
    def test_unknown_index_family_raises(self) -> None:
        with pytest.raises(ParseError, match=r"index"):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics index unknown_family i j k
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )


# ---------------------------------------------------------------------------
# Stable-message contract: every recovery error must mention something a
# user can act on.
# ---------------------------------------------------------------------------


class TestStableMessageContract:
    """Failure messages must echo the offending construct so users can self-correct."""

    @pytest.mark.integration
    def test_unsupported_material_message_includes_offender_and_remedy(self) -> None:
        with pytest.raises(UnsupportedError) as excinfo:
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material foobar --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
"""
            )
        msg = str(excinfo.value)
        assert "foobar" in msg, "message must echo the offending material name"
        # Either a phase pointer or a list of supported alternatives counts as a remedy.
        assert "Plan B" in msg or "supported models" in msg, (
            "message must point users at either a phase or a list of accepted values"
        )
