"""Scaffold stubs for Task P1-1: TiconstitTarget profile + PlasticityCarrierSpec contract.

Plan: dev/plans/mfront_cycleM0.md (lines 55-58) — MFront-mimic Cycle M0, Phase 1.
Deliverables under test (built in P1-1 exec):
  packages/mechdsl-core/src/mechdsl/lawgen/{__init__,contracts}.py

These are AutViam scaffold stubs — each `pytest.skip`s until P1-1 lands the
`mechdsl.lawgen` package, at which point ExecPhase replaces the bodies with real
assertions (mirroring tests/lawgen/test_contracts.py). One stub per test_plan case.
"""

from __future__ import annotations

import pytest
import sympy as sp

from mechdsl.lawgen import PlasticityCarrierSpec, TiconstitTarget


class TestTaskP1_1:
    """Tests for Task P1-1: TiconstitTarget + PlasticityCarrierSpec. AC covered: 1,2,3,4."""

    @pytest.mark.unit
    def test_ticonstit_target_all_defaults(self) -> None:
        """Verifies: TiconstitTarget() instantiates with default fields.
        AC1: contract_id == 'ticonstit.plasticity_carrier.v1', package == 'ticonstit.generated'.
        Passes when: default instance carries the fixed contract id + package + ti_type_default."""
        target = TiconstitTarget()
        assert target.contract_id == "ticonstit.plasticity_carrier.v1"
        assert target.package == "ticonstit.generated"
        assert target.ti_type_default == "ti.f64"

    @pytest.mark.unit
    def test_ticonstit_target_overridden_budget_knobs(self) -> None:
        """Verifies: budget knob fields override cleanly and default to the P2-2 constants.
        AC3: budget knob defaults match P2-2 (max_expr_ops=400, max_cse_temps_per_func=96,
        max_func_lines=220, max_total_generated_lines_per_class=900, max_piecewise_branches=8,
        max_pow_with_symbolic_exponent=12).
        Passes when: overrides take effect and defaults equal the six P2-2 limits."""
        # Defaults equal the six P2-2 limits.
        default = TiconstitTarget()
        assert default.max_expr_ops == 400
        assert default.max_cse_temps_per_func == 96
        assert default.max_func_lines == 220
        assert default.max_total_generated_lines_per_class == 900
        assert default.max_piecewise_branches == 8
        assert default.max_pow_with_symbolic_exponent == 12
        # Overrides take effect.
        overridden = TiconstitTarget(max_expr_ops=42, max_piecewise_branches=3)
        assert overridden.max_expr_ops == 42
        assert overridden.max_piecewise_branches == 3
        assert overridden.max_func_lines == 220  # untouched knob keeps its default

    @pytest.mark.unit
    def test_plasticity_carrier_spec_rhq_expressions(self) -> None:
        """Verifies: PlasticityCarrierSpec holds name, parameters, R/H/Q exprs, variable bindings.
        AC2: spec round-trips name/parameters/expressions(R,H,Q)/variable_bindings.
        Passes when: a spec built from SymPy R/H/Q expressions preserves every field."""
        p, edot, T = sp.symbols("p edot T")
        sigma_y0, K, n = sp.symbols("sigma_y0 K n")
        spec = PlasticityCarrierSpec(
            name="voce",
            parameters=("sigma_y0", "K", "n"),
            expressions={
                "R": sigma_y0 + K * p**n,
                "H": K * n * p ** (n - 1),
                "Q": sp.Integer(1),
            },
            variable_bindings={"p": p, "edot": edot, "T": T},
        )
        assert spec.name == "voce"
        assert spec.parameters == ("sigma_y0", "K", "n")
        assert sigma_y0 + K * p**n == spec.R
        assert K * n * p ** (n - 1) == spec.H
        assert sp.Integer(1) == spec.Q
        assert set(spec.variable_bindings) == {"p", "edot", "T"}

    @pytest.mark.unit
    def test_contract_id_validation_rejects_wrong_string(self) -> None:
        """Verifies: contract_id validation rejects any string != the fixed contract id.
        AC1: contract_id is validated at construction time.
        Passes when: constructing TiconstitTarget with a wrong contract_id raises."""
        with pytest.raises(ValueError, match="contract_id"):
            TiconstitTarget(contract_id="ticonstit.plasticity_carrier.v2")
