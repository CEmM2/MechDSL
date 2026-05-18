"""Tests for Layer 5 -- Taichi printer (P6.2).

Covers:
1.  Deterministic: two calls with same bundle produce identical source.
2.  Preamble: contains "import taichi", "ti.init", "ti.f64".
3.  Constitutive present: source contains "constitutive_update" function.
4.  Internal force present: source contains internal force kernel.
5.  Tangent matvec present: source contains tangent matvec kernel.
6.  ti.f64: all float types are f64 (no f32).
7.  Index partitioning: physics loops use "ti.static" where appropriate.
8.  Syntactically valid Python: source parses with ``ast.parse``.
9.  SVK constitutive: contains lam*tr(E)*I + 2*mu*E pattern.
10. Bundle metadata: different bundles produce different source (SVK vs J2).
"""

from __future__ import annotations

import ast

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    emit,
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

pytestmark = pytest.mark.stable_backend

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_svk_bundle() -> ArtifactBundle:
    """Create a test bundle with SVK material."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _make_j2_bundle() -> ArtifactBundle:
    """Create a test bundle with J2 plasticity material."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n_exp": 10.0},
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


@pytest.fixture
def svk_bundle() -> ArtifactBundle:
    return _make_svk_bundle()


@pytest.fixture
def j2_bundle() -> ArtifactBundle:
    return _make_j2_bundle()


@pytest.fixture
def svk_source(svk_bundle: ArtifactBundle) -> str:
    return emit(svk_bundle)


@pytest.fixture
def j2_source(j2_bundle: ArtifactBundle) -> str:
    return emit(j2_bundle)


# ---------------------------------------------------------------------------
# Test 1: Deterministic output
# ---------------------------------------------------------------------------


class TestDeterministic:
    def test_same_bundle_same_source(self, svk_bundle: ArtifactBundle) -> None:
        """Two calls with the same bundle produce identical source."""
        source_a = emit(svk_bundle)
        source_b = emit(svk_bundle)
        assert source_a == source_b

    def test_j2_deterministic(self, j2_bundle: ArtifactBundle) -> None:
        """Determinism holds for J2 bundles too."""
        source_a = emit(j2_bundle)
        source_b = emit(j2_bundle)
        assert source_a == source_b


# ---------------------------------------------------------------------------
# Test 2: Preamble
# ---------------------------------------------------------------------------


class TestPreamble:
    def test_import_taichi(self, svk_source: str) -> None:
        assert "import taichi as ti" in svk_source

    def test_import_numpy(self, svk_source: str) -> None:
        assert "import numpy as np" in svk_source

    def test_ti_init(self, svk_source: str) -> None:
        assert "ti.init(" in svk_source

    def test_ti_f64_in_init(self, svk_source: str) -> None:
        assert "ti.f64" in svk_source

    def test_default_fp_f64(self, svk_source: str) -> None:
        assert "default_fp=ti.f64" in svk_source


# ---------------------------------------------------------------------------
# Test 3: Constitutive function present
# ---------------------------------------------------------------------------


class TestConstitutivePresent:
    def test_constitutive_update_defined(self, svk_source: str) -> None:
        assert "def constitutive_update(" in svk_source

    def test_ti_func_decorator(self, svk_source: str) -> None:
        assert "@ti.func" in svk_source


# ---------------------------------------------------------------------------
# Test 4: Internal force kernel present
# ---------------------------------------------------------------------------


class TestInternalForcePresent:
    def test_internal_force_function(self, svk_source: str) -> None:
        assert "def compute_internal_force(" in svk_source

    def test_ti_kernel_decorator(self, svk_source: str) -> None:
        assert "@ti.kernel" in svk_source

    def test_deformation_gradient(self, svk_source: str) -> None:
        """Internal force kernel computes deformation gradient F."""
        # The kernel should compute F from the displacement gradient
        assert "F = ti.Matrix.identity(ti.f64, DIM)" in svk_source
        assert "F[i, I] += u[nid][i] * dNdX[a, I]" in svk_source

    def test_constitutive_called(self, svk_source: str) -> None:
        """Internal force kernel calls the constitutive update."""
        assert "S = constitutive_update(F, lam, mu)" in svk_source

    def test_piola_kirchhoff(self, svk_source: str) -> None:
        """Internal force kernel computes P = F @ S."""
        assert "P = F @ S" in svk_source


# ---------------------------------------------------------------------------
# Test 5: Tangent matvec present
# ---------------------------------------------------------------------------


