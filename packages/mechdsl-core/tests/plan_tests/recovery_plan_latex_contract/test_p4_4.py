"""Live audit for recovery-plan P4-4: lowering rejections are deterministic.

Asserts that:

1. Every unsupported stable-path combination raises
   :class:`LocalisationError` (a subclass of :class:`UnsupportedError`).
2. Each rejection message names the offending construct AND the Plan-B
   phase that adds support.
3. The rejection axes fire in deterministic order
   (formulation → element → material) so error messages stay stable
   across runs.
4. ``LocalisationError`` is exported from
   :mod:`mechdsl.lowering` so callers can ``except`` it cleanly.
5. Catching the broader :class:`UnsupportedError` still works
   (back-compat with the ``.claude/rules/ir.md`` rejection contract).
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
from mechdsl.lowering import LocalisationError, localise
from mechdsl.symbolic.convected import UnsupportedError


def _problem_ir(
    *,
    formulation: Formulation = Formulation.TOTAL_LAGRANGIAN,
    element_type: ElementType = ElementType.HEX8,
    material_model: str = "svk",
) -> ProblemIR:
    return ProblemIR(
        dim=3,
        formulation=formulation,
        element_type=element_type,
        material=MaterialSpec(model=material_model, params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


# ---------------------------------------------------------------------------
# 1. Rejection class hierarchy and exports
# ---------------------------------------------------------------------------


class TestRejectionClassHierarchy:
    @pytest.mark.integration
    def test_localisation_error_subclasses_unsupported_error(self) -> None:
        # Catching UnsupportedError must still trip on a LocalisationError.
        assert issubclass(LocalisationError, UnsupportedError)

    @pytest.mark.integration
    def test_localisation_error_is_re_exported(self) -> None:
        from mechdsl import lowering

        assert hasattr(lowering, "LocalisationError")
        assert "LocalisationError" in lowering.__all__


# ---------------------------------------------------------------------------
# 2. Per-axis rejection: each axis fires deterministically
# ---------------------------------------------------------------------------


class TestPerAxisRejections:
    @pytest.mark.integration
    @pytest.mark.parametrize("elem", [ElementType.TET4, ElementType.TET10, ElementType.HEX20])
    def test_non_hex8_element_rejected_with_phase_pointer(self, elem: ElementType) -> None:
        ir = _problem_ir(element_type=elem)
        with pytest.raises(LocalisationError) as exc:
            localise(ir)
        msg = str(exc.value)
        # Must name the offending element value and the Plan-B phase.
        assert elem.value in msg
        assert "Plan B phase B5" in msg

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "model",
        # Models valid in the IR but outside the lowering allowlist would
        # otherwise be silently accepted. Note: every model below is on the
        # lowering allowlist already; the negative path here is "garbage
        # model name" caught earlier in ProblemIR.__post_init__. So we
        # exercise the lowering rejection by patching `_SUPPORTED_MODELS`
        # via direct call to `_check_stable_path_combo` in the next class.
        ["lemaitre", "perzyna", "neo_hookean"],
    )
    def test_supported_models_dont_raise_at_localise(self, model: str) -> None:
        # Models on the lowering allowlist should NOT trip the rejection
        # path. They may fail later in codegen (Plan-B-specific support)
        # but `localise()` itself accepts them.
        ir = _problem_ir(material_model=model)
        result = localise(ir)
        assert result.problem_ir.material.model == model


class TestSupportedModelsAllowlistGate:
    """Direct exercise of the rejection helper for off-allowlist models."""

    @pytest.mark.integration
    def test_off_allowlist_model_raises_with_phase_pointer(self) -> None:
        # Bypass ProblemIR's own model allowlist to feed the lowering
        # rejection a fabricated unsupported name. The rejection message
        # must name the offending model AND a Plan-B phase pointer.
        from mechdsl.lowering.fe_localise import _check_stable_path_combo

        # Build a minimal IR shell — we only need the .formulation,
        # .element_type, and .material.model fields read by the helper.
        class _FakeMaterial:
            model = "fictional_model_x"

        class _FakeIR:
            formulation = Formulation.TOTAL_LAGRANGIAN
            element_type = ElementType.HEX8
            material = _FakeMaterial()

        with pytest.raises(LocalisationError) as exc:
            _check_stable_path_combo(_FakeIR())  # type: ignore[arg-type]
        msg = str(exc.value)
        assert "fictional_model_x" in msg
        assert "Plan B" in msg


# ---------------------------------------------------------------------------
# 3. Deterministic rejection order (formulation → element → material)
# ---------------------------------------------------------------------------


class TestDeterministicRejectionOrder:
    @pytest.mark.integration
    def test_element_rejection_fires_before_material_rejection(self) -> None:
        # If both axes are unsupported, the element rejection must fire
        # first. We can't easily build a ProblemIR with two unsupported
        # axes (the IR rejects unknown materials at construction), so we
        # exercise the helper directly with a fake IR instead.
        from mechdsl.lowering.fe_localise import _check_stable_path_combo

        class _FakeMaterial:
            model = "fictional_model_x"

        class _FakeIR:
            formulation = Formulation.TOTAL_LAGRANGIAN
            element_type = ElementType.TET4  # unsupported
            material = _FakeMaterial()  # also unsupported

        with pytest.raises(LocalisationError) as exc:
            _check_stable_path_combo(_FakeIR())  # type: ignore[arg-type]
        # The element rejection (axis 2) fires before the material
        # rejection (axis 3) — message must mention the element type, not
        # the material model.
        msg = str(exc.value)
        assert "tet4" in msg
        assert "fictional_model_x" not in msg


# ---------------------------------------------------------------------------
# 4. Catch-as-UnsupportedError back-compat
# ---------------------------------------------------------------------------


class TestUnsupportedErrorBackCompat:
    @pytest.mark.integration
    def test_unsupported_error_catches_localisation_error(self) -> None:
        ir = _problem_ir(element_type=ElementType.TET4)
        with pytest.raises(UnsupportedError) as exc:
            localise(ir)
        assert isinstance(exc.value, LocalisationError)
        # And the broader catch surfaces the same Plan-B pointer.
        assert "Plan B phase B5" in str(exc.value)
