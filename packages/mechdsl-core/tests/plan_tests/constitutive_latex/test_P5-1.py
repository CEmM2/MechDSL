"""Tests for Task P5-1: fiber-direction per-element field-data plumbing.

A ``% mechanics fiber --family "x, y, z"`` directive declares fiber direction(s)
as per-element FIELD data (distinct from scalar ``% mechanics material`` params),
which flows frontend -> ProblemIR.fiber_field (a FiberFieldSpec) -> ElementIR
.fiber_field with no layer bypass. Malformed declarations reject with a
line-numbered, phase-pointed message; the carry is immutable and validated at
construction.

``build_context(fiber_data=...)`` (programmatic) + the HGO-requires-fiber gate
already existed; P5-1 adds the LaTeX *directive* and the ProblemIR/Element IR
field-data carry.

Acceptance criteria:
- AC-1: Fiber direction(s) parse as per-element field data, distinct from scalar params.
- AC-2: Field data flows frontend -> ProblemIR -> Element IR (no layer bypass).
- AC-3: Malformed fiber declaration rejects with line number + phase pointer.
- AC-4: IR immutability + construction-time validation preserved.
"""

from __future__ import annotations

import dataclasses

import pytest

from mechdsl.frontend.directives import ParseError
from mechdsl.frontend.parser import parse
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    FiberFieldSpec,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise


def _hgo_source(*fiber_lines: str) -> str:
    """A minimal HGO LaTeX problem with the given `% mechanics fiber` lines."""
    head = (
        "% mechanics dim 3\n"
        "% mechanics cell hex8\n"
        "% mechanics formulation total_lagrangian\n"
        "% mechanics material hgo --mu 1.0 --k1 1.0 --k2 1.0 --kappa 100.0 "
        "--fiber_dispersion 0.0\n"
        '% mechanics boundary fix --type dirichlet --components "0 1 2"\n'
        "% mechanics boundary load --type neumann --traction t_bar\n"
    )
    return head + "".join(line if line.endswith("\n") else line + "\n" for line in fiber_lines)


