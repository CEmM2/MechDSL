"""Unit tests for the lawgen emission contracts (Task P1-1).

Covers the four ``test_plan.cases`` from ``dev/plans/mfront_cycleM0/json/P1-1.json``:

1. instantiate ``TiconstitTarget`` with all defaults
2. instantiate ``TiconstitTarget`` with overridden budget knobs
3. instantiate ``PlasticityCarrierSpec`` with R/H/Q SymPy expressions
4. contract_id validation rejects a wrong string

Plus failure-route coverage for immutability and required-field validation.
"""

from __future__ import annotations

import dataclasses

import pytest
import sympy as sp

from mechdsl.lawgen import (
    TICONSTIT_CONTRACT_ID,
    TICONSTIT_PACKAGE,
    PlasticityCarrierSpec,
    TiconstitTarget,
)


def _example_carrier() -> PlasticityCarrierSpec:
    """A Voce-style isotropic-hardening carrier used across several tests."""
    p, edot, T = sp.symbols("p edot T")
    sigma_y0, K, n = sp.symbols("sigma_y0 K n")
    return PlasticityCarrierSpec(
        name="voce",
        parameters=("sigma_y0", "K", "n"),
        expressions={
            "R": sigma_y0 + K * p**n,
            "H": K * n * p ** (n - 1),
            "Q": sp.Integer(1),
        },
        variable_bindings={"p": p, "edot": edot, "T": T},
    )


# ---------------------------------------------------------------------------
# Case 1 — TiconstitTarget defaults.
# ---------------------------------------------------------------------------


class TestTiconstitTargetDefaults:
    def test_default_identity_fields(self) -> None:
        target = TiconstitTarget()
        assert target.contract_id == "ticonstit.plasticity_carrier.v1"
        assert target.contract_id == TICONSTIT_CONTRACT_ID
        assert target.package == "ticonstit.generated"
        assert target.package == TICONSTIT_PACKAGE
        assert target.ti_type_default == "ti.f64"

    def test_default_budget_knobs_match_p2_2(self) -> None:
        target = TiconstitTarget()
        assert target.max_expr_ops == 400
        assert target.max_cse_temps_per_func == 96
        assert target.max_func_lines == 220
        assert target.max_total_generated_lines_per_class == 900
        assert target.max_piecewise_branches == 8
        assert target.max_pow_with_symbolic_exponent == 12

    def test_target_is_immutable(self) -> None:
        target = TiconstitTarget()
        with pytest.raises(dataclasses.FrozenInstanceError):
            target.max_expr_ops = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Case 2 — TiconstitTarget with overridden budget knobs.
# ---------------------------------------------------------------------------


class TestTiconstitTargetOverrides:
    def test_overridden_budget_knobs_take_effect(self) -> None:
        target = TiconstitTarget(
            max_expr_ops=10,
            max_cse_temps_per_func=11,
            max_func_lines=12,
            max_total_generated_lines_per_class=13,
            max_piecewise_branches=14,
            max_pow_with_symbolic_exponent=15,
        )
        assert target.max_expr_ops == 10
        assert target.max_cse_temps_per_func == 11
        assert target.max_func_lines == 12
        assert target.max_total_generated_lines_per_class == 13
        assert target.max_piecewise_branches == 14
        assert target.max_pow_with_symbolic_exponent == 15
        # contract identity is untouched by knob overrides.
        assert target.contract_id == TICONSTIT_CONTRACT_ID

    def test_overriding_ti_type_default(self) -> None:
        target = TiconstitTarget(ti_type_default="ti.f32")
        assert target.ti_type_default == "ti.f32"

    @pytest.mark.parametrize(
        "knob",
        [
            "max_expr_ops",
            "max_cse_temps_per_func",
            "max_func_lines",
            "max_total_generated_lines_per_class",
            "max_piecewise_branches",
            "max_pow_with_symbolic_exponent",
        ],
    )
    def test_nonpositive_budget_knob_rejected(self, knob: str) -> None:
        with pytest.raises(ValueError, match=knob):
            TiconstitTarget(**{knob: 0})

    def test_empty_ti_type_default_rejected(self) -> None:
        # Empty string now trips the strict non-empty-str check (F5) → TypeError.
        with pytest.raises((ValueError, TypeError), match="ti_type_default"):
            TiconstitTarget(ti_type_default="")


# ---------------------------------------------------------------------------
# Case 3 — PlasticityCarrierSpec with R/H/Q SymPy expressions.
# ---------------------------------------------------------------------------


class TestPlasticityCarrierSpec:
    def test_holds_name_parameters_expressions_bindings(self) -> None:
        spec = _example_carrier()
        assert spec.name == "voce"
        assert spec.parameters == ("sigma_y0", "K", "n")
        assert set(spec.expressions) == {"R", "H", "Q"}
        assert set(spec.variable_bindings) == {"p", "edot", "T"}

    def test_rhq_role_accessors_preserve_which_is_which(self) -> None:
        spec = _example_carrier()
        p = spec.variable_bindings["p"]
        sigma_y0, K, n = sp.symbols("sigma_y0 K n")
        assert sigma_y0 + K * p**n == spec.R
        assert K * n * p ** (n - 1) == spec.H
        assert sp.Integer(1) == spec.Q
        # accessors and the map agree.
        assert spec.R is spec.expressions["R"]
        assert spec.H is spec.expressions["H"]
        assert spec.Q is spec.expressions["Q"]

    def test_expressions_are_sympy(self) -> None:
        spec = _example_carrier()
        for expr in spec.expressions.values():
            assert isinstance(expr, sp.Expr)

    def test_parameters_normalised_to_tuple(self) -> None:
        p, edot, T = sp.symbols("p edot T")
        spec = PlasticityCarrierSpec(
            name="lin",
            parameters=["sigma_y0", "K"],  # list on input
            expressions={"R": sp.Symbol("sigma_y0"), "H": sp.Symbol("K"), "Q": sp.Integer(1)},
            variable_bindings={"p": p, "edot": edot, "T": T},
        )
        assert spec.parameters == ("sigma_y0", "K")
        assert isinstance(spec.parameters, tuple)

    def test_spec_mappings_are_read_only(self) -> None:
        spec = _example_carrier()
        with pytest.raises(TypeError):
            spec.expressions["R"] = sp.Integer(0)  # type: ignore[index]
        with pytest.raises(TypeError):
            spec.variable_bindings["p"] = sp.Symbol("q")  # type: ignore[index]

    def test_spec_is_frozen(self) -> None:
        spec = _example_carrier()
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Case 4 — contract_id validation + other required-field failure routes.
# ---------------------------------------------------------------------------


