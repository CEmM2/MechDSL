"""Live audit for recovery-plan P3-4: stable `ProblemIR` minimal subset.

Asserts that:

1. ``MVP_STABLE_SUBSET`` is an immutable, well-typed snapshot of the
   contract.
2. Every value enumerated in ``MVP_STABLE_SUBSET`` produces an IR that
   passes ``assert_mvp_stable`` and reports ``is_mvp_stable() == True``.
3. Every dimension that the broader ``ProblemIR`` schema accepts but the
   MVP-stable subset rejects (UL formulation, TET4/TET10/HEX20 elements,
   non-MVP materials, EXPLICIT dynamics) raises ``MvpSubsetViolation``
   with a message that names the offending field and points at the
   Plan-B phase that adds support.
4. ``MvpSubsetViolation`` subclasses ``UnsupportedError`` so callers that
   catch the broader supported-subset exception still work.
5. ``MVP_STABLE_SUBSET`` stays in lock-step with
   ``ALLOWED_PROFILES`` in :mod:`mechdsl` and the README support tier.
"""

from __future__ import annotations

import pytest

from mechdsl import ALLOWED_PROFILES
from mechdsl.ir.mechanics_ir import (
    MVP_STABLE_SUBSET,
    BCType,
    BoundaryCondition,
    Configuration,
    DynamicsMode,
    ElementType,
    Formulation,
    MaterialSpec,
    MvpStableSubset,
    MvpSubsetViolation,
    ProblemIR,
)
from mechdsl.symbolic.convected import UnsupportedError

# Per-model param packs that satisfy the P3-5 required-parameters validation
# for every model the MVP-stable subset enumerates. Tests that swap models
# pull from this table so they do not collide with P3-5 surface-level checks.
_PARAMS_BY_MODEL: dict[str, dict[str, float]] = {
    "svk": {"E": 200e3, "nu": 0.3},
    "j2_power_law": {"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 1000.0, "n": 10.0},
}


def _mvp_problem_ir(
    *,
    formulation: Formulation = Formulation.TOTAL_LAGRANGIAN,
    element_type: ElementType = ElementType.HEX8,
    material_model: str = "svk",
    dynamics_mode: DynamicsMode | None = None,
) -> ProblemIR:
    """Build a ProblemIR pre-loaded with MVP-stable defaults.

    Parameters allow swapping a single axis at a time so negative tests can
    exercise one violation per case without redundant setup.
    """
    params = _PARAMS_BY_MODEL.get(material_model, {"E": 200e3, "nu": 0.3})
    return ProblemIR(
        dim=3,
        formulation=formulation,
        element_type=element_type,
        material=MaterialSpec(model=material_model, params=params),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        dynamics_mode=dynamics_mode,
    )


class TestMvpStableSubsetDescriptor:
    """The descriptor must expose an immutable, well-typed contract snapshot."""

    @pytest.mark.unit
    def test_subset_is_frozen_dataclass_instance(self) -> None:
        from dataclasses import FrozenInstanceError

        assert isinstance(MVP_STABLE_SUBSET, MvpStableSubset)
        with pytest.raises(FrozenInstanceError):
            MVP_STABLE_SUBSET.dim = (2, 3)  # type: ignore[misc]

    @pytest.mark.unit
    def test_subset_axes_are_tuples_not_sets(self) -> None:
        # Tuples preserve documentation order; sets would shuffle it.
        assert isinstance(MVP_STABLE_SUBSET.dim, tuple)
        assert isinstance(MVP_STABLE_SUBSET.formulations, tuple)
        assert isinstance(MVP_STABLE_SUBSET.element_types, tuple)
        assert isinstance(MVP_STABLE_SUBSET.materials, tuple)
        assert isinstance(MVP_STABLE_SUBSET.dynamics_modes, tuple)
        assert isinstance(MVP_STABLE_SUBSET.configurations, tuple)

    @pytest.mark.unit
    def test_subset_documents_canonical_mvp_axes(self) -> None:
        assert MVP_STABLE_SUBSET.dim == (3,)
        assert MVP_STABLE_SUBSET.formulations == (Formulation.TOTAL_LAGRANGIAN,)
        assert MVP_STABLE_SUBSET.element_types == (ElementType.HEX8,)
        assert MVP_STABLE_SUBSET.materials == ("svk", "j2_power_law")
        assert MVP_STABLE_SUBSET.dynamics_modes == (DynamicsMode.STATIC,)
        assert MVP_STABLE_SUBSET.configurations == (Configuration.REFERENCE,)


class TestMvpStableSubsetPositive:
    """Every value enumerated in the subset must accept cleanly."""

    @pytest.mark.unit
    def test_canonical_mvp_ir_passes_assert(self) -> None:
        ir = _mvp_problem_ir()
        ir.assert_mvp_stable()
        assert ir.is_mvp_stable() is True

    @pytest.mark.unit
    @pytest.mark.parametrize("model", MVP_STABLE_SUBSET.materials)
    def test_every_listed_material_accepts(self, model: str) -> None:
        ir = _mvp_problem_ir(material_model=model)
        ir.assert_mvp_stable()
        assert ir.is_mvp_stable() is True

    @pytest.mark.unit
    def test_explicit_static_dynamics_mode_accepts(self) -> None:
        # Passing dynamics_mode explicitly (instead of letting it auto-infer
        # to STATIC) must not change the verdict.
        ir = _mvp_problem_ir(dynamics_mode=DynamicsMode.STATIC)
        assert ir.is_mvp_stable() is True


class TestMvpSubsetViolationRejections:
    """Each axis outside the subset must raise with a pointed message."""

    @pytest.mark.unit
    def test_updated_lagrangian_rejected(self) -> None:
        ir = _mvp_problem_ir(formulation=Formulation.UPDATED_LAGRANGIAN)
        assert ir.is_mvp_stable() is False
        with pytest.raises(MvpSubsetViolation, match=r"formulation=") as exc:
            ir.assert_mvp_stable()
        # Plan-phase pointer is required by .claude/rules/ir.md.
        assert "Plan B" in str(exc.value)

    @pytest.mark.unit
    @pytest.mark.parametrize("elem", [ElementType.TET4, ElementType.TET10, ElementType.HEX20])
    def test_experimental_element_rejected(self, elem: ElementType) -> None:
        ir = _mvp_problem_ir(element_type=elem)
        assert ir.is_mvp_stable() is False
        with pytest.raises(MvpSubsetViolation, match=r"element_type=") as exc:
            ir.assert_mvp_stable()
        assert "Plan B phase B5" in str(exc.value)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "model",
        ["neo_hookean", "mooney_rivlin", "ogden", "hgo", "lemaitre", "perzyna"],
    )
    def test_non_mvp_material_rejected(self, model: str) -> None:
        ir = _mvp_problem_ir(material_model=model)
        assert ir.is_mvp_stable() is False
        with pytest.raises(MvpSubsetViolation, match=r"material\.model=") as exc:
            ir.assert_mvp_stable()
        assert "Plan B" in str(exc.value)

    @pytest.mark.unit
    def test_explicit_dynamics_rejected(self) -> None:
        ir = _mvp_problem_ir(dynamics_mode=DynamicsMode.EXPLICIT)
        assert ir.is_mvp_stable() is False
        with pytest.raises(MvpSubsetViolation, match=r"dynamics_mode=") as exc:
            ir.assert_mvp_stable()
        assert "Plan B phase B7" in str(exc.value)

    @pytest.mark.unit
    def test_violation_subclasses_unsupported_error(self) -> None:
        # Callers catching UnsupportedError per .claude/rules/ir.md must keep
        # working when the IR raises the more specific MvpSubsetViolation.
        ir = _mvp_problem_ir(formulation=Formulation.UPDATED_LAGRANGIAN)
        with pytest.raises(UnsupportedError):
            ir.assert_mvp_stable()


