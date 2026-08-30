"""Tests for Phase 4: compile() pipeline wiring.

Covers tasks P4-T1 (compile function implementation) and
P4-T2 (pipeline integration tests).
"""

from __future__ import annotations

import ast

import pytest

from mechdsl import compile
from mechdsl.codegen import compile as compile_from_codegen
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)

pytestmark = pytest.mark.from_problem_ir

# ============================================================================
# Helpers
# ============================================================================


def _make_elastic_ir() -> ProblemIR:
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


def _make_plastic_ir() -> ProblemIR:
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 500.0, "n": 1.0},
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


# ============================================================================
# compile() import
# ============================================================================


class TestCompileImport:
    """Tests for Task P4-T1: compile is importable from both locations."""

    def test_import_from_mechdsl(self):
        """compile is importable from mechdsl."""
        assert callable(compile)

    def test_import_from_codegen(self):
        """compile is importable from mechdsl.codegen."""
        assert callable(compile_from_codegen)

    def test_same_function(self):
        """Both imports refer to the same function."""
        assert compile is compile_from_codegen


# ============================================================================
# Pipeline integration tests
# ============================================================================


class TestCompilePipeline:
    """Tests for Task P4-T2: compile() produces valid ArtifactBundles."""

    def test_elastic_compile_produces_bundle(self):
        """compile(elastic_ir) returns ArtifactBundle with non-empty source."""
        bundle = compile(_make_elastic_ir())
        assert isinstance(bundle, ArtifactBundle)
        assert bundle.emitted_source
        assert len(bundle.emitted_source) > 100

    def test_plastic_compile_produces_bundle(self):
        """compile(plastic_ir) returns ArtifactBundle with non-empty source."""
        bundle = compile(_make_plastic_ir())
        assert isinstance(bundle, ArtifactBundle)
        assert bundle.emitted_source
        assert len(bundle.emitted_source) > 100

    def test_emitted_source_parses_as_python(self):
        """Emitted source is valid Python syntax."""
        bundle = compile(_make_elastic_ir())
        # ast.parse raises SyntaxError if invalid
        ast.parse(bundle.emitted_source)

    def test_deterministic_output(self):
        """compile() is deterministic — same input produces same output."""
        ir = _make_elastic_ir()
        bundle_a = compile(ir)
        bundle_b = compile(ir)
        assert bundle_a.emitted_source == bundle_b.emitted_source

    def test_content_hash_stable(self):
        """content_hash is identical across two calls with same input."""
        ir = _make_elastic_ir()
        bundle_a = compile(ir)
        bundle_b = compile(ir)
        assert bundle_a.content_hash() == bundle_b.content_hash()

    def test_bundle_contains_intermediate_products(self):
        """ArtifactBundle contains all pipeline intermediates."""
        bundle = compile(_make_elastic_ir())
        assert bundle.problem_ir_dict
        assert bundle.element_ir_summary
        assert len(bundle.contraction_plans) > 0
        assert bundle.element_ir_summary["element_type"] == "hex8"
        assert bundle.element_ir_summary["n_nodes"] == 8
