"""Tests for Phase 1, Task P1-T4: fe_localise model string validation.

Verifies that localise() validates material model strings against
known ConstitutiveModel subclasses.
"""

from __future__ import annotations

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise


def _make_problem(model: str = "svk", **params: float) -> ProblemIR:
    """Build a minimal valid ProblemIR for the given material model string."""
    default_params: dict[str, float] = {"E": 200e3, "nu": 0.3}
    if model == "j2_power_law":
        default_params.update({"sigma_y0": 250.0, "K": 500.0, "n": 1.0})
    default_params.update(params)
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model=model, params=default_params),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )


class TestModelStringValidation:
    """Tests for Task P1-T4: Update fe_localise model validation.

    Acceptance criteria covered: valid model strings accepted,
    unknown model string raises error.
    """

    def test_svk_model_string_accepted(self):
        """Verifies: localise() accepts 'svk' material model string.

        Acceptance criterion: localise() still works for 'svk' and 'j2_power_law' model strings
        Passes when: localise(problem_ir_with_svk) succeeds without error.
        """
        problem = _make_problem(model="svk")
        result = localise(problem)
        assert result.problem_ir.material.model == "svk"

    def test_j2_model_string_accepted(self):
        """Verifies: localise() accepts 'j2_power_law' material model string.

        Acceptance criterion: localise() still works for 'svk' and 'j2_power_law' model strings
        Passes when: localise(problem_ir_with_j2) succeeds without error.
        """
        problem = _make_problem(model="j2_power_law")
        result = localise(problem)
        assert result.problem_ir.material.model == "j2_power_law"

    def test_unknown_model_string_raises_error(self):
        """Verifies: unknown material model strings are rejected with a ValueError.

        Acceptance criterion: Unknown model string raises appropriate error
        Passes when: constructing ProblemIR with model='unknown' raises ValueError
        (ProblemIR.__post_init__ validates the model field before localise() is called).
        """
        with pytest.raises(ValueError, match="Unknown material model"):
            _make_problem(model="unknown")