class TestMvpSubsetContractAlignment:
    """Cross-check `MVP_STABLE_SUBSET` stays aligned with sibling contracts."""

    @pytest.mark.unit
    def test_allowed_profiles_only_lists_mvp(self) -> None:
        # If a new profile lands in `compile_latex` the subset descriptor and
        # docs must follow. This guard fails loudly so the contract does not
        # silently drift.
        assert frozenset({"mvp"}) == ALLOWED_PROFILES, (
            "Adding a profile to ALLOWED_PROFILES requires extending "
            "MVP_STABLE_SUBSET (and `dev/design_docs/04-MECHANICS-IR.md` "
            "§3.1) in lock-step."
        )

    @pytest.mark.unit
    def test_subset_documented_in_ir_architecture_doc(self) -> None:
        # IR architecture lives in `mechdsl/ir/ARCHITECTURE.md` (sibling of
        # the implementation) because `dev/design_docs/` is hook-protected
        # and the contract must move in lock-step with code changes.
        from pathlib import Path

        import mechdsl.ir as ir_pkg

        ir_pkg_dir = Path(ir_pkg.__file__).resolve().parent
        ir_arch = ir_pkg_dir / "ARCHITECTURE.md"
        assert ir_arch.is_file(), f"IR architecture doc missing: {ir_arch}"
        body = ir_arch.read_text()
        assert "MVP-stable subset" in body, (
            "ir/ARCHITECTURE.md must document the MVP-stable subset that "
            "MVP_STABLE_SUBSET encodes (see P3-4)."
        )