class TestTangentMatvecPresent:
    def test_tangent_matvec_function(self, svk_source: str) -> None:
        assert "def tangent_matvec(" in svk_source

    def test_analytical_push_forward(self, svk_source: str) -> None:
        """SVK tangent_matvec uses analytical push-forward linearisation.

        PLAN-A §A7.5: the emitted tangent is the closed-form linearisation
        ``dP = grad_v @ S + F @ dS`` integrated over each element, not a
        finite-difference approximation.
        """
        assert "FD_EPS" not in svk_source
        assert "dP = grad_v @ S + F @ dS" in svk_source

    def test_closed_form_svk_material_tangent(self, svk_source: str) -> None:
        """SVK tangent collapses C:dE to the closed-form (lam*tr(dE)*I + 2*mu*dE)."""
        assert "dS = lam * tr_dE * I3 + 2.0 * mu * dE" in svk_source


# ---------------------------------------------------------------------------
# Test 6: ti.f64 used throughout (no f32)
# ---------------------------------------------------------------------------


class TestFloat64:
    def test_no_f32(self, svk_source: str) -> None:
        """Emitted code must never use ti.f32."""
        assert "ti.f32" not in svk_source

    def test_f64_in_constitutive(self, svk_source: str) -> None:
        """Constitutive function uses f64."""
        assert "ti.f64" in svk_source

    def test_field_declarations_use_f64(self, svk_source: str) -> None:
        """Field declarations use ti.f64."""
        assert "dtype=ti.f64" in svk_source


# ---------------------------------------------------------------------------
# Test 7: Index partitioning -- ti.static for physics indices
# ---------------------------------------------------------------------------


class TestIndexPartitioning:
    def test_ti_static_physics_loops(self, svk_source: str) -> None:
        """Physics index loops (DIM=3) use ti.static(range(...))."""
        assert "ti.static(range(DIM))" in svk_source

    def test_node_loops_runtime(self, svk_source: str) -> None:
        """Node loops (N_NODES=8 > 6) use runtime range per convention."""
        # Node gather, deformation gradient, and force integration use runtime
        assert "for a in range(N_NODES):" in svk_source

    def test_node_loop_grad_gather_static(self, svk_source: str) -> None:
        """GRAD_AT_QUAD gather loop keeps ti.static for Python list access."""
        assert "for a in ti.static(range(N_NODES)):" in svk_source

    def test_ti_static_in_constitutive(self, svk_source: str) -> None:
        """Constitutive trace uses ti.static."""
        assert "for i in ti.static(range(3)):" in svk_source

    def test_runtime_element_loop(self, svk_source: str) -> None:
        """Element loop uses runtime range."""
        assert "for e in range(n_elem):" in svk_source

    def test_quadrature_loop_static(self, svk_source: str) -> None:
        """Quadrature loop uses ti.static (N_QP=8 is element-type constant)."""
        assert "for q in ti.static(range(N_QP)):" in svk_source

    def test_no_mesh_static_unroll(self, svk_source: str) -> None:
        """Element count must NOT be unrolled with ti.static."""
        assert "ti.static(range(n_elem))" not in svk_source


# ---------------------------------------------------------------------------
# Test 8: Syntactically valid Python
# ---------------------------------------------------------------------------


class TestSyntax:
    def test_ast_parse_svk(self, svk_source: str) -> None:
        """Emitted SVK source must parse as valid Python."""
        try:
            ast.parse(svk_source)
        except SyntaxError as exc:
            pytest.fail(f"Emitted source has syntax error: {exc}")

    def test_ast_parse_j2(self, j2_source: str) -> None:
        """Emitted J2 source must parse as valid Python."""
        try:
            ast.parse(j2_source)
        except SyntaxError as exc:
            pytest.fail(f"Emitted source has syntax error: {exc}")


# ---------------------------------------------------------------------------
# Test 9: SVK constitutive -- lam*tr(E)*I + 2*mu*E pattern
# ---------------------------------------------------------------------------


class TestSVKConstitutive:
    def test_green_lagrange_strain(self, svk_source: str) -> None:
        """SVK computes E = 0.5*(C - I)."""
        assert "E = 0.5 * (C - I3)" in svk_source

    def test_cauchy_green(self, svk_source: str) -> None:
        """SVK computes C = F^T @ F."""
        assert "C = F.transpose() @ F" in svk_source

    def test_trace_computation(self, svk_source: str) -> None:
        """SVK computes trace of E."""
        assert "tr_E" in svk_source

    def test_svk_stress(self, svk_source: str) -> None:
        """SVK stress: S = lam*tr_E*I + 2*mu*E."""
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in svk_source

    def test_identity_matrix(self, svk_source: str) -> None:
        """SVK uses a 3x3 identity matrix."""
        assert "ti.Matrix.identity(ti.f64, 3)" in svk_source


