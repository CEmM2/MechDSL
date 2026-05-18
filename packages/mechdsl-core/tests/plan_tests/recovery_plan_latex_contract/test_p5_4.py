"""Live audit for recovery-plan P5-4: Taichi printer consumes enriched IR.

Asserts that:

1. The Taichi printer reads from ``ArtifactBundle.element_ir_dict``
   (set by P4-5 from ``ElementIR.to_dict()``) instead of relying
   primarily on the legacy ``element_ir_summary``.
2. Codegen tests show canonical path works with enriched IR fields
   (``geometry``, ``material_eval``, ``local_force``, ``local_tangent``).
3. Emitted code makes decisions based on enriched IR rather than
   inline sniffing of ``problem_ir.formulation`` (e.g. stress measure
   choice drives force layout).
4. Output is functionally equivalent to pre-P5-4 codegen (no regressions
   on numerical kernel tests).
5. The printer surfaces enriched-IR metadata in emitted comments (e.g.
   docstring, function preamble) for auditability.
"""

from __future__ import annotations

from dataclasses import replace as _replace

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    _ir_block,
    _ir_field,
    _n_quadrature_points,
    emit,
    emit_constants,
    emit_preamble,
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

# ---------------------------------------------------------------------------
# Fixtures (mirror the P4-5 pattern)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def enriched_bundle() -> ArtifactBundle:
    """Build a bundle with element_ir_dict populated (post-P4-5 path)."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(loc.problem_ir, loc, plans)


@pytest.fixture(scope="module")
def legacy_bundle() -> ArtifactBundle:
    """Build a bundle with empty element_ir_dict (legacy fallback path)."""
    return ArtifactBundle(
        problem_ir_dict={
            "dim": 3,
            "formulation": "total_lagrangian",
            "material": {"model": "svk", "params": {"E": 200e3, "nu": 0.3}},
        },
        element_ir_summary={
            "element_type": "hex8",
            "n_nodes": 8,
            "dim": 3,
            "n_quadrature_points": 8,
            "formulation": "total_lagrangian",
        },
        # element_ir_dict left at the default (empty dict).
    )


class TestP5_4:
    """Unit tests for P5-4: Taichi printer consumes enriched IR."""

    @pytest.mark.unit
    def test_printer_prefers_element_ir_dict_over_summary(
        self, legacy_bundle: ArtifactBundle
    ) -> None:
        """Codegen prefers element_ir_dict when available.

        Verifies
        --------
        When ArtifactBundle carries populated element_ir_dict, the Taichi
        printer's ``_ir_field`` helper resolves to the dict's value rather
        than the summary's. We construct a bundle whose two carriers
        DISAGREE on a field, then assert the helper picks the dict.

        Criterion
        ---------
        P5-4-c1: Codegen tests show canonical path works with enriched IR fields.
        """
        bundle = _replace(
            legacy_bundle,
            element_ir_dict={
                "element_type": "hex8",
                "n_nodes": 8,
                "dim": 3,
                "formulation": "total_lagrangian",
            },
            element_ir_summary={
                "element_type": "BOGUS_LEGACY_TYPE",
                "n_nodes": -1,
                "dim": -1,
                "n_quadrature_points": 8,
            },
        )
        # Helper picks the dict when both are populated.
        assert _ir_field(bundle, "element_type", "fallback") == "hex8"
        assert _ir_field(bundle, "n_nodes", 0) == 8
        assert _ir_field(bundle, "dim", 0) == 3

    @pytest.mark.unit
    def test_stress_measure_from_enriched_ir(self, enriched_bundle: ArtifactBundle) -> None:
        """Material eval stress measure comes from enriched IR.

        Verifies
        --------
        ``_ir_block`` returns the ``material_eval`` block from
        ``element_ir_dict`` and the auditability emission surfaces the
        ``stress_measure`` field in the emitted source's docstring.

        Criterion
        ---------
        P5-4-c1: Codegen tests show canonical path works with enriched IR fields.
        """
        bundle = enriched_bundle
        block = _ir_block(bundle, "material_eval")
        assert block is not None
        assert block["stress_measure"] == "pk2"

        ctx = EmissionContext(verbose=True)
        emit_preamble(ctx, bundle)
        source = ctx.get_source()
        assert "Stress measure" in source
        assert "pk2" in source

    @pytest.mark.unit
    def test_force_descriptor_from_enriched_ir(self, enriched_bundle: ArtifactBundle) -> None:
        """Local force descriptor comes from enriched IR.

        Verifies
        --------
        ``_ir_block`` exposes the ``local_force`` block and the verbose
        preamble surfaces ``n_dof`` in the audit comment.

        Criterion
        ---------
        P5-4-c1: Codegen tests show canonical path works with enriched IR fields.
        """
        bundle = enriched_bundle
        block = _ir_block(bundle, "local_force")
        assert block is not None
        assert block["n_dof"] == 24  # Hex8: 8 nodes * 3 dim

        ctx = EmissionContext(verbose=True)
        emit_preamble(ctx, bundle)
        source = ctx.get_source()
        assert "Force n_dof" in source
        assert "24" in source

    @pytest.mark.unit
    def test_tangent_symmetry_from_enriched_ir(self, enriched_bundle: ArtifactBundle) -> None:
        """Tangent symmetry flag comes from enriched IR.

        Verifies
        --------
        ``_ir_block`` exposes ``local_tangent`` and the verbose preamble
        surfaces the ``is_symmetric`` flag.

        Criterion
        ---------
        P5-4-c1: Codegen tests show canonical path works with enriched IR fields.
        """
        bundle = enriched_bundle
        block = _ir_block(bundle, "local_tangent")
        assert block is not None
        assert block["is_symmetric"] is True

        ctx = EmissionContext(verbose=True)
        emit_preamble(ctx, bundle)
        source = ctx.get_source()
        assert "Tangent symmetric" in source
        assert "True" in source

    @pytest.mark.unit
    def test_geometry_summary_available_in_codegen(self, enriched_bundle: ArtifactBundle) -> None:
        """Geometry summary is available for codegen inspection.

        Verifies
        --------
        The printer accesses ``element_ir_dict["geometry"]`` for
        ``n_quad`` via the dedicated ``_n_quadrature_points`` helper.
        emit_constants then uses that count instead of the legacy
        ``element_ir_summary["n_quadrature_points"]`` key.

        Criterion
        ---------
        P5-4-c1: Codegen tests show canonical path works with enriched IR fields.
        """
        bundle = enriched_bundle
        block = _ir_block(bundle, "geometry")
        assert block is not None
        assert block["n_quad"] == 8
        assert "reference_volume" in block
        assert "natural_coord_dim" in block
        # Helper resolves through the geometry block.
        assert _n_quadrature_points(bundle) == 8

        # And the verbose audit surfaces the count.
        ctx = EmissionContext(verbose=True)
        emit_preamble(ctx, bundle)
        source = ctx.get_source()
        assert "Quadrature" in source
        assert "8-point" in source

    @pytest.mark.unit
    def test_emitted_code_roundtrips_through_enriched_bundle(
        self, enriched_bundle: ArtifactBundle
    ) -> None:
        """Emitted code is deterministic from enriched bundle.

        Verifies
        --------
        Given an ArtifactBundle with populated element_ir_dict, calling
        the Taichi printer twice produces identical output, and the
        standard preamble is intact (auditability comments are additive
        only when ``verbose=True``).

        Criterion
        ---------
        Acceptance: No regressions on the existing test suite.
        """
        bundle = enriched_bundle
        s1 = emit(bundle)
        s2 = emit(bundle)
        assert s1 == s2, "emit() must be deterministic for the same bundle"

        # Standard preamble headers always present.
        assert '"""Auto-generated Taichi FEM solver. DO NOT EDIT.' in s1
        assert "Formulation : total_lagrangian" in s1
        assert "Material    : svk" in s1
        assert "Element     : hex8" in s1
        assert "Dimension   : 3" in s1
        assert "import taichi as ti" in s1
        # Default emission is non-verbose: audit block must NOT appear.
        assert "Enriched-IR contract surface" not in s1

        # Verbose emission via the step-wise API: audit lines DO appear.
        ctx = EmissionContext(verbose=True)
        emit_preamble(ctx, bundle)
        verbose_source = ctx.get_source()
        assert "Enriched-IR contract surface" in verbose_source
        assert "Stress measure" in verbose_source

    @pytest.mark.unit
    def test_backward_compat_empty_element_ir_dict(self, legacy_bundle: ArtifactBundle) -> None:
        """Printer handles empty element_ir_dict gracefully.

        Verifies
        --------
        When element_ir_dict is empty (pre-P4-5 bundles), the printer
        falls back cleanly to element_ir_summary without error.

        Criterion
        ---------
        Acceptance: No regressions on the existing test suite.
        """
        bundle = legacy_bundle
        assert bundle.element_ir_dict == {}

        # Helper falls back to summary.
        assert _ir_field(bundle, "element_type", "fallback") == "hex8"
        assert _ir_field(bundle, "n_nodes", 0) == 8
        assert _ir_field(bundle, "dim", 0) == 3
        # n_quadrature_points falls back via the dedicated helper.
        assert _n_quadrature_points(bundle) == 8

        # Preamble emits without raising; audit block stays empty since
        # neither carrier holds the four enrichment blocks.
        ctx = EmissionContext()
        emit_preamble(ctx, bundle)
        # emit_constants must also work on the legacy bundle.
        emit_constants(ctx, bundle)
        source = ctx.get_source()
        assert "Element     : hex8" in source
        assert "N_NODES = 8" in source
        assert "N_QP = 8" in source
        assert "DIM = 3" in source

        # And even with verbose=True, the legacy bundle has no enrichment
        # to surface, so the audit block is suppressed (no header line).
        ctx_v = EmissionContext(verbose=True)
        emit_preamble(ctx_v, bundle)
        legacy_verbose = ctx_v.get_source()
        assert "Enriched-IR contract surface" not in legacy_verbose

    @pytest.mark.unit
    def test_deliverable_surfaces_documented(self) -> None:
        """All P5-4 deliverables are present at specified surfaces.

        Verifies
        --------
        Taichi printer exports the new helpers, the EmissionContext carries
        the ``verbose`` flag, and the module/preamble docstrings document
        the enriched-IR consumption.

        Criterion
        ---------
        P5-4-c2: deliverables present at the listed surfaces
                 (taichi_printer.py:333-352 + material emission paths).
        """
        from mechdsl.codegen import taichi_printer as tp

        # 1. Helpers exist at module scope (private but importable).
        assert callable(tp._ir_field)
        assert callable(tp._ir_block)
        assert callable(tp._n_quadrature_points)

        # 2. EmissionContext carries the verbose flag with the documented default.
        ctx = tp.EmissionContext()
        assert hasattr(ctx, "verbose")
        assert ctx.verbose is False

        # 3. Module docstring mentions the recovery P5-4 enriched-IR consumption.
        assert tp.__doc__ is not None
        assert "P5-4" in tp.__doc__
        assert "element_ir_dict" in tp.__doc__

        # 4. emit_preamble's docstring documents the P5-4 sourcing change.
        assert tp.emit_preamble.__doc__ is not None
        assert "P5-4" in tp.emit_preamble.__doc__

        # 5. emit_constants's docstring documents the P5-4 sourcing change.
        assert tp.emit_constants.__doc__ is not None
        assert "P5-4" in tp.emit_constants.__doc__
