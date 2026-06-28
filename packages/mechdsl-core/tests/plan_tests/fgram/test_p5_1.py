"""Focused fgram Phase 5 P5-1 coverage: LaTeX semantics to Mechanics IR."""

from __future__ import annotations

import json

import pytest

from mechdsl.frontend import parse, parse_with_math
from mechdsl.ir.mechanics_ir import (
    ElementType,
    Formulation,
    ProblemIR,
    ResidualContract,
)

# A directive-only LaTeX source carrying fields, a constitutive role, weak-form
# (residual) metadata, and both a Dirichlet and a Neumann boundary. This is the
# canonical "what the compiler understood" input for P5-1.
_LATEX_SOURCE = r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics field u --type vector --space H1 --order 1
% mechanics constitutive Psi --strain_energy
% mechanics constitutive S --pk2
% mechanics weak_form internal_residual --residual
% mechanics bc dirichlet --boundary fix_base --value 0.0
% mechanics bc neumann --boundary load_top --traction "0 0 -1000"
"""

# The same directive core plus a real ``$...$`` math block whose equation the
# math parser classifies as an auxiliary definition (LHS symbol ``A`` is not a
# recognised constitutive symbol and no directive keyword surrounds it). This
# drives the equation path through the *real* frontend (``parse_with_math``),
# not a hand-built ``ctx["math"]`` shape.
_LATEX_SOURCE_WITH_MATH = _LATEX_SOURCE + (
    "% declare FUU --dim 3\n% declare AUU --dim 3\n$A^{i I} = F^{i I}$\n"
)


class TestTaskP5_1:
    """Tests for Task P5-1: LaTeX semantics to Mechanics IR. AC covered: 1, 2."""

    @pytest.mark.integration
    def test_latex_semantics_constructs_mvp_stable_problem_ir(self) -> None:
        """Verifies: LaTeX with fields, constitutive equations, weak-form metadata,
        and BCs constructs a valid MVP-stable ProblemIR via the LaTeX-semantic
        constructor. AC: A LaTeX source ... constructs a valid MVP-stable ProblemIR.
        Passes when: from_latex_semantics (or equivalent adapter) returns a ProblemIR
        that passes MVP-subset validation."""
        ctx = parse(_LATEX_SOURCE)
        ir = ProblemIR.from_latex_semantics(ctx)

        # Core MVP-stable configuration is honoured.
        assert ir.dim == 3
        assert ir.formulation is Formulation.TOTAL_LAGRANGIAN
        assert ir.element_type is ElementType.HEX8
        assert ir.material.model == "svk"
        assert ir.is_mvp_stable()
        ir.assert_mvp_stable()  # must not raise

        # LaTeX-derived fields became FieldSpec entries.
        assert tuple(f.name for f in ir.fields) == ("u",)
        assert ir.fields[0].kind == "vector"

        # Weak-form (residual) declaration became a ResidualContract.
        assert isinstance(ir.residual_contract, ResidualContract)
        assert ir.residual_contract.weak_form_label == "internal_residual"

        # Both boundaries flowed through.
        assert {bc.name for bc in ir.boundaries} == {"fix_base", "load_top"}

        # Convergence: from_latex_semantics and from_context agree on the
        # MVP-stable core (the LaTeX path only *adds* enrichment).
        core = ProblemIR.from_context(ctx)
        assert ir.dim == core.dim
        assert ir.formulation == core.formulation
        assert ir.element_type == core.element_type
        assert ir.material.model == core.material.model
        assert {bc.name for bc in ir.boundaries} == {bc.name for bc in core.boundaries}

    @pytest.mark.integration
    def test_serialized_ir_records_source_semantic_metadata(self) -> None:
        """Verifies: the serialized ProblemIR exposes enough LaTeX-derived semantic
        source data to explain what the compiler understood. AC: The serialized
        ProblemIR records enough semantic source data. Passes when: to_dict output
        includes the LaTeX-derived semantic metadata for review and golden diffs."""
        ctx = parse(_LATEX_SOURCE)
        ir = ProblemIR.from_latex_semantics(ctx)
        d = ir.to_dict()

        # to_dict stays JSON-primitive and round-trip-safe.
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

        # The serialized IR carries the LaTeX-derived semantic record.
        assert "latex_semantics" in d
        semantics = d["latex_semantics"]
        assert semantics is not None

        # Constitutive roles the compiler understood are recorded by symbol.
        constitutive = {entry["symbol"]: entry["role"] for entry in semantics["constitutive"]}
        assert constitutive == {"Psi": "strain_energy", "S": "pk2"}

        # The declared fields and the weak-form label are recorded too.
        assert "u" in semantics["fields"]
        assert semantics["weak_form_label"] == "internal_residual"

        # Round-trips losslessly through from_dict back to a serialized form.
        restored = ProblemIR.from_dict(json.loads(json_str))
        assert restored.to_dict() == d

    @pytest.mark.integration
    def test_real_math_block_populates_equation_semantics(self) -> None:
        """The real frontend (``parse_with_math``) populates ``ctx['math']['equations']``
        from a ``$...$`` block, and ``from_latex_semantics`` reads that real key —
        no hand-built ctx/math shape. Confirms the end-to-end plumbing of P5-1."""
        ctx = parse_with_math(_LATEX_SOURCE_WITH_MATH)
        # The frontend actually emits the equation semantics under the real key.
        assert "math" in ctx
        assert ctx["math"]["equations"], "parse_with_math must populate math['equations']"

        ir = ProblemIR.from_latex_semantics(ctx)
        equations = ir.to_dict()["latex_semantics"]["equations"]
        roles = {e["lhs"]: e["role"] for e in equations}
        # The auxiliary-definition role (no committed physics) is recorded as
        # ``auxiliary`` — never inferred into a real constitutive role. Per the
        # Phase 4 handoff, ``unknown`` / ``None`` are downgraded the same way.
        assert "A^{i I}" in roles
        assert roles["A^{i I}"] == "auxiliary"

    @pytest.mark.integration
    def test_unknown_role_is_treated_as_auxiliary_not_inferred(self) -> None:
        """Heeds the Phase 4 handoff: a role of ``unknown`` / ``None`` must not be
        inferred into a constitutive role; it is recorded as auxiliary. Drives the
        downgrade through real ``parse_with_math`` output rather than a synthetic
        ctx/math shape — the equation classifier labels ``A^{i I} = F^{i I}`` as a
        non-committed (auxiliary) definition."""
        ctx = parse_with_math(_LATEX_SOURCE_WITH_MATH)
        # The real classifier produced a non-committed role for this equation.
        raw_roles = {eq["lhs"]: eq["role"] for eq in ctx["math"]["equations"]}
        assert raw_roles["A^{i I}"] in {"unknown", "auxiliary_definition", None, ""}

        ir = ProblemIR.from_latex_semantics(ctx)
        equations = ir.to_dict()["latex_semantics"]["equations"]
        roles = {e["lhs"]: e["role"] for e in equations}
        # Non-committed role is downgraded to auxiliary — never promoted.
        assert roles["A^{i I}"] == "auxiliary"
