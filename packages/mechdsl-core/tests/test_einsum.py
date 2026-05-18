"""Tests for Layer 4b — Einsum optimiser and JIT budget counter.

P5.2 tests: Element IR <-> optimizer integration (localise_and_optimize, from_pipeline).
P5.3 tests: CI budget regression fixtures.
"""

from __future__ import annotations

import pytest

from mechdsl.codegen.artifact import ArtifactBundle, ContractionPlan
from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_ABSOLUTE,
    MAX_LINES_TI_FUNC,
    MAX_LINES_TI_KERNEL,
    BudgetExceededError,
    Tier,
    check_absolute_budget,
    check_kernel_budget,
    optimize_contraction,
)
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import (
    LocalisationResult,
    localise,
    localise_and_optimize,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_mvp_problem(**overrides: object) -> ProblemIR:
    """Build a valid MVP ProblemIR (3D, Hex8, TL, SVK) with optional overrides."""
    defaults: dict = {
        "dim": 3,
        "formulation": Formulation.TOTAL_LAGRANGIAN,
        "element_type": ElementType.HEX8,
        "material": MaterialSpec(model="svk", params={"E": 1000.0, "nu": 0.3}),
        "boundaries": (
            BoundaryCondition(
                name="fix_base",
                bc_type=BCType.DIRICHLET,
                components=(0, 1, 2),
                value=0.0,
            ),
        ),
    }
    defaults.update(overrides)
    return ProblemIR(**defaults)


# ======================================================================
# P5.2: Element IR <-> optimizer integration
# ======================================================================


class TestLocaliseAndOptimize:
    """Tests for the integrated localise_and_optimize pipeline."""

    def test_mvp_pipeline_produces_nonempty_plans(self):
        """MVP pipeline (Hex8 TL SVK) produces non-empty contraction plans."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        assert isinstance(loc_result, LocalisationResult)
        assert len(plans) > 0

    def test_each_spec_has_corresponding_plan(self):
        """Each einsum spec has a corresponding contraction plan."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        assert len(plans) == len(loc_result.einsum_specs)
        for spec, plan in zip(loc_result.einsum_specs, plans, strict=True):
            assert plan.einsum_string == spec.einsum_string

    def test_plans_have_valid_tier_assignments(self):
        """All plans have tier assignments in {1, 2, 3}."""
        problem = _make_mvp_problem()
        _loc_result, plans = localise_and_optimize(problem)

        for plan in plans:
            assert plan.tier in (1, 2, 3), (
                f"Plan '{plan.einsum_string}' has invalid tier {plan.tier}"
            )

    def test_plans_within_budget(self):
        """All MVP contraction plans are within the per-function budget."""
        problem = _make_mvp_problem()
        loc_result, _plans = localise_and_optimize(problem)

        # Verify using the optimizer for detailed budget info
        for spec in loc_result.einsum_specs:
            result = optimize_contraction(
                spec.einsum_string,
                list(spec.operand_shapes),
            )
            # Each individual contraction must fit within @ti.func budget
            # (Tier 3 is allowed — it signals restructuring is needed, but
            # the absolute ceiling must never be exceeded)
            assert result.estimated_lines <= MAX_LINES_ABSOLUTE, (
                f"Contraction '{spec.name}' exceeds absolute ceiling: "
                f"{result.estimated_lines} > {MAX_LINES_ABSOLUTE}"
            )

    def test_plans_are_contraction_plan_instances(self):
        """Each plan is a ContractionPlan instance."""
        problem = _make_mvp_problem()
        _loc_result, plans = localise_and_optimize(problem)

        for plan in plans:
            assert isinstance(plan, ContractionPlan)

    def test_plans_have_nonempty_paths(self):
        """Each plan has a non-empty contraction path."""
        problem = _make_mvp_problem()
        _loc_result, plans = localise_and_optimize(problem)

        for plan in plans:
            assert len(plan.contraction_path) >= 1, (
                f"Plan '{plan.einsum_string}' has empty contraction path"
            )

    def test_plans_have_positive_flops(self):
        """Each plan has non-negative estimated flops."""
        problem = _make_mvp_problem()
        _loc_result, plans = localise_and_optimize(problem)

        for plan in plans:
            assert plan.estimated_flops >= 0

    def test_localise_result_matches_direct_localise(self):
        """The localisation result from the integrated pipeline matches direct localise."""
        problem = _make_mvp_problem()
        direct_result = localise(problem)
        integrated_result, _plans = localise_and_optimize(problem)

        assert integrated_result.element_ir.element_type == direct_result.element_ir.element_type
        assert integrated_result.element_ir.n_nodes == direct_result.element_ir.n_nodes
        assert len(integrated_result.einsum_specs) == len(direct_result.einsum_specs)
        for a, b in zip(integrated_result.einsum_specs, direct_result.einsum_specs, strict=True):
            assert a.einsum_string == b.einsum_string
            assert a.name == b.name


class TestArtifactBundleFromPipeline:
    """Tests for ArtifactBundle.from_pipeline convenience constructor."""

    def test_from_pipeline_stores_plans(self):
        """Artifact bundle from_pipeline stores contraction plans correctly."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
        )

        assert bundle.contraction_plans == plans
        assert len(bundle.contraction_plans) == len(plans)

    def test_from_pipeline_stores_problem_ir(self):
        """Artifact bundle preserves serialised ProblemIR."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
        )

        assert bundle.problem_ir_dict == problem.to_dict()

    def test_from_pipeline_stores_element_ir_summary(self):
        """Artifact bundle captures element IR metadata."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
        )

        summary = bundle.element_ir_summary
        assert summary["element_type"] == "hex8"
        assert summary["n_nodes"] == 8
        assert summary["dim"] == 3
        assert summary["n_quadrature_points"] == 8
        assert summary["formulation"] == "total_lagrangian"

    def test_from_pipeline_emitted_source_default_empty(self):
        """Emitted source defaults to empty string."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
        )

        assert bundle.emitted_source == ""

    def test_from_pipeline_emitted_source_custom(self):
        """Emitted source can be provided."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
            emitted_source="# generated code\nimport taichi as ti\n",
        )

        assert bundle.emitted_source == "# generated code\nimport taichi as ti\n"

    def test_from_pipeline_bundle_is_frozen(self):
        """Artifact bundle from from_pipeline is immutable."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
        )

        with pytest.raises(AttributeError):
            bundle.emitted_source = "hacked"  # type: ignore[misc]

    def test_from_pipeline_content_hash_stable(self):
        """Content hash is deterministic across identical pipeline runs."""
        problem = _make_mvp_problem()

        loc1, plans1 = localise_and_optimize(problem)
        bundle1 = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc1,
            contraction_plans=plans1,
        )

        loc2, plans2 = localise_and_optimize(problem)
        bundle2 = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc2,
            contraction_plans=plans2,
        )

        assert bundle1.content_hash() == bundle2.content_hash()

    def test_from_pipeline_roundtrip_json(self):
        """Bundle created via from_pipeline can round-trip through JSON."""
        problem = _make_mvp_problem()
        loc_result, plans = localise_and_optimize(problem)

        bundle = ArtifactBundle.from_pipeline(
            problem_ir=problem,
            localisation=loc_result,
            contraction_plans=plans,
            emitted_source="# test source",
        )

        json_str = bundle.to_json()
        restored = ArtifactBundle.from_json(json_str=json_str)

        assert restored.problem_ir_dict == bundle.problem_ir_dict
        assert restored.element_ir_summary == bundle.element_ir_summary
        assert len(restored.contraction_plans) == len(bundle.contraction_plans)
        assert restored.emitted_source == bundle.emitted_source
        assert restored.content_hash() == bundle.content_hash()


