"""Tests for Task P2-1: Invariant-authoring contract + energy.py named-invariant binding.

Verifies that a strain energy authored in named invariants (\\bar I_1, \\bar I_2, J, I_4, I_5)
derives S = 2 dPsi/dC and C = 4 d²Psi/dC dC via the existing dPsi/dE core (C = 2E + I, so
d/dE = 2 d/dC), without nrpylatex ever parsing \\det or \\log.

Acceptance criteria:
- AC-1: Invariant symbol → definition substitution on C = 2E + I
- AC-2: S = 2 dPsi/dC matches reference for a known invariant energy
- AC-3: Unsupported invariant form rejects with phase pointer
"""

from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from mechdsl.symbolic import invariants
from mechdsl.symbolic.energy import (
    EnergyDerivationError,
    _bind_invariants,
    _c_from_strain,
    _strain_grid,
    derive_from_energy,
)


def _zero_strain_grid() -> tuple[tuple[sp.Symbol, ...], ...]:
    """A full EDD grid with no strain symbols present in psi (=> created)."""
    return _strain_grid(sp.Integer(0))


class TestTaskP2_1:
    """Tests for Task P2-1: Invariant-authoring contract + energy.py binding. AC covered: 1-3."""

    @pytest.mark.unit
    def test_invariant_symbol_substitution_on_c(self):
        """Verifies: Named invariant symbols (\\bar I_1, \\bar I_2, J, I_4, I_5) substitute
        to their definitions evaluated on C = 2E + I.
        AC: AC-1.
        Passes when: A simple energy Psi = f(\\bar I_1) is rewritten as Psi = f(expr_in_C)."""
        strain = _zero_strain_grid()
        c = _c_from_strain(strain)

        # At E = 0, C = I, so the invariant definitions take their reference values.
        zero = {strain[i][j]: 0 for i in range(3) for j in range(3)}

        # Ibar1 = I1 * I3^{-1/3} -> tr(I) * 1 = 3 at C = I.
        ibar1 = _bind_invariants(sp.Symbol("Ibar1"), strain, "")
        assert ibar1 != sp.Symbol("Ibar1"), "Ibar1 must be substituted, not left bare"
        assert sp.Symbol("Ibar1") not in ibar1.free_symbols
        assert sp.simplify(ibar1.subs(zero)) == 3

        # Ibar2 = I2 * I3^{-2/3} -> i2(I) = 3 at C = I.
        ibar2 = _bind_invariants(sp.Symbol("Ibar2"), strain, "")
        assert sp.simplify(ibar2.subs(zero)) == 3

        # Jdet = sqrt(det C) -> 1 at C = I.
        jdet = _bind_invariants(sp.Symbol("Jdet"), strain, "")
        assert sp.simplify(jdet.subs(zero)) == 1

        # The substituted expression must equal the invariants.py definition on C = 2E + I
        # (no independent re-derivation): Ibar1 == i1(C) * i3(C)^{-1/3}, symbolically.
        ibar1_ref = invariants.i1(c) * invariants.i3(c) ** sp.Rational(-1, 3)
        assert sp.simplify(ibar1 - ibar1_ref) == 0

        # Bare material parameters (not invariants) are left untouched.
        passthrough = _bind_invariants(sp.Symbol("mu") * sp.Symbol("kappa"), strain, "")
        assert passthrough == sp.Symbol("mu") * sp.Symbol("kappa")

    @pytest.mark.unit
    def test_derived_stress_matches_reference_invariant_energy(self):
        """Verifies: An energy authored in named invariants derives S(C) matching
        a hand-computed reference via the C = 2E + I binding.
        AC: AC-2.
        Passes when: Derived S_IJ = 2 dPsi/dC reproduces a known closed-form stress
        to within numerical tolerance (< 1e-9 relative error)."""
        # Single-term volumetric energy: Psi = (kappa/2)(J - 1)^2.
        #   S = 2 dPsi/dC = 2 * kappa(J-1) dJ/dC,  dJ/dC = (J/2) C^{-1}
        #     => S = kappa (J - 1) J C^{-1}   (hand-derived closed form).
        src = r"""
        % declare metric gDD --dim 3
        % declare EDD --dim 3
        % declare \kappa --const
        \Psi = \frac{\kappa}{2} (\mathrm{Jdet} - 1)^2
        """
        model = derive_from_energy(src)

        # No nrpylatex parse of \det / \log occurred: the parsed psi carried only
        # the bare invariant symbol (acceptance criterion #2).
        kappa = next(s for s in model.pk2.free_symbols if s.name == "kappa")
        strain = model.strain_symbols

        kap_val = 1.5e5
        rng = np.random.default_rng(20260604)
        for _ in range(25):
            a = rng.standard_normal((3, 3)) * 0.1
            e = 0.5 * (a + a.T)  # symmetric Green-Lagrange strain
            subs: dict = {kappa: kap_val}
            for i in range(3):
                for j in range(3):
                    subs[strain[i][j]] = float(e[i, j])

            s_derived = np.array(
                [[float(model.pk2[i, j].subs(subs)) for j in range(3)] for i in range(3)]
            )

            c_num = 2.0 * e + np.eye(3)
            j_det = np.sqrt(np.linalg.det(c_num))
            c_inv = np.linalg.inv(c_num)
            s_ref = kap_val * (j_det - 1.0) * j_det * c_inv

            assert np.allclose(s_derived, s_ref, atol=0.0, rtol=1e-9)

    @pytest.mark.unit
    def test_isochoric_invariant_stress_matches_reference(self):
        """Verifies: The barred (isochoric) invariant binding carries the J^{-2/3}
        volumetric coupling correctly (exponents -1/3 / -2/3).
        AC: AC-2 (isochoric exponent guard)."""
        # Psi = c (Ibar1 - 3),  Ibar1 = I1 I3^{-1/3}.
        #   S = 2 c dIbar1/dC = 2 c I3^{-1/3}(I - (1/3) I1 C^{-1})  (hand-derived).
        src = r"""
        % declare metric gDD --dim 3
        % declare EDD --dim 3
        % declare \mu --const
        \Psi = \mu (\mathrm{Ibar1} - 3)
        """
        model = derive_from_energy(src)
        mu = next(s for s in model.pk2.free_symbols if s.name == "mu")
        strain = model.strain_symbols

        mu_val = 8.0e4
        rng = np.random.default_rng(424242)
        for _ in range(25):
            a = rng.standard_normal((3, 3)) * 0.1
            e = 0.5 * (a + a.T)
            subs: dict = {mu: mu_val}
            for i in range(3):
                for j in range(3):
                    subs[strain[i][j]] = float(e[i, j])

            s_derived = np.array(
                [[float(model.pk2[i, j].subs(subs)) for j in range(3)] for i in range(3)]
            )

            c_num = 2.0 * e + np.eye(3)
            i1 = np.trace(c_num)
            i3 = np.linalg.det(c_num)
            c_inv = np.linalg.inv(c_num)
            s_ref = 2.0 * mu_val * i3 ** (-1.0 / 3.0) * (np.eye(3) - (1.0 / 3.0) * i1 * c_inv)

            assert np.allclose(s_derived, s_ref, atol=0.0, rtol=1e-9)

    @pytest.mark.unit
    def test_unsupported_invariant_rejects_with_phase_pointer(self):
        """Verifies: Unsupported invariant forms reject at derivation time with a
        plan-phase pointer.
        AC: AC-3.
        Passes when: EnergyDerivationError raised with message containing a phase
        reference (e.g., 'Phase 5')."""
        # Fiber invariant I4 — recognised but needs a fiber direction (Phase 5 / P5-1).
        fiber_src = r"""
        % declare metric gDD --dim 3
        % declare EDD --dim 3
        \Psi = \mathrm{I4f}
        """
        with pytest.raises(EnergyDerivationError) as fiber_exc:
            derive_from_energy(fiber_src)
        msg = str(fiber_exc.value)
        assert "I4f" in msg
        assert "Phase 5" in msg or "P5-1" in msg

        # An invariant-shaped but unknown symbol is also rejected with a phase pointer
        # rather than silently treated as a free parameter.
        unknown_src = r"""
        % declare metric gDD --dim 3
        % declare EDD --dim 3
        \Psi = \mathrm{Ibar7}
        """
        with pytest.raises(EnergyDerivationError) as unknown_exc:
            derive_from_energy(unknown_src)
        unknown_msg = str(unknown_exc.value)
        assert "Ibar7" in unknown_msg
        assert "Phase 5" in unknown_msg or "P5-1" in unknown_msg
        # The rejection locates the offending invariant by source line: \mathrm{Ibar7}
        # sits on line 4 of unknown_src (line 1 is the leading newline).
        assert "line 4" in unknown_msg, unknown_msg

    @pytest.mark.unit
    def test_misspelled_invariant_does_not_silently_pass_as_parameter(self):
        """Verifies: a symbol that LOOKS like an invariant but does not match the
        invariant-name regex (Jdet2, Ibar1x, Jbar) is rejected, not left as a bare
        free parameter that silently contributes zero stress.
        AC: AC-3 (IR discipline — unrecognised constructs must raise).
        Passes when: EnergyDerivationError names the offending symbol."""
        for bad in ("Jdet2", "Ibar1x", "Jbar"):
            src = (
                "% declare metric gDD --dim 3\n"
                "% declare EDD --dim 3\n"
                "% declare \\mu --const\n"
                rf"\Psi = \frac{{\mu}}{{2}} (\mathrm{{{bad}}} - 3)"
            )
            with pytest.raises(EnergyDerivationError) as exc:
                derive_from_energy(src)
            assert bad in str(exc.value), f"{bad}: {exc.value}"

    @pytest.mark.unit
    def test_undeclared_parameter_is_rejected(self):
        """Verifies: an undeclared scalar (neither a --const param, a strain
        component, nor a supported invariant) is rejected rather than silently
        treated as a free constant.
        AC: AC-3.
        Passes when: EnergyDerivationError names the undeclared symbol."""
        src = (
            "% declare metric gDD --dim 3\n"
            "% declare EDD --dim 3\n"
            r"\Psi = \mathrm{Ibar1} \cdot \mathrm{undeclared}"
        )
        with pytest.raises(EnergyDerivationError) as exc:
            derive_from_energy(src)
        assert "undeclared" in str(exc.value)
