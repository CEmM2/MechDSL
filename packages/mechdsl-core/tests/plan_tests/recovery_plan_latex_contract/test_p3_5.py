"""Live audit for recovery-plan P3-5: targeted IR validation.

P3-5 closes a class of silent acceptance: malformed IRs that used to
construct without error and surface as cryptic codegen / runtime
failures. Each block below pairs a positive case (valid IR builds) with a
negative case (the previously-silent malformed IR now raises a clear
``ValueError`` with a message that names the offending field).

The validations cover:

a. Duplicate boundary region names.
b. BC component indices out of [0, dim).
c. Coordinate-name uniqueness (``coord_spatial`` / ``coord_material``).
d. Duplicate ``FieldSpec.name`` entries.
e. BC ``field_name`` references unknown field.
f. Required material parameters missing for MVP-stable models.

Each negative case must raise *at construction time* (not later in
codegen / runtime), and the message must mention the offending field so
the failure points at the user's IR construction site.
"""

from __future__ import annotations

from typing import Any

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    FieldSpec,
    Formulation,
    MaterialSpec,
    MvpSubsetViolation,
    ProblemIR,
)


def _valid_kwargs(**overrides: Any) -> dict[str, Any]:
    """Canonical valid-IR kwarg dict that downstream tests can perturb."""
    base: dict[str, Any] = dict(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    base.update(overrides)
    return base


class TestBoundaryNameUniqueness:
    """P3-5a: duplicate boundary region names raise at construction time."""

    @pytest.mark.integration
    def test_unique_names_pass(self) -> None:
        ir = ProblemIR(**_valid_kwargs())
        assert {bc.name for bc in ir.boundaries} == {"fix", "load"}

    @pytest.mark.integration
    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"Duplicate boundary condition name 'fix'"):
            ProblemIR(
                **_valid_kwargs(
                    boundaries=(
                        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                        BoundaryCondition(name="fix", bc_type=BCType.NEUMANN, traction="t_bar"),
                    )
                )
            )


class TestComponentRange:
    """P3-5b: BC component indices must lie in [0, dim)."""

    @pytest.mark.integration
    def test_in_range_components_pass(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                boundaries=(
                    BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, components=(0, 1, 2)),
                ),
            )
        )
        assert ir.boundaries[0].components == (0, 1, 2)

    @pytest.mark.integration
    def test_negative_component_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"component index -1 is out of range for dim=3"):
            ProblemIR(
                **_valid_kwargs(
                    boundaries=(
                        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, components=(-1,)),
                    )
                )
            )

    @pytest.mark.integration
    def test_overflow_component_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"component index 3 is out of range for dim=3"):
            ProblemIR(
                **_valid_kwargs(
                    boundaries=(
                        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, components=(0, 3)),
                    )
                )
            )


class TestCoordinateUniqueness:
    """P3-5c: spatial / material coordinate names must be unique."""

    @pytest.mark.integration
    def test_unique_coord_spatial_pass(self) -> None:
        ir = ProblemIR(**_valid_kwargs(coord_spatial=("x", "y", "z")))
        assert ir.coord_spatial == ("x", "y", "z")

    @pytest.mark.integration
    def test_duplicate_coord_spatial_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"coord_spatial=.+duplicate"):
            ProblemIR(**_valid_kwargs(coord_spatial=("x", "x", "z")))

    @pytest.mark.integration
    def test_duplicate_coord_material_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"coord_material=.+duplicate"):
            ProblemIR(**_valid_kwargs(coord_material=("X", "Y", "X")))


class TestFieldNameUniqueness:
    """P3-5d: declared FieldSpec names must be unique."""

    @pytest.mark.integration
    def test_unique_field_names_pass(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                fields=(
                    FieldSpec(name="u", kind="vector"),
                    FieldSpec(name="p", kind="scalar"),
                ),
                boundaries=(
                    BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, field_name="u"),
                ),
            )
        )
        assert {f.name for f in ir.fields} == {"u", "p"}

    @pytest.mark.integration
    def test_duplicate_field_names_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"Duplicate field name 'u'"):
            ProblemIR(
                **_valid_kwargs(
                    fields=(
                        FieldSpec(name="u", kind="vector"),
                        FieldSpec(name="u", kind="scalar"),
                    ),
                )
            )