class TestValidation:
    def test_wrong_contract_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="contract_id"):
            TiconstitTarget(contract_id="something.else")

    def test_empty_contract_id_rejected(self) -> None:
        # Empty string now trips the strict non-empty-str check (F5) → TypeError.
        with pytest.raises((ValueError, TypeError), match="contract_id"):
            TiconstitTarget(contract_id="")

    def test_empty_package_rejected(self) -> None:
        # Empty string now trips the strict non-empty-str check (F5) → TypeError.
        with pytest.raises((ValueError, TypeError), match="package"):
            TiconstitTarget(package="")

    def test_empty_name_rejected(self) -> None:
        p = sp.Symbol("p")
        with pytest.raises(ValueError, match="name"):
            PlasticityCarrierSpec(
                name="",
                parameters=("K",),
                expressions={"R": sp.Symbol("K"), "H": sp.Integer(0), "Q": sp.Integer(1)},
                variable_bindings={"p": p},
            )

    def test_empty_parameters_rejected(self) -> None:
        p = sp.Symbol("p")
        with pytest.raises(ValueError, match="parameter"):
            PlasticityCarrierSpec(
                name="lin",
                parameters=(),
                expressions={"R": sp.Integer(0), "H": sp.Integer(0), "Q": sp.Integer(1)},
                variable_bindings={"p": p},
            )

    def test_bare_string_parameters_rejected(self) -> None:
        # A bare str would silently split into per-character names ('K', 'n').
        p = sp.Symbol("p")
        with pytest.raises(ValueError, match="not a single str"):
            PlasticityCarrierSpec(
                name="lin",
                parameters="Kn",  # type: ignore[arg-type]
                expressions={"R": sp.Symbol("K"), "H": sp.Integer(0), "Q": sp.Integer(1)},
                variable_bindings={"p": p},
            )

    def test_missing_expression_rejected(self) -> None:
        p = sp.Symbol("p")
        with pytest.raises(ValueError, match="expression"):
            PlasticityCarrierSpec(
                name="lin",
                parameters=("K",),
                expressions={"R": sp.Symbol("K"), "H": sp.Integer(0)},  # no Q
                variable_bindings={"p": p},
            )

    def test_empty_variable_bindings_rejected(self) -> None:
        with pytest.raises(ValueError, match="variable binding"):
            PlasticityCarrierSpec(
                name="lin",
                parameters=("K",),
                expressions={"R": sp.Symbol("K"), "H": sp.Integer(0), "Q": sp.Integer(1)},
                variable_bindings={},
            )


# ---------------------------------------------------------------------------
# F3 — value-type validation on the spec's mappings (strict, closes the
# alias-mutation hole: a mutable non-Expr value cannot be stored).
# ---------------------------------------------------------------------------


class TestSpecValueTypeValidation:
    def test_non_expr_expression_value_rejected(self) -> None:
        # A list value is not an sp.Expr → rejected (also blocks alias mutation).
        p = sp.Symbol("p")
        with pytest.raises((TypeError, ValueError)):
            PlasticityCarrierSpec(
                name="lin",
                parameters=("K",),
                expressions={"R": [], "H": sp.Integer(1), "Q": sp.Integer(1)},  # type: ignore[dict-item]
                variable_bindings={"p": p},
            )

    def test_non_symbol_binding_value_rejected(self) -> None:
        with pytest.raises((TypeError, ValueError)):
            PlasticityCarrierSpec(
                name="lin",
                parameters=("K",),
                expressions={"R": sp.Symbol("K"), "H": sp.Integer(1), "Q": sp.Integer(1)},
                variable_bindings={"p": "notasym"},  # type: ignore[dict-item]
            )


# ---------------------------------------------------------------------------
# F5 — strict scalar types on TiconstitTarget (reject bool/float knobs and
# non-string identity fields).
# ---------------------------------------------------------------------------


class TestTargetScalarTypeValidation:
    def test_float_budget_knob_rejected(self) -> None:
        with pytest.raises((TypeError, ValueError), match="max_expr_ops"):
            TiconstitTarget(max_expr_ops=1.5)  # type: ignore[arg-type]

    def test_bool_budget_knob_rejected(self) -> None:
        # type(True) is bool, not int — must be rejected even though True == 1.
        with pytest.raises((TypeError, ValueError), match="max_expr_ops"):
            TiconstitTarget(max_expr_ops=True)  # type: ignore[arg-type]

    def test_non_string_package_rejected(self) -> None:
        with pytest.raises((TypeError, ValueError), match="package"):
            TiconstitTarget(package=["x"])  # type: ignore[arg-type]
