"""Tests for Phase 5: TaichiPrinter upgrades (postprocess, main, golden files).

Covers tasks P5-T1 (rename + postprocess), P5-T2 (main block),
P5-T3 (wiring + golden file regeneration).
"""

from __future__ import annotations

import pytest

import mechdsl.codegen.taichi_printer as tp
from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import (
    EmissionContext,
    emit,
    emit_main,
    emit_postprocess,
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


def _make_svk_bundle() -> ArtifactBundle:
    ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc, plans = localise_and_optimize(ir)
    return ArtifactBundle.from_pipeline(ir, loc, plans)


# ============================================================================
# P5-T1: Rename + emit_postprocess
# ============================================================================


class TestEmitPostprocess:
    def test_emit_postprocess_produces_save_results(self):
        """emit_postprocess produces a save_results function."""
        ctx = EmissionContext()
        emit_postprocess(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "def save_results" in source

    def test_emit_postprocess_vtk_has_hex_topology(self):
        """VTK export includes hexahedron cell topology, not empty cells."""
        ctx = EmissionContext()
        emit_postprocess(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "hexahedron" in source
        assert "cells=[]" not in source

    def test_rename_no_more_stub(self):
        """emit_newton_driver_stub no longer exists as a module attribute."""
        assert not hasattr(tp, "emit_newton_driver_stub")
        assert hasattr(tp, "emit_newton_driver")


# ============================================================================
# P5-T2: emit_main
# ============================================================================


class TestEmitMain:
    def test_emit_main_produces_name_block(self):
        """emit_main produces if __name__ == '__main__' block."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert 'if __name__ == "__main__":' in source

    def test_emit_main_references_newton_solve(self):
        """Emitted main block references newton_solve."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "newton_solve" in source

    def test_emit_main_calls_allocate_fields(self):
        """Emitted main block calls allocate_fields, not direct field assignment."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "allocate_fields(n_nodes_mesh, n_elem_mesh)" in source
        # Must NOT treat n_nodes/n_elem as Taichi scalar fields
        assert "n_nodes[None]" not in source
        assert "n_elem[None]" not in source

    def test_emit_main_loads_mesh_into_fields(self):
        """Emitted main block loads coords/conn into Taichi fields."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "x_ref.from_numpy(coords)" in source
        assert "elem_nodes.from_numpy(conn)" in source

    def test_emit_main_loads_boundary_conditions(self):
        """Emitted main block loads f_ext and bc_dofs from mesh file."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "f_ext.from_numpy(" in source
        assert "bc_dofs" in source

    def test_emit_main_passes_bc_dofs_to_newton(self):
        """Emitted main block passes bc_dofs to newton_solve."""
        ctx = EmissionContext()
        emit_main(ctx, _make_svk_bundle())
        source = ctx.get_source()
        assert "bc_dofs=bc_dofs" in source


# ============================================================================
# Newton driver BC enforcement
# ============================================================================


class TestNewtonDriverBC:
    def test_newton_solve_accepts_bc_dofs(self):
        """Emitted newton_solve has bc_dofs parameter."""
        source = emit(_make_svk_bundle())
        assert "bc_dofs: np.ndarray | None = None" in source

    def test_newton_solve_dual_tolerance(self):
        """Emitted newton_solve uses dual abs/rel convergence tolerances."""
        source = emit(_make_svk_bundle())
        assert "tol_abs: float = 1.0e-10" in source
        assert "tol_rel: float = 1.0e-8" in source
        assert "conv_threshold = max(tol_abs, tol_rel * r0_norm)" in source

    def test_newton_solve_zeros_residual_at_bc(self):
        """Emitted Newton loop zeros residual at constrained DOFs."""
        source = emit(_make_svk_bundle())
        assert "r_flat[bc_dofs] = 0.0" in source

    def test_newton_solve_zeros_du_at_bc(self):
        """Emitted Newton loop zeros displacement update at constrained DOFs."""
        source = emit(_make_svk_bundle())
        assert "du_flat[bc_dofs] = 0.0" in source

    def test_newton_solve_modifies_matvec_for_bc(self):
        """Emitted CG matvec enforces identity at constrained DOFs."""
        source = emit(_make_svk_bundle())
        assert "v_bc[bc_dofs] = 0.0" in source
        assert "Kv[bc_dofs] = v[bc_dofs]" in source


# ============================================================================
# P5-T3: Wire into emit() chain
# ============================================================================


class TestEmitChainWiring:
    def test_main_block_in_emitted_source(self):
        """if __name__ appears in full emitted source."""
        source = emit(_make_svk_bundle())
        assert "__name__" in source

    def test_save_results_in_emitted_source(self):
        """def save_results appears in full emitted source."""
        source = emit(_make_svk_bundle())
        assert "def save_results" in source