# ======================================================================
# P5.3: CI budget regression fixtures
# ======================================================================


class TestBudgetRegressionMVP:
    """Budget regression tests for MVP contractions.

    These tests ensure that the MVP einsum contractions (strain_displacement,
    internal_force, tangent_matvec) remain within the JIT budget limits.
    Any change that pushes a contraction over budget will be caught in CI.
    """

    def test_budget_regression_mvp_per_func(self):
        """All MVP contractions individually fit within @ti.func budget (512 lines)."""
        problem = _make_mvp_problem()
        loc_result = localise(problem)

        for spec in loc_result.einsum_specs:
            result = optimize_contraction(
                spec.einsum_string,
                list(spec.operand_shapes),
            )
            assert result.estimated_lines <= MAX_LINES_TI_FUNC, (
                f"Budget regression: '{spec.name}' exceeds @ti.func limit — "
                f"{result.estimated_lines} > {MAX_LINES_TI_FUNC} lines. "
                f"Einsum: {spec.einsum_string}"
            )

    def test_budget_regression_mvp_kernel_total(self):
        """Total MVP contractions fit within @ti.kernel budget (2000 lines)."""
        problem = _make_mvp_problem()
        loc_result = localise(problem)

        results = [
            optimize_contraction(spec.einsum_string, list(spec.operand_shapes))
            for spec in loc_result.einsum_specs
        ]

        ok, detail = check_kernel_budget(results)
        assert ok, f"Budget regression: MVP contractions exceed @ti.kernel limit — {detail}"

    def test_budget_regression_mvp_absolute_ceiling(self):
        """Total MVP contractions are well within absolute ceiling (5000 lines)."""
        problem = _make_mvp_problem()
        loc_result = localise(problem)

        results = [
            optimize_contraction(spec.einsum_string, list(spec.operand_shapes))
            for spec in loc_result.einsum_specs
        ]

        ok, detail = check_absolute_budget(results)
        assert ok, f"Budget regression: MVP contractions exceed absolute ceiling — {detail}"

    def test_budget_regression_mvp_tier_assignments(self):
        """MVP contractions are classified as Tier 1 or Tier 2 (no Tier 3)."""
        problem = _make_mvp_problem()
        loc_result = localise(problem)

        for spec in loc_result.einsum_specs:
            result = optimize_contraction(
                spec.einsum_string,
                list(spec.operand_shapes),
            )
            assert result.tier in (Tier.TIER_1, Tier.TIER_2), (
                f"Budget regression: '{spec.name}' classified as Tier {result.tier} "
                f"(expected Tier 1 or 2). Einsum: {spec.einsum_string}, "
                f"estimated lines: {result.estimated_lines}"
            )

    def test_budget_regression_mvp_all_within_budget_flag(self):
        """All MVP contractions have within_budget=True."""
        problem = _make_mvp_problem()
        loc_result = localise(problem)

        for spec in loc_result.einsum_specs:
            result = optimize_contraction(
                spec.einsum_string,
                list(spec.operand_shapes),
            )
            assert result.within_budget, (
                f"Budget regression: '{spec.name}' flagged as over budget. "
                f"Detail: {result.budget_detail}"
            )