class TestTaskP5_1:
    """Tests for Task P5-1: fiber-direction per-element field-data plumbing.
    AC covered: 1, 2, 3, 4."""

    # ------------------------------------------------------------------
    # AC-1: the directive parses to per-element field data, distinct from params
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_fiber_directive_parses_to_per_element_data(self):
        """Verifies: `% mechanics fiber --family` parses to fiber field data on
        ProblemIR.fiber_field (a FiberFieldSpec), distinct from MaterialSpec.params.
        AC: AC-1.
        Passes when: two fiber families round-trip into FiberFieldSpec.families and
        the directions are NOT present in material.params."""
        ctx = parse(
            _hgo_source(
                '% mechanics fiber --family "1, 0, 0"', '% mechanics fiber --family "0, 1, 0"'
            )
        )
        assert ctx["fiber_families"][0]["direction"] == (1.0, 0.0, 0.0)
        assert ctx["fiber_families"][1]["direction"] == (0.0, 1.0, 0.0)

        ir = ProblemIR.from_context(ctx)
        assert isinstance(ir.fiber_field, FiberFieldSpec)
        assert ir.fiber_field.families == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        assert ir.fiber_field.n_families == 2
        # Field data, NOT a scalar material param.
        assert "family" not in ir.material.params
        assert all(not isinstance(v, tuple) for v in ir.material.params.values())

    # ------------------------------------------------------------------
    # AC-2: field data flows frontend -> ProblemIR -> Element IR (no bypass)
    # ------------------------------------------------------------------

    @pytest.mark.integration
    def test_fiber_data_flows_problemir_to_element_ir(self):
        """Verifies: fiber field data flows frontend -> ProblemIR -> Element IR.
        AC: AC-2.
        Passes when: localise(ir).element_ir.fiber_field equals the declared
        family directions (lossless, no layer bypass)."""
        ctx = parse(
            _hgo_source(
                '% mechanics fiber --family "1, 0, 0"', '% mechanics fiber --family "0, 1, 0"'
            )
        )
        ir = ProblemIR.from_context(ctx)
        result = localise(ir)
        assert result.element_ir.fiber_field == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))

    @pytest.mark.unit
    def test_isotropic_problem_has_no_fiber_field(self):
        """Verifies: a problem with no fiber directive carries fiber_field=None
        through ProblemIR and Element IR (isotropic path unaffected).
        AC: AC-2 (negative case)."""
        ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
            boundaries=(
                BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
            ),
        )
        assert ir.fiber_field is None
        assert localise(ir).element_ir.fiber_field is None

    # ------------------------------------------------------------------
    # AC-3: malformed fiber declaration rejects with line number + phase pointer
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_malformed_fiber_wrong_length_rejected(self):
        """Verifies: a fiber family with != 3 components rejects with a line number.
        AC: AC-3."""
        with pytest.raises(ParseError, match=r"line \d+.*exactly 3 components"):
            parse(_hgo_source('% mechanics fiber --family "1, 0"'))

    @pytest.mark.unit
    def test_malformed_fiber_nonnumeric_rejected(self):
        """Verifies: a non-numeric fiber family rejects with a line number.
        AC: AC-3."""
        with pytest.raises(ParseError, match=r"line \d+.*numeric 3-vector"):
            parse(_hgo_source('% mechanics fiber --family "1, x, 0"'))

    @pytest.mark.unit
    def test_missing_family_option_rejected_with_phase_pointer(self):
        """Verifies: `% mechanics fiber` without --family rejects with a phase
        pointer (P5-1).
        AC: AC-3."""
        with pytest.raises(ParseError, match=r"requires --family.*P5-1"):
            parse(_hgo_source("% mechanics fiber"))

    @pytest.mark.unit
    def test_zero_direction_rejected(self):
        """Verifies: a zero fiber direction rejects (not a valid direction).
        AC: AC-3."""
        with pytest.raises(ParseError, match=r"nonzero direction"):
            parse(_hgo_source('% mechanics fiber --family "0, 0, 0"'))

    # ------------------------------------------------------------------
    # AC-4: IR immutability + construction-time validation
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_fiber_field_spec_is_immutable_and_validated(self):
        """Verifies: FiberFieldSpec is frozen and validates its families at
        construction (nonzero 3-vectors).
        AC: AC-4."""
        spec = FiberFieldSpec(families=((1.0, 0.0, 0.0),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.families = ((0.0, 1.0, 0.0),)  # type: ignore[misc]

        with pytest.raises(ValueError, match="3-vector"):
            FiberFieldSpec(families=((1.0, 0.0),))  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="nonzero"):
            FiberFieldSpec(families=((0.0, 0.0, 0.0),))
        with pytest.raises(ValueError, match="at least one fiber family"):
            FiberFieldSpec(families=())

    @pytest.mark.unit
    def test_fiber_field_round_trips_through_serialization(self):
        """Verifies: a ProblemIR carrying fiber_field serialises and rebuilds it
        (and a fiber-less IR omits the key, keeping legacy goldens byte-identical).
        AC: AC-4 (immutability/validation preserved across round-trip)."""
        ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="hgo", params={"mu": 1.0}),
            boundaries=(
                BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
            ),
            fiber_field=FiberFieldSpec(families=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))),
        )
        d = ir.to_dict()
        assert d["fiber_field"] == {"families": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]}
        rebuilt = ProblemIR.from_dict(d)
        assert rebuilt.fiber_field == ir.fiber_field

        # Fiber-less IR: the key is omitted (golden stability).
        iso = ProblemIR.from_dict({k: v for k, v in d.items() if k != "fiber_field"})
        assert iso.fiber_field is None
        assert "fiber_field" not in iso.to_dict()
