"""End-to-end pipeline tests: ProblemIR -> IR -> lower -> optimize -> codegen.

Phase 2 (LaTeX frontend) is BLOCKED, so the pipeline starts from ProblemIR.
The full LaTeX -> solution e2e requires Phase 2 (NRPyLaTeX fork).

Test tiers:
  - TestEmissionPipelineSmoke: fast structural checks (ast.parse + pattern matching)
  - TestGeneratedCodeImport: slow — writes emitted module to disk and imports it,
    catching undeclared runtime dependencies and import-time errors
  - TestLocalisationE2E / TestArtifactRoundTrip: pipeline component checks
"""

from __future__ import annotations

import ast

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise, localise_and_optimize

pytestmark = [pytest.mark.e2e, pytest.mark.from_problem_ir]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_elastic_problem_ir() -> ProblemIR:
    """Create SVK elastic ProblemIR."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


def _make_plastic_problem_ir() -> ProblemIR:
    """Create J2 power-law plastic ProblemIR."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": 200e3,
                "nu": 0.3,
                "sigma_y0": 250.0,
                "K": 500.0,
                "n": 1.0,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


def _run_full_pipeline(problem_ir: ProblemIR) -> tuple[ArtifactBundle, str]:
    """Run the full pipeline: ProblemIR -> lower -> optimize -> emit.

    Returns the artifact bundle and emitted source.
    """
    # 1. Lower + optimize
    loc_result, plans = localise_and_optimize(problem_ir)

    # 2. Build artifact bundle
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)

    # 3. Emit Taichi source
    source = emit(bundle)

    return bundle, source


# ===========================================================================
# P9.1: Full pipeline e2e test
# ===========================================================================


class TestEmissionPipelineSmoke:
    """Emission pipeline smoke tests: structural/syntactic checks only.

    These tests verify the pipeline produces syntactically valid, structurally
    complete Taichi source.  They do NOT import or execute the emitted code —
    see TestGeneratedCodeImport for that.
    """

    def test_elastic_pipeline(self):
        """SVK elastic: ProblemIR -> LocalisationResult -> ArtifactBundle -> Taichi source."""
        problem_ir = _make_elastic_problem_ir()

        # 1. Lower + optimize
        loc_result, plans = localise_and_optimize(problem_ir)

        # Validate localisation result
        assert loc_result.element_ir is not None
        assert loc_result.element_ir.n_nodes == 8
        assert loc_result.element_ir.dim == 3
        assert len(loc_result.einsum_specs) == 3  # strain_disp, internal_force, tangent
        assert loc_result.problem_ir is problem_ir

        # Validate contraction plans
        assert len(plans) == 3
        for plan in plans:
            assert plan.einsum_string
            assert plan.tier > 0  # all should be classified

        # 2. Build artifact
        bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
        assert bundle.problem_ir_dict["material"]["model"] == "svk"
        assert bundle.element_ir_summary["element_type"] == "hex8"

        # 3. Emit
        source = emit(bundle)

        # 4. Verify: syntactically valid Python
        ast.parse(source)

        # 5. Verify: key functions present
        assert "constitutive_update" in source
        assert "compute_internal_force" in source
        assert "newton_solve" in source
        assert "tangent_matvec" in source
        assert "allocate_fields" in source

        # 6. Verify: Taichi-specific patterns
        assert "import taichi as ti" in source
        assert "ti.init(" in source
        assert "@ti.func" in source
        assert "@ti.kernel" in source
        assert "ti.f64" in source

        # 7. Verify: no f32 (all f64 as per spec)
        assert "ti.f32" not in source

    def test_plastic_pipeline(self):
        """J2 plastic: same pipeline with j2_power_law material."""
        problem_ir = _make_plastic_problem_ir()

        # Run full pipeline
        loc_result, plans = localise_and_optimize(problem_ir)
        bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
        source = emit(bundle)

        # Syntactically valid
        ast.parse(source)

        # J2-specific patterns
        assert "constitutive_update_plastic" in source
        assert "compute_internal_force" in source
        assert "newton_solve" in source
        assert "tangent_matvec" in source

        # Plasticity-specific: alpha history field and radial return
        assert "alpha" in source
        assert "sigma_y0" in source
        assert "radial return" in source.lower() or "sigma_eq" in source

        # J2 material parameters should appear in the constitutive function
        assert "K_hard" in source or "n_hard" in source

    def test_pipeline_deterministic(self):
        """Same input produces identical output."""
        problem_ir = _make_elastic_problem_ir()

        _, source_a = _run_full_pipeline(problem_ir)
        _, source_b = _run_full_pipeline(problem_ir)

        assert source_a == source_b, "Pipeline is not deterministic"

    def test_pipeline_deterministic_plastic(self):
        """Determinism also holds for the plastic pipeline."""
        problem_ir = _make_plastic_problem_ir()

        _, source_a = _run_full_pipeline(problem_ir)
        _, source_b = _run_full_pipeline(problem_ir)

        assert source_a == source_b, "Plastic pipeline is not deterministic"

    def test_pipeline_rejects_unsupported_formulation(self):
        """Unsupported formulation rejected at IR level."""
        # ProblemIR.__post_init__ validates formulation at construction time.
        # There is no way to construct a ProblemIR with an unsupported formulation
        # because the Formulation enum only has TOTAL_LAGRANGIAN.
        # Instead, verify localise rejects ElementType mismatch (if we could
        # construct one). Here we verify via the ProblemIR constructor.
        with pytest.raises(ValueError, match="dim=2 not supported"):
            ProblemIR(
                dim=2,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
            )

    def test_pipeline_rejects_unknown_material(self):
        """Unknown material model rejected at ProblemIR construction."""
        with pytest.raises(ValueError, match="Unknown material model"):
            ProblemIR(
                dim=3,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="lemaitre_damage", params={}),
                boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
            )

    def test_pipeline_rejects_no_boundaries(self):
        """At least one boundary condition required."""
        with pytest.raises(ValueError, match="At least one boundary condition"):
            ProblemIR(
                dim=3,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
                boundaries=(),
            )


