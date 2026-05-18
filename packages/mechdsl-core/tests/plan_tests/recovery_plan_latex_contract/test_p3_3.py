"""Live audit for recovery-plan P3-3: boundary/domain assumptions on the IR.

P3-3 moves the previously-scattered "BC name == mesh boundary tag"
assumption into the IR layer:

- :meth:`ProblemIR.required_region_tags` enumerates the mesh region tags
  the problem needs in one place.
- :meth:`ProblemIR.derived_mesh_contract` materializes a
  :class:`MeshContract` (either the explicit one or one synthesized from
  the BC names) so downstream consumers never branch on
  ``mesh_contract is None``.
- :func:`mechdsl.solver.mesh_io.validate_mesh_against_contract` is the
  single check that the runtime mesh carries every region the IR needs;
  pre-P3-3 each consumer (assemblers, codegen runtime, BC compilers)
  re-derived the lookup as ``mesh.boundary_tags[bc.name]`` and surfaced
  the failure as a deep ``KeyError``.

These tests verify the new helpers exist, return consistent answers, and
that the duplication-reduction goal is met by exercising the full
``ProblemIR → MeshContract → HexMesh`` validation path.
"""

from __future__ import annotations

import pytest

from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    BoundaryRegionError,
    ElementType,
    Formulation,
    MaterialSpec,
    MeshContract,
    ProblemIR,
)
from mechdsl.solver.mesh_io import generate_hex8_mesh, validate_mesh_against_contract


def _mvp_problem(*, mesh_contract: MeshContract | None = None) -> ProblemIR:
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="x0", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="x1", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
        mesh_contract=mesh_contract,
    )


class TestRequiredRegionTags:
    """`required_region_tags` is the single source of truth for required regions."""

    @pytest.mark.regression
    def test_default_returns_bc_names_in_order(self) -> None:
        ir = _mvp_problem()
        assert ir.required_region_tags() == ("x0", "x1")

    @pytest.mark.regression
    def test_explicit_mesh_contract_takes_priority(self) -> None:
        # Explicit names lead so documentation order is preserved.
        ir = _mvp_problem(mesh_contract=MeshContract(region_tags=("x0", "x1")))
        assert ir.required_region_tags() == ("x0", "x1")

    @pytest.mark.regression
    def test_explicit_contract_extras_appear_first(self) -> None:
        # MeshContract may declare regions the BCs do not yet reference
        # (planned future BCs, mesh-validation-only tags). They must come
        # first in the result so MeshContract's own ordering wins.
        ir = _mvp_problem(
            mesh_contract=MeshContract(region_tags=("future_bc", "x0", "x1")),
        )
        assert ir.required_region_tags() == ("future_bc", "x0", "x1")

    @pytest.mark.regression
    def test_bc_only_names_appended_when_missing_from_contract(self) -> None:
        # If the contract enumerates only some BC names, the rest are
        # appended in BC-declaration order (so nothing silently drops).
        ir = _mvp_problem(mesh_contract=MeshContract(region_tags=("x0",)))
        assert ir.required_region_tags() == ("x0", "x1")


class TestDerivedMeshContract:
    """`derived_mesh_contract` materializes a usable contract for every IR."""

    @pytest.mark.regression
    def test_returns_explicit_contract_unchanged(self) -> None:
        explicit = MeshContract(region_tags=("x0", "x1"), metadata={"min_elements": 8})
        ir = _mvp_problem(mesh_contract=explicit)
        # Identity, not equality — same object passes through, so callers
        # see the explicit metadata bag without a copy round-trip.
        assert ir.derived_mesh_contract() is explicit

    @pytest.mark.regression
    def test_synthesizes_when_implicit(self) -> None:
        ir = _mvp_problem()
        derived = ir.derived_mesh_contract()
        assert isinstance(derived, MeshContract)
        assert derived.region_tags == ("x0", "x1")
        # The synthesized contract has empty metadata; that is the marker
        # downstream tests can use to tell synthesized from explicit.
        assert dict(derived.metadata) == {}

    @pytest.mark.regression
    def test_required_tags_match_derived_contract_tags(self) -> None:
        # Invariant: the two helpers always agree on the tag set so
        # downstream layers can pick either entry point.
        ir = _mvp_problem(
            mesh_contract=MeshContract(region_tags=("future_bc", "x0", "x1")),
        )
        assert ir.required_region_tags() == ir.derived_mesh_contract().region_tags


class TestValidateMeshAgainstContract:
    """The mesh / IR boundary check raises BoundaryRegionError on mismatch."""

    @pytest.mark.regression
    def test_fully_tagged_mesh_passes(self) -> None:
        mesh = generate_hex8_mesh(nx=2, ny=2, nz=2, Lx=1.0, Ly=1.0, Lz=1.0)
        ir = _mvp_problem()
        # Should not raise — the structured mesh tags x0/x1/y0/y1/z0/z1 by
        # default, which covers what the IR needs.
        validate_mesh_against_contract(mesh, ir.derived_mesh_contract())

    @pytest.mark.regression
    def test_missing_tag_raises_boundary_region_error(self) -> None:
        mesh = generate_hex8_mesh(nx=2, ny=2, nz=2, Lx=1.0, Ly=1.0, Lz=1.0)
        # Drop the tag the IR will require. The mesh is now incomplete.
        del mesh.boundary_tags["x1"]
        ir = _mvp_problem()
        with pytest.raises(BoundaryRegionError, match=r"missing required boundary tags \['x1'\]"):
            validate_mesh_against_contract(mesh, ir.derived_mesh_contract())

    @pytest.mark.regression
    def test_error_message_lists_mesh_and_contract_tags(self) -> None:
        mesh = generate_hex8_mesh(nx=2, ny=2, nz=2, Lx=1.0, Ly=1.0, Lz=1.0)
        ir = _mvp_problem(
            mesh_contract=MeshContract(region_tags=("nonexistent", "x0", "x1")),
        )
        with pytest.raises(BoundaryRegionError) as exc:
            validate_mesh_against_contract(mesh, ir.derived_mesh_contract())
        # The user needs both halves of the mismatch in the message to see
        # what's wrong — pre-P3-3 a bare KeyError gave them only one half.
        assert "nonexistent" in str(exc.value)
        assert "x0" in str(exc.value)


class TestDuplicationReductionInvariant:
    """Sanity guard: helpers ship from the IR module, not duplicated downstream."""

    @pytest.mark.regression
    def test_helpers_live_on_problem_ir(self) -> None:
        # If a future refactor moves these to a downstream layer, the
        # duplication this PR removed will return — surface the regression.
        assert hasattr(ProblemIR, "required_region_tags")
        assert hasattr(ProblemIR, "derived_mesh_contract")
        assert callable(ProblemIR.required_region_tags)
        assert callable(ProblemIR.derived_mesh_contract)

    @pytest.mark.regression
    def test_validate_helper_lives_on_solver_mesh_io(self) -> None:
        # The mesh ↔ IR-contract bridge is owned by `solver.mesh_io` —
        # asserting the import path here keeps consumers off ad-hoc copies.
        from mechdsl.solver import mesh_io

        assert hasattr(mesh_io, "validate_mesh_against_contract")
        assert callable(mesh_io.validate_mesh_against_contract)