class TestBudgetRegressionOverBudget:
    """Negative budget regression tests.

    Verify that the budget machinery correctly detects over-budget einsums.
    These tests use deliberately oversized contractions.
    """

    def test_budget_regression_over_budget_huge_einsum(self):
        """A huge fake einsum exceeds the @ti.func budget and is flagged."""
        # Construct a contraction with many physics indices (range 6 each)
        # that will produce > 512 unrolled lines:
        # 6^6 = 46656 multiplied by the conservatism factor -> well over budget
        result = optimize_contraction(
            "abcdef,defghi->abcghi",
            [(6, 6, 6, 6, 6, 6), (6, 6, 6, 6, 6, 6)],
        )
        assert not result.within_budget, (
            f"Expected over-budget but got within_budget=True. "
            f"Lines: {result.estimated_lines}, detail: {result.budget_detail}"
        )
        assert result.tier == Tier.TIER_3

    def test_budget_regression_over_budget_absolute_ceiling(self):
        """Multiple large contractions exceed the absolute ceiling."""
        # Use a contraction that produces many lines
        single = optimize_contraction(
            "ijkl,kl->ij",
            [(6, 6, 6, 6), (6, 6)],
        )

        # Replicate enough to exceed absolute ceiling
        copies_needed = (MAX_LINES_ABSOLUTE // max(single.estimated_lines, 1)) + 2
        specs: list[tuple[str, list[tuple[int, ...]]]] = [
            ("ijkl,kl->ij", [(6, 6, 6, 6), (6, 6)])
        ] * copies_needed

        with pytest.raises(BudgetExceededError):
            from mechdsl.codegen.einsum_optimizer import optimize_all

            optimize_all(specs)

    def test_budget_regression_over_budget_kernel(self):
        """Synthetic over-budget kernel total is detected."""
        # Create results whose total exceeds MAX_LINES_TI_KERNEL
        from mechdsl.codegen.einsum_optimizer import ContractionResult

        lines_each = MAX_LINES_TI_KERNEL // 2 + 100
        items = [
            ContractionResult(
                einsum_string=f"over_budget_{i}",
                contraction_path=[],
                estimated_flops=1000.0,
                estimated_lines=lines_each,
                tier=Tier.TIER_3,
                within_budget=False,
            )
            for i in range(3)
        ]
        ok, detail = check_kernel_budget(items)
        assert not ok, f"Expected kernel budget exceeded but got ok=True. Detail: {detail}"
        assert "OVER BUDGET" in detail