# ===========================================================================
# Localisation-specific e2e checks
# ===========================================================================


class TestLocalisationE2E:
    """Verify localisation pass produces consistent results."""

    def test_einsum_specs_complete(self):
        """All three einsum specs present: strain_displacement, internal_force, tangent_matvec."""
        problem_ir = _make_elastic_problem_ir()
        loc_result = localise(problem_ir)

        spec_names = {s.name for s in loc_result.einsum_specs}
        assert "strain_displacement" in spec_names
        assert "internal_force" in spec_names
        assert "tangent_matvec" in spec_names

    def test_einsum_shapes_consistent(self):
        """Einsum operand shapes are consistent with Hex8 3D element."""
        problem_ir = _make_elastic_problem_ir()
        loc_result = localise(problem_ir)

        for spec in loc_result.einsum_specs:
            # All shapes should involve dim=3 and n_nodes=8
            for shape in spec.operand_shapes:
                for dim_val in shape:
                    assert dim_val in (3, 8, 9, 24, 27, 64, 192, 576), (
                        f"Unexpected dimension {dim_val} in {spec.name} operand shape {shape}"
                    )


# ===========================================================================
# Artifact bundle round-trip e2e
# ===========================================================================


class TestArtifactRoundTrip:
    """Artifact bundle serialisation round-trip from pipeline."""

    def test_elastic_bundle_round_trip(self):
        """Elastic bundle survives JSON round-trip."""
        problem_ir = _make_elastic_problem_ir()
        bundle, source = _run_full_pipeline(problem_ir)

        # Add source to bundle for complete round-trip
        bundle_with_source = ArtifactBundle(
            problem_ir_dict=bundle.problem_ir_dict,
            element_ir_summary=bundle.element_ir_summary,
            contraction_plans=bundle.contraction_plans,
            emitted_source=source,
            metadata=bundle.metadata,
        )

        json_str = bundle_with_source.to_json()
        restored = ArtifactBundle.from_json(json_str=json_str)

        assert restored.problem_ir_dict == bundle.problem_ir_dict
        assert restored.element_ir_summary == bundle.element_ir_summary
        assert restored.emitted_source == source
        assert len(restored.contraction_plans) == len(bundle.contraction_plans)

    def test_content_hash_stable(self):
        """Content hash is stable across runs."""
        problem_ir = _make_elastic_problem_ir()
        bundle_a, _ = _run_full_pipeline(problem_ir)
        bundle_b, _ = _run_full_pipeline(problem_ir)

        assert bundle_a.content_hash() == bundle_b.content_hash()

    def test_content_hash_differs_for_different_materials(self):
        """Different materials produce different content hashes."""
        bundle_elastic, _ = _run_full_pipeline(_make_elastic_problem_ir())
        bundle_plastic, _ = _run_full_pipeline(_make_plastic_problem_ir())

        assert bundle_elastic.content_hash() != bundle_plastic.content_hash()


# ===========================================================================
# Generated code import verification (catches undeclared runtime deps)
# ===========================================================================


@pytest.mark.slow
class TestGeneratedCodeImport:
    """Write emitted module to disk and import it.

    Catches runtime dependency gaps (e.g. missing imports) that ast.parse
    alone cannot detect.  Requires a working Python environment with all
    declared dependencies installed.
    """

    def test_elastic_module_imports(self, tmp_path):
        """Emitted elastic SVK module is importable."""
        import importlib.util

        problem_ir = _make_elastic_problem_ir()
        _, source = _run_full_pipeline(problem_ir)

        mod_path = tmp_path / "gen_elastic.py"
        mod_path.write_text(source)

        spec = importlib.util.spec_from_file_location("gen_elastic", mod_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except ImportError as exc:
            pytest.fail(f"Generated elastic module failed to import: {exc}")

        # Verify expected callable attributes exist
        assert hasattr(mod, "newton_solve")
        assert hasattr(mod, "allocate_fields")
        assert callable(mod.newton_solve)

    def test_plastic_module_imports(self, tmp_path):
        """Emitted J2 plastic module is importable."""
        import importlib.util

        problem_ir = _make_plastic_problem_ir()
        _, source = _run_full_pipeline(problem_ir)

        mod_path = tmp_path / "gen_plastic.py"
        mod_path.write_text(source)

        spec = importlib.util.spec_from_file_location("gen_plastic", mod_path)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except ImportError as exc:
            pytest.fail(f"Generated plastic module failed to import: {exc}")
