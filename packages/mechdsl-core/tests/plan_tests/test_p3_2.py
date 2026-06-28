"""Tests for Task P3-2 (PlanJune14 Phase 3).

The Taichi printer now emits a generated ``@ti.kernel`` matrix-free SVK tangent
operator (``svk_tangent_matvec_apply``) **alongside** the legacy host-NumPy
``tangent_matvec``. The generated kernel applies ``K(u)·v`` fully matrix-free
(D-A: element tangents never stored), forms the consistent two-point tangent
``A(i,I,j,J)`` per quadrature point from the Tier-1 ``ti_runtime`` helpers, and
routes the tangent contraction through the **P3-1 opt_einsum ContractionPlan**
(``qaI,qiIjJ,qbJ,bj->qai``, path ``[(2,3),(1,2),(0,1)]``) — not a hand-rolled
contraction. It targets the ``ti_runtime`` ``apply_A(out, x)`` injection seam.

Acceptance (P3-2):

* AC-1: generated tangent matvec matches ``tests/ref/ref_hex8_elastic`` to <1e-10.
* AC-2: the generated tangent passes the JIT-budget counter (≤512 lines/@ti.func).
* AC-3: the generated operator injects into the ti_runtime seam and drives a
  Newton solve (matches the reference solve to <1e-10).
* AC-4: the tangent matvec consumes the opt_einsum ContractionPlan (the recorded
  optimiser path appears in the emitted source; no hand-rolled einsum).
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_ABSOLUTE,
    MAX_LINES_TI_FUNC,
    MAX_LINES_TI_KERNEL,
    Tier,
    estimate_unrolled_lines,
)
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.element_ir import create_hex8_element_ir
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.einsum_extract import (
    TANGENT_MATVEC_APPLY_EINSUM,
    build_tangent_matvec_plan,
    tangent_matvec_apply_spec,
)
from mechdsl.lowering.fe_localise import localise_and_optimize
from tests._e2e_helpers import _import_generated_module
from tests.ref.ref_hex8_elastic import (
    element_tangent_matvec,
    generate_hex8_mesh,
    solve_elastic,
)

# Steel-like SVK (matches test_pj1_svk_spike.py / test_ref_elastic.py).
_E_YOUNG = 200.0e3
_NU = 0.3
_LAM = _E_YOUNG * _NU / ((1 + _NU) * (1 - 2 * _NU))
_MU = _E_YOUNG / (2 * (1 + _NU))

# Generated-vs-reference tolerance (PlanJune14 / 07-CONVENTIONS §6).
_GATE_TOL = 1e-10


def _make_svk_source() -> str:
    """Emit the SVK Taichi solver source (carries the generated kernel)."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": _E_YOUNG, "nu": _NU}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