# ---------------------------------------------------------------------------
# Test 10: Different bundles produce different source
# ---------------------------------------------------------------------------


class TestBundleDifference:
    def test_svk_vs_j2_differ(self, svk_source: str, j2_source: str) -> None:
        """SVK and J2 bundles produce different source code."""
        assert svk_source != j2_source

    def test_svk_mentions_svk(self, svk_source: str) -> None:
        """SVK source contains SVK-specific content."""
        assert "svk" in svk_source.lower()

    def test_j2_mentions_j2(self, j2_source: str) -> None:
        """J2 source contains J2-specific content."""
        assert "j2" in j2_source.lower()

    def test_j2_has_radial_return(self, j2_source: str) -> None:
        """J2 source contains radial return algorithm (P8.1)."""
        assert "constitutive_update_plastic" in j2_source


# ---------------------------------------------------------------------------
# Test 11: EmissionContext unit tests
# ---------------------------------------------------------------------------


class TestEmissionContext:
    def test_empty_source(self) -> None:
        ctx = EmissionContext()
        assert ctx.get_source() == "\n"

    def test_emit_line(self) -> None:
        ctx = EmissionContext()
        ctx.emit("hello")
        assert "hello" in ctx.get_source()

    def test_emit_blank(self) -> None:
        ctx = EmissionContext()
        ctx.emit()
        assert ctx.get_source() == "\n"

    def test_indent_block(self) -> None:
        ctx = EmissionContext()
        ctx.emit("outer")
        with ctx.indent_block():
            ctx.emit("inner")
        ctx.emit("outer_again")
        lines = ctx.get_source().splitlines()
        assert lines[0] == "outer"
        assert lines[1] == "    inner"
        assert lines[2] == "outer_again"

    def test_nested_indent(self) -> None:
        ctx = EmissionContext()
        with ctx.indent_block(), ctx.indent_block():
            ctx.emit("deep")
        lines = ctx.get_source().splitlines()
        assert lines[0] == "        deep"


# ---------------------------------------------------------------------------
# Test 12: Source contains element constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_n_nodes_constant(self, svk_source: str) -> None:
        assert "N_NODES = 8" in svk_source

    def test_n_qp_constant(self, svk_source: str) -> None:
        assert "N_QP = 8" in svk_source

    def test_dim_constant(self, svk_source: str) -> None:
        assert "DIM = 3" in svk_source

    def test_quad_weights(self, svk_source: str) -> None:
        assert "QUAD_WEIGHTS" in svk_source

    def test_shape_at_quad(self, svk_source: str) -> None:
        assert "SHAPE_AT_QUAD" in svk_source

    def test_grad_at_quad(self, svk_source: str) -> None:
        assert "GRAD_AT_QUAD" in svk_source


# ---------------------------------------------------------------------------
# Test 13: Newton driver present
# ---------------------------------------------------------------------------


class TestNewtonDriver:
    def test_newton_solve_function(self, svk_source: str) -> None:
        assert "def newton_solve(" in svk_source

    def test_convergence_check(self, svk_source: str) -> None:
        assert "res_norm" in svk_source
        assert "tol" in svk_source

    def test_cg_solver(self, svk_source: str) -> None:
        """Newton driver uses the project's CGSolver."""
        assert "CGSolver" in svk_source
        assert "solver.solve(" in svk_source


# ---------------------------------------------------------------------------
# Test 14: Field declarations
# ---------------------------------------------------------------------------


class TestFieldDeclarations:
    def test_displacement_field(self, svk_source: str) -> None:
        assert "u = ti.Vector.field(3, dtype=ti.f64)" in svk_source

    def test_internal_force_field(self, svk_source: str) -> None:
        assert "f_int = ti.Vector.field(3, dtype=ti.f64)" in svk_source

    def test_allocate_fields(self, svk_source: str) -> None:
        assert "def allocate_fields(" in svk_source

    def test_elem_nodes_connectivity(self, svk_source: str) -> None:
        assert "elem_nodes" in svk_source


# ---------------------------------------------------------------------------
# Test 15: Source is non-trivially long
# ---------------------------------------------------------------------------


class TestSourceLength:
    def test_svk_source_nontrivial(self, svk_source: str) -> None:
        """Emitted SVK source should be substantial (> 50 lines)."""
        n_lines = len(svk_source.splitlines())
        assert n_lines > 50, f"Source is only {n_lines} lines"

    def test_j2_source_nontrivial(self, j2_source: str) -> None:
        """Emitted J2 source should be substantial (> 50 lines)."""
        n_lines = len(j2_source.splitlines())
        assert n_lines > 50, f"Source is only {n_lines} lines"