class TestBcFieldNameConsistency:
    """P3-5e: BC field_name must reference a declared FieldSpec.name."""

    @pytest.mark.integration
    def test_matching_field_name_passes(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                fields=(FieldSpec(name="u", kind="vector"),),
                boundaries=(
                    BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, field_name="u"),
                ),
            )
        )
        assert ir.boundaries[0].field_name == "u"

    @pytest.mark.integration
    def test_unknown_field_name_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"references field 'ux'"):
            ProblemIR(
                **_valid_kwargs(
                    fields=(FieldSpec(name="u", kind="vector"),),
                    boundaries=(
                        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, field_name="ux"),
                    ),
                )
            )

    @pytest.mark.integration
    def test_validation_skipped_when_fields_empty(self) -> None:
        # When `fields` is the default empty tuple, the consistency check is
        # off — pre-P3-1 callers that never set FieldSpec entries continue
        # to construct with the implicit "u" default field_name.
        ir = ProblemIR(
            **_valid_kwargs(
                boundaries=(
                    BoundaryCondition(
                        name="fix", bc_type=BCType.DIRICHLET, field_name="some_other"
                    ),
                )
            )
        )
        assert ir.fields == ()


class TestMvpMaterialParamCompleteness:
    """P3-5f: MVP-stable material models require their full parameter set.

    The check lives in :meth:`ProblemIR.assert_mvp_stable` (not
    ``__post_init__``) so in-tree research code that builds minimal IRs
    for shape-only testing keeps working. The canonical compile path
    (:func:`mechdsl.compile_latex`) calls ``assert_mvp_stable`` and
    therefore enforces the contract at the user-visible boundary.
    """

    @pytest.mark.integration
    def test_complete_svk_params_pass_mvp_check(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
            )
        )
        ir.assert_mvp_stable()
        assert ir.is_mvp_stable() is True

    @pytest.mark.integration
    def test_minimal_svk_constructs_but_fails_mvp_check(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                material=MaterialSpec(model="svk", params={"E": 200e3}),
            )
        )
        assert ir.is_mvp_stable() is False
        with pytest.raises(MvpSubsetViolation, match=r"Material model 'svk' requires"):
            ir.assert_mvp_stable()

    @pytest.mark.integration
    def test_complete_j2_power_law_params_pass_mvp_check(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                material=MaterialSpec(
                    model="j2_power_law",
                    params={
                        "E": 200e3,
                        "nu": 0.3,
                        "sigma_y0": 250.0,
                        "K": 1000.0,
                        "n": 10.0,
                    },
                ),
            )
        )
        ir.assert_mvp_stable()

    @pytest.mark.integration
    def test_missing_j2_power_law_params_fails_mvp_check(self) -> None:
        ir = ProblemIR(
            **_valid_kwargs(
                material=MaterialSpec(
                    model="j2_power_law",
                    params={"E": 200e3, "nu": 0.3},
                ),
            )
        )
        with pytest.raises(MvpSubsetViolation, match=r"Material model 'j2_power_law' requires"):
            ir.assert_mvp_stable()

    @pytest.mark.integration
    def test_experimental_model_skips_required_check_at_post_init(self) -> None:
        # `lemaitre` is a known-but-experimental model — it still passes
        # the model-name allowlist (so legacy code keeps working). The IR
        # constructs cleanly, and the required-params table omits the
        # model so no spurious failure surfaces at construction time.
        ir = ProblemIR(
            **_valid_kwargs(
                material=MaterialSpec(model="lemaitre", params={}),
            )
        )
        assert ir.material.model == "lemaitre"
        # `assert_mvp_stable` still rejects it, but on the higher-level
        # "lemaitre is not in the MVP-stable materials axis" ground.
        assert ir.is_mvp_stable() is False


class TestErrorsRaiseAtConstructionTime:
    """Aggregate acceptance criterion: schema-shape violations raise in __post_init__.

    The required-material-params check (P3-5f) lives on the compile-path
    boundary instead of ``__post_init__`` — see
    :class:`TestMvpMaterialParamCompleteness` for that surface.
    """

    @pytest.mark.integration
    @pytest.mark.parametrize(
        "kwargs, match",
        [
            (
                {
                    "boundaries": (
                        BoundaryCondition(name="dup", bc_type=BCType.DIRICHLET),
                        BoundaryCondition(name="dup", bc_type=BCType.NEUMANN, traction="t_bar"),
                    )
                },
                r"Duplicate boundary",
            ),
            (
                {
                    "boundaries": (
                        BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET, components=(99,)),
                    )
                },
                r"out of range",
            ),
            ({"coord_spatial": ("x", "x", "z")}, r"coord_spatial=.+duplicate"),
        ],
    )
    def test_each_violation_raises_in_post_init(self, kwargs: dict[str, Any], match: str) -> None:
        with pytest.raises(ValueError, match=match):
            ProblemIR(**_valid_kwargs(**kwargs))