class TestTaskP3_2:
    """Tests for Task P3-2: generated @ti.kernel matrix-free tangent. AC 1-4."""

    @pytest.mark.slow
    def test_generated_tangent_matches_reference_to_1e_10(self, tmp_path):
        """AC-1: generated @ti.kernel tangent matvec matches ref_hex8_elastic to <1e-10."""
        import taichi as ti

        source = _make_svk_source()
        mod = _import_generated_module(source, tmp_path, name="gen_p3_2_matvec")
        assert hasattr(mod, "svk_tangent_matvec_apply"), (
            "generated module is missing the P3-2 @ti.kernel matrix-free tangent"
        )

        # Small 2x1x1 mesh, finite displacement, random direction.
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        rng = np.random.default_rng(7)
        u_np = np.zeros((n_nodes, 3))
        u_np[:, 0] = 0.04 * coords[:, 0]
        u_np[:, 1] = -0.01 * coords[:, 1]
        v_np = rng.standard_normal((n_nodes, 3)) * 1e-2

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.u.from_numpy(u_np)

        out = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field.from_numpy(v_np)

        # Generated matrix-free tangent matvec: out = K(u) · v.
        mod.svk_tangent_matvec_apply(out, v_field, _LAM, _MU)
        kv_gen = out.to_numpy()

        # Reference: assemble the handwritten element tangent matvec.
        kv_ref = np.zeros((n_nodes, 3))
        for e in range(n_elem):
            nodes = conn[e]
            kv_e = element_tangent_matvec(u_np[nodes], coords[nodes], v_np[nodes], _LAM, _MU)
            for a in range(8):
                kv_ref[nodes[a]] += kv_e[a]

        max_diff = float(np.max(np.abs(kv_gen - kv_ref)))
        assert max_diff < _GATE_TOL, (
            f"generated matvec differs from reference: max|Kv_gen - Kv_ref| = "
            f"{max_diff:.3e} >= {_GATE_TOL:.0e}"
        )

    @pytest.mark.unit
    def test_generated_tangent_passes_jit_budget_counter(self):
        """AC-2: the generated tangent contraction stays ≤512 lines/@ti.func (budget counter)."""
        element_ir = create_hex8_element_ir()
        plan = build_tangent_matvec_plan(element_ir)
        spec = tangent_matvec_apply_spec(element_ir)

        # Re-run the budget counter over the recorded optimiser path: the
        # tangent contraction the generated kernel emits must fit the
        # 512-line @ti.func budget and be Tier <= 2 (no Tier-3 restructuring).
        lines = estimate_unrolled_lines(
            spec.einsum_string,
            list(spec.operand_shapes),
            plan.contraction_path,
        )
        assert lines <= MAX_LINES_TI_FUNC, (
            f"generated tangent contraction is {lines} lines > {MAX_LINES_TI_FUNC} @ti.func budget"
        )
        assert plan.tier <= int(Tier.TIER_2)

    def test_full_svk_kernel_within_kernel_and_absolute_budget(self):
        """The FULL emitted ``svk_tangent_matvec_apply`` @ti.kernel honours BOTH
        the 2000 ``@ti.kernel`` budget and the 5000 absolute ceiling — the honest
        budget test (PlanJune14 WI-1).

        The original AC-2 budget test only gated the inner contraction
        ``@ti.func``; it never measured the full kernel, which (with a
        ``ti.static`` N_QP=8 q-loop) ran ~5311 unrolled lines — over the absolute
        ceiling. WI-1's runtime-q lever divides the per-QP unroll by 8, bringing
        the full SVK kernel to ~678 unrolled, comfortably under both limits. The
        count uses the project's "unrolled lines" weighting (07-CONVENTIONS
        §JIT-budget) via :func:`count_unrolled_kernel_lines`.
        """
        from tests._e2e_helpers import count_unrolled_kernel_lines

        source = _make_svk_source()
        unrolled = count_unrolled_kernel_lines(source, "svk_tangent_matvec_apply")
        assert unrolled <= MAX_LINES_TI_KERNEL, (
            f"full svk_tangent_matvec_apply is {unrolled} unrolled lines > "
            f"{MAX_LINES_TI_KERNEL} @ti.kernel budget"
        )
        assert unrolled <= MAX_LINES_ABSOLUTE, (
            f"full svk_tangent_matvec_apply is {unrolled} unrolled lines > "
            f"{MAX_LINES_ABSOLUTE} absolute ceiling"
        )

    @pytest.mark.slow
    def test_generated_operator_drives_newton_via_seam(self, tmp_path):
        """AC-3: the generated operator injects into the ti_runtime seam and drives a Newton solve."""
        import taichi as ti

        # Reuse the PJ-1 spike's PCG body + Dirichlet seam kernels: the generated
        # operator is interchangeable with the spike's hand-written one, which is
        # the whole point of P3-2 (production replacement of the spike operator).
        from tests.spike.svk_hex8_taichi import (
            _apply_dirichlet,
            _mask_free,
            _PCGWorkspace,
            _set_constrained,
            pcg,
        )
        from ti_runtime import vector_ops as vops
        from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

        source = _make_svk_source()
        mod = _import_generated_module(source, tmp_path, name="gen_p3_2_newton")

        # Uniaxial-stretch single Hex8 patch (the PJ-1 gate problem).
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left = np.abs(coords[:, 0]) < 1e-12
        right = np.abs(coords[:, 0] - 1.0) < 1e-12
        bc_mask[left, :] = True
        bc_mask[right, 0] = True
        bc_values[right, 0] = 0.1
        f_ext_np = np.zeros((n_nodes, 3), dtype=np.float64)

        # Reference solve (handwritten NumPy Newton + ScipyCG).
        u_ref, res_ref = solve_elastic(
            coords,
            conn,
            _LAM,
            _MU,
            bc_mask,
            bc_values,
            f_ext_np,
            tol=1e-10,
            cg_tol=1e-12,
        )
        assert len(res_ref) >= 2, "expected a nonlinear (Newton-iterated) solve"

        # Allocate the generated module's fields and load the mesh + BCs.
        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.f_ext.from_numpy(f_ext_np)

        free = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        bc_val = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        free.from_numpy((~bc_mask).astype(np.float64))
        bc_val.from_numpy(bc_values)

        # Inject the GENERATED operator into the ti_runtime apply_A seam.
        v_bc = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)

        def apply_A(out_field, x_field):
            _mask_free(v_bc, x_field, free)  # zero constrained DOFs of the direction
            mod.svk_tangent_matvec_apply(out_field, v_bc, _LAM, _MU)
            _set_constrained(out_field, x_field, free)  # identity rows on constrained DOFs

        ctx = LinearSolveContext()
        ctx.set_operator(apply_A)
        ctx.set_preconditioner(IdentityPreconditioner())

        # Thin Newton loop driven by the generated internal-force kernel + the
        # generated tangent operator through the seam.
        resid = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        du = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        ws = _PCGWorkspace.alloc(n_nodes)
        _apply_dirichlet(mod.u, free, bc_val)

        r0 = None
        for _ in range(50):
            mod.compute_internal_force(_LAM, _MU)
            vops.copy(resid, mod.f_ext)
            vops.axpy(resid, -1.0, mod.f_int)  # R = f_ext - f_int
            _mask_free(resid, resid, free)
            r_norm = vops.norm2(resid)
            if r0 is None:
                r0 = r_norm
            if r_norm < 1e-10 * r0:
                break
            du.fill(0.0)
            pcg(ctx, ws, resid, du, 1e-12, 2000)
            _mask_free(du, du, free)
            vops.axpy(mod.u, 1.0, du)
        else:
            pytest.fail("generated-operator Newton solve did not converge")

        u_gen = mod.u.to_numpy()
        assert np.max(np.abs(u_gen)) > 1e-3, "expected a nonzero converged displacement"
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < _GATE_TOL, (
            f"generated-operator solve differs from reference: "
            f"max|u_gen - u_ref| = {max_diff:.3e} >= {_GATE_TOL:.0e}"
        )

    @pytest.mark.unit
    def test_generated_tangent_routes_through_optimizer_not_handrolled(self):
        """AC-4: the tangent matvec consumes the opt_einsum ContractionPlan (no hand-rolled contraction)."""
        source = _make_svk_source()

        # The generated kernel must exist and target the ti_runtime seam.
        assert "def svk_tangent_matvec_apply(" in source
        assert "from ti_runtime import tensor_ti as _tt" in source

        # The optimiser-recorded path must be embedded in the emitted source —
        # the kernel realises THIS path, it does not hand-roll a contraction.
        element_ir = create_hex8_element_ir()
        plan = build_tangent_matvec_plan(element_ir)
        assert plan.einsum_string == TANGENT_MATVEC_APPLY_EINSUM
        assert str(list(plan.contraction_path)) in source, (
            "the emitted kernel must embed the opt_einsum ContractionPlan path "
            f"{list(plan.contraction_path)}"
        )
        assert plan.einsum_string in source

        # The three recorded pairwise steps are realised as step comments, proving
        # the emission is path-driven rather than a single hand-written einsum.
        assert "step 1" in source and "step 2" in source and "step 3" in source
