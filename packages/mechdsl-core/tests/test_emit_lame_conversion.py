"""Tests for emit_main E/nu → Lamé parameter conversion (Sprint 2, Phase 1, Tasks P1-T1 / P1-T6).

Verifies that when ProblemIR stores E/nu instead of pre-computed lam/mu,
the emitted __main__ block contains correct Lame parameters:
  lam = E*nu/((1+nu)*(1-2*nu))
  mu = E/(2*(1+nu))
"""

from __future__ import annotations

import re

import pytest

from mechdsl.codegen import compile
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)

pytestmark = pytest.mark.stable_backend


def _make_problem(material_params: dict) -> ProblemIR:
    """Construct a minimal ProblemIR with given material params."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params=material_params),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )


def _make_j2_problem(material_params: dict) -> ProblemIR:
    """Construct a minimal ProblemIR with J2 material and given params."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="j2_power_law", params=material_params),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )


def _parse_float_assignment(source: str, var_name: str) -> float:
    """Extract the float value from a ``var_name = <number>`` line in source."""
    match = re.search(rf"{re.escape(var_name)}\s*=\s*([\d.e+\-]+)", source)
    assert match is not None, f"Could not find '{var_name} = ...' in emitted source"
    return float(match.group(1))


class TestEmitMainLameConversion:
    """Tests for E/nu → Lamé conversion in emit_main().

    Acceptance criteria covered: P1-T1 AC1-AC4, P1-T6 AC1-AC2
    """

    def test_enu_svk_emits_correct_lam_val(self):
        """
        Verifies: emit_main() with E=200e3, nu=0.3 SVK → lam_val ≈ 115384.615
        Acceptance criterion: P1-T1 AC1 — correct lam_val for E/nu inputs
        Passes when: emitted lam_val matches E*nu/((1+nu)*(1-2*nu)) to 6 digits
        """
        E, nu = 200e3, 0.3
        expected_lam = E * nu / ((1 + nu) * (1 - 2 * nu))

        bundle = compile(_make_problem({"E": E, "nu": nu}))
        source = bundle.emitted_source

        lam_val = _parse_float_assignment(source, "lam_val")
        assert lam_val == pytest.approx(expected_lam, rel=1e-6)

    def test_enu_svk_emits_correct_mu_val(self):
        """
        Verifies: emit_main() with E=200e3, nu=0.3 SVK → mu_val ≈ 76923.077
        Acceptance criterion: P1-T1 AC1 — correct mu_val for E/nu inputs
        Passes when: emitted mu_val matches E/(2*(1+nu)) to 6 digits
        """
        E, nu = 200e3, 0.3
        expected_mu = E / (2 * (1 + nu))

        bundle = compile(_make_problem({"E": E, "nu": nu}))
        source = bundle.emitted_source

        mu_val = _parse_float_assignment(source, "mu_val")
        assert mu_val == pytest.approx(expected_mu, rel=1e-6)

    def test_direct_lam_mu_unchanged(self):
        """
        Verifies: emit_main() with direct lam/mu params → values passed through.
        Acceptance criterion: P1-T1 AC2 — works with pre-computed lam/mu
        Passes when: emitted lam_val and mu_val match input params exactly
        """
        lam_in = 115384.615
        mu_in = 76923.077

        bundle = compile(_make_problem({"lam": lam_in, "mu": mu_in}))
        source = bundle.emitted_source

        lam_val = _parse_float_assignment(source, "lam_val")
        mu_val = _parse_float_assignment(source, "mu_val")

        assert lam_val == pytest.approx(lam_in, rel=1e-6)
        assert mu_val == pytest.approx(mu_in, rel=1e-6)

    def test_enu_j2_emits_correct_lam_mu(self):
        """
        Verifies: emit_main() with J2 material (E/nu + sigma_y0/K/n) → correct lam/mu.
        Acceptance criterion: P1-T6 AC2 — covers J2 material path
        Passes when: emitted lam_val and mu_val correct, plus sigma_y0/K/n present
        """
        E, nu = 200e3, 0.3
        expected_lam = E * nu / ((1 + nu) * (1 - 2 * nu))
        expected_mu = E / (2 * (1 + nu))

        bundle = compile(
            _make_j2_problem({"E": E, "nu": nu, "sigma_y0": 200.0, "K": 100.0, "n": 0.3})
        )
        source = bundle.emitted_source

        lam_val = _parse_float_assignment(source, "lam_val")
        mu_val = _parse_float_assignment(source, "mu_val")

        assert lam_val == pytest.approx(expected_lam, rel=1e-6)
        assert mu_val == pytest.approx(expected_mu, rel=1e-6)

        # Plastic parameters must also appear in the emitted source
        assert "sigma_y0_val" in source
        assert "K_hard_val" in source
        assert "n_hard_val" in source

    def test_emitted_main_block_has_nonzero_lam_mu(self):
        """
        Verifies: Generated __main__ block does NOT have lam_val=0.0 or mu_val=0.0.
        Acceptance criterion: P1-T1 AC3 — non-zero values for E/nu inputs
        Passes when: '0.0' not found for lam_val/mu_val in emitted main block
        """
        bundle = compile(_make_problem({"E": 200e3, "nu": 0.3}))
        source = bundle.emitted_source

        # Check neither assignment is zero
        assert not re.search(r"lam_val\s*=\s*0\.0\b", source), (
            "lam_val should not be 0.0 when E/nu are provided"
        )
        assert not re.search(r"mu_val\s*=\s*0\.0\b", source), (
            "mu_val should not be 0.0 when E/nu are provided"
        )
