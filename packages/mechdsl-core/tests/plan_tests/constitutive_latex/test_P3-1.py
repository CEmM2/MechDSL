"""Tests for Task P3-1: Replace taichi_printer string-dispatch + flow energy through IR.

Covers: Derived-energy carrier round-trips through ProblemIR/ArtifactBundle,
taichi_printer emits derived branch when energy present (not just advisory
LatexSemantics), named-model fallback (svk/j2_power_law/lemaitre) still works.

Task P3-1 structural rewiring on the happy path (Neo-Hookean) to de-risk
the production path for all later models. Focus: IR discipline (no layer bypass),
immutability of ProblemIR/ArtifactBundle, construction-time validation.

Acceptance criteria:
  1. Derived energy flows frontend -> ProblemIR -> codegen (no advisory-only path)
  2. Named-model fallback (svk/j2/lemaitre) unchanged
  3. Existing codegen/golden tests unaffected (P3-3 gate)
  4. IR immutability + construction-time validation preserved
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    emit,
    emit_constitutive_update,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize
from mechdsl.symbolic.energy import EnergyModel, derive_from_energy

pytestmark = pytest.mark.integration

# Neo-Hookean strain-energy authored in named invariants (P2-2). The derived
# EnergyModel is the input P3-1 wires through ProblemIR -> ArtifactBundle ->
# codegen. Derivation runs nrpylatex + sympy, so it is module-scoped.
_NEO_HOOKEAN_TEX = (
    Path(__file__).resolve().parents[5] / "dev" / "examples" / "neo_hookean_energy.tex"
)


@pytest.fixture(scope="module")
def neo_hookean_energy() -> EnergyModel:
    """Derive the Neo-Hookean EnergyModel once for the module."""
    return derive_from_energy(_NEO_HOOKEAN_TEX.read_text())


def _boundaries() -> tuple[BoundaryCondition, ...]:
    return (
        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
        BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
    )


def _make_ir(*, material: MaterialSpec, derived_energy: EnergyModel | None = None) -> ProblemIR:
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=material,
        boundaries=_boundaries(),
        derived_energy=derived_energy,
    )


def _emit(problem_ir: ProblemIR) -> str:
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


def _emit_constitutive(problem_ir: ProblemIR) -> str:
    """Emit only the constitutive ``@ti.func`` block — the surface P3-1 rewires.

    The full force / tangent kernels are not part of the P3-1 dispatch rewire
    (derived-energy force/tangent emission is later wiring), so the focused
    assertions target the constitutive block alone.
    """
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    ctx = EmissionContext()
    emit_constitutive_update(ctx, bundle)
    return ctx.get_source()


class TestTaskP3_1:
    """Tests for Task P3-1: taichi_printer dispatch + flow energy through IR.

    AC covered: 1 (derived energy flow), 2 (fallback unchanged), 3, 4.
    """

    # ------------------------------------------------------------------
    # AC 1 / AC 4: derived-energy carrier on ProblemIR
    # ------------------------------------------------------------------

    def test_derived_energy_carrier_in_problem_ir(self, neo_hookean_energy: EnergyModel):
        """The derived EnergyModel is carried as a real ProblemIR field.

        AC 1: derived energy flows frontend -> ProblemIR (not advisory only).
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        assert ir.derived_energy is neo_hookean_energy
        assert ir.derived_energy.pk2.shape == (3, 3)

    def test_problem_ir_derived_energy_defaults_to_none(self):
        """ProblemIR without the new arg works and defaults to None (back-compat).

        AC 4: the ~61 existing constructors pass no new argument -> unaffected.
        """
        ir = _make_ir(material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}))
        assert ir.derived_energy is None

    def test_problem_ir_immutability_preserved_with_derived_energy(
        self, neo_hookean_energy: EnergyModel
    ):
        """ProblemIR stays frozen with the new field set.

        AC 4: IR immutability preserved.
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ir.derived_energy = None  # type: ignore[misc]

    def test_problem_ir_validates_derived_energy_at_construction(self):
        """A malformed carrier is rejected at construction, not at emission.

        AC 4: construction-time validation preserved (IR discipline).
        """

        class _Bogus:
            """Matches none of the recognised model shapes (invariant / spectral / fiber)."""

        with pytest.raises(ValueError, match="must be a recognised constitutive model"):
            _make_ir(
                material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
                derived_energy=_Bogus(),  # type: ignore[arg-type]
            )

    def test_derived_energy_excluded_from_problem_ir_to_dict(self, neo_hookean_energy: EnergyModel):
        """to_dict stays JSON-able: the SymPy-bearing carrier is NOT serialised.

        AC 1: the carrier is the Python-object channel, not the JSON surface.
        """
        import json

        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        d = ir.to_dict()
        assert "derived_energy" not in d
        json.dumps(d)  # must not raise (no SymPy in the dict)

    # ------------------------------------------------------------------
    # AC 1: derived-energy channel through ArtifactBundle
    # ------------------------------------------------------------------

    def test_artifact_bundle_carries_derived_energy(self, neo_hookean_energy: EnergyModel):
        """ArtifactBundle.from_pipeline pulls the carrier off the ProblemIR.

        AC 1: derived energy reaches codegen through the real bundle channel.
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        loc_result, plans = localise_and_optimize(ir)
        bundle = ArtifactBundle.from_pipeline(ir, loc_result, plans)
        assert bundle.derived_energy is neo_hookean_energy

    def test_bundle_json_path_unaffected_when_derived_energy_present(
        self, neo_hookean_energy: EnergyModel
    ):
        """The JSON path (to_dict / content_hash) ignores the carrier.

        AC 1/3: golden JSON surface and content hash are unchanged whether or
        not a derived energy rides on the bundle.
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        loc_result, plans = localise_and_optimize(ir)
        with_energy = ArtifactBundle.from_pipeline(ir, loc_result, plans)
        without_energy = dataclasses.replace(with_energy, derived_energy=None)

        assert "derived_energy" not in with_energy.to_dict()
        assert with_energy.to_dict() == without_energy.to_dict()
        assert with_energy.content_hash() == without_energy.content_hash()

    # ------------------------------------------------------------------
    # AC 1: taichi_printer emits the derived branch
    # ------------------------------------------------------------------

    def test_taichi_printer_emits_derived_branch_when_energy_present(
        self, neo_hookean_energy: EnergyModel
    ):
        """emit() routes through energy_emitter when a derived energy is present.

        AC 1: derived energy through codegen (no name-string switch, no
        advisory-only path). The emitted constitutive func is derived, not the
        hand-coded SVK/J2 branch.
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        block = _emit_constitutive(ir)
        assert "derived from LaTeX energy" in block
        assert "def constitutive_update(" in block
        assert "PK2 stress derived from a LaTeX strain-energy density" in block
        # The hand-coded SVK closed-form must NOT be the constitutive func body:
        # this is the derived path, not the name-string switch.
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" not in block
        # And the full emit() still routes through the derived branch.
        assert "derived from LaTeX energy" in _emit(ir)

    def test_derived_branch_admits_model_outside_named_emit_allowlist(
        self, neo_hookean_energy: EnergyModel
    ):
        """A derived energy lets emit() accept a model name the named-emit
        allow-list (svk/j2/lemaitre) would otherwise reject.

        AC 1: the derived branch is the real production path, not gated by the
        legacy name allow-list.
        """
        ir = _make_ir(
            material=MaterialSpec(model="neo_hookean", params={"mu": 1.0, "kappa": 1.0}),
            derived_energy=neo_hookean_energy,
        )
        # neo_hookean is NOT in the emit() named allow-list; the derived energy
        # must carry it through.
        source = _emit(ir)
        assert "def constitutive_update(" in source

    # ------------------------------------------------------------------
    # AC 2: named-model fallback unchanged
    # ------------------------------------------------------------------

    def test_named_model_fallback_svk_unchanged(self):
        """SVK dispatch (no derived energy) still emits the hand-coded closed form.

        AC 2: fallback unchanged.
        """
        ir = _make_ir(material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}))
        block = _emit_constitutive(ir)
        assert "def constitutive_update(" in block
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in block
        assert "derived from LaTeX energy" not in block

    def test_named_model_fallback_j2_power_law_unchanged(self):
        """J2 power-law dispatch (no derived energy) still emits the radial return.

        AC 2: fallback unchanged.
        """
        ir = _make_ir(
            material=MaterialSpec(
                model="j2_power_law",
                params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 100.0, "n": 0.2},
            )
        )
        source = _emit(ir)
        assert "def constitutive_update_plastic(" in source
        assert "derived from LaTeX energy" not in source

    def test_named_model_fallback_lemaitre_unchanged(self):
        """Lemaitre dispatch (no derived energy) still emits J2 + damage wrapper.

        AC 2: fallback unchanged.
        """
        ir = _make_ir(
            material=MaterialSpec(
                model="lemaitre",
                params={
                    "E": 200e3,
                    "nu": 0.3,
                    "sigma_y0": 250.0,
                    "K": 100.0,
                    "n": 0.2,
                    "S": 1.0,
                    "s": 1.0,
                    "D_crit": 0.5,
                },
            )
        )
        source = _emit(ir)
        assert "def constitutive_update_plastic(" in source
        assert "derived from LaTeX energy" not in source

    def test_emit_still_rejects_unsupported_model_without_derived_energy(self):
        """The emit() name allow-list still rejects unknown models when no
        derived energy is present.

        AC 2: the fallback guard is intact for the named-model path.
        """
        # `perzyna` is accepted by ProblemIR construction but is outside the
        # Taichi emit allow-list and has no derived energy -> must reject.
        ir = _make_ir(
            material=MaterialSpec(
                model="perzyna",
                params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "eta": 1.0, "m": 1.0},
            )
        )
        loc_result, plans = localise_and_optimize(ir)
        bundle = ArtifactBundle.from_pipeline(ir, loc_result, plans)
        with pytest.raises(ValueError, match="Unsupported material model"):
            emit(bundle)
