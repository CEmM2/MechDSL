"""Tests for Task P4-2 (PlanJune14 Phase 4).

Generated matrix-free PCG (``dev/algorithms/pcg.tex``, callable operator ``A`` +
callable preconditioner ``M_inv``) transpiled via ``algo2code`` in *runtime mode*
and injected through the ``ti_runtime`` ``set_solver`` seam, solving against the
**P3-2 generated SVK tangent operator** (``set_operator`` / ``apply_A``).
All-Taichi on-device (Option 1): **no NumPy / ``.to_numpy()`` in the generated
solve hot path**.

The generated PCG body productionizes the PJ-1 spike's hand-written ``pcg``
(``tests/spike/svk_hex8_taichi.py``): same algorithm, but *derived from LaTeX*.
The reusable seam-solve helper lives in
``mechdsl.solver.seam_solve`` (``bind_generated_pcg_solver`` / ``build_seam_pcg``).

Acceptance criteria covered:
  AC-1  Generated PCG injected via ``set_solver`` solves the PJ-1 SVK patch to
        <1e-10 over the seam, driven by the **P3-2 generated tangent operator**.
  AC-2  Generated PCG matches the canonical PCG LaTeX behaviour (converged +
        max-iter-exhausted paths) — vs the PJ-1 spike ``pcg`` body, on device.
  AC-3  No NumPy / ``.to_numpy()`` in the generated solve hot path (source/AST
        check on the transpiled body, mirroring test_pj1_svk_spike).
  AC-4  The issue #307 / PCG-parity suite stays green.
"""

# NOTE: no ``from __future__ import annotations`` — this test imports the spike
# and the generated seam PCG, both of which define @ti.kernel bodies whose
# ti.template() annotations Taichi must evaluate eagerly (PEP 563 breaks JIT).

import ast

import numpy as np
import pytest

from mechdsl.solver.seam_solve import (
    bind_generated_pcg_solver,
    build_seam_pcg,
    transpile_seam_pcg,
)

# Steel-like SVK (matches test_p3_2.py / test_pj1_svk_spike.py).
_E_YOUNG = 200.0e3
_NU = 0.3
_LAM = _E_YOUNG * _NU / ((1 + _NU) * (1 - 2 * _NU))
_MU = _E_YOUNG / (2 * (1 + _NU))

# Generated-vs-reference tolerance (PlanJune14 / 07-CONVENTIONS §6).
_GATE_TOL = 1e-10


def _make_svk_source() -> str:
    """Emit the SVK Taichi solver source (carries the P3-2 generated kernel)."""
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
    from mechdsl.lowering.fe_localise import localise_and_optimize

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


class TestTaskP4_2:
    """Tests for Task P4-2: generated PCG via set_solver. AC 1-4."""

    @pytest.mark.slow
    def test_generated_pcg_solves_svk_patch_via_set_solver(self, tmp_path):
        """AC-1: generated PCG (set_solver) solves the SVK patch <1e-10 over the seam.

        Drives the generated PCG against the **P3-2 generated SVK tangent
        operator** (``svk_tangent_matvec_apply``), injected via ``set_operator``,
        with the generated PCG body injected via ``set_solver``.  The whole linear
        solve runs on device over ``ti.Vector.field`` DOF vectors — no NumPy in
        the hot path.  The Newton loop reuses the spike's Dirichlet seam kernels
        (interchangeable with the generated operator — the point of P3-2/P4-2).
        """
        import taichi as ti

        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic
        from tests.spike.svk_hex8_taichi import (
            _apply_dirichlet,
            _mask_free,
            _set_constrained,
        )
        from ti_runtime import vector_ops as vops
        from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        # P3-2 generated operator module (carries svk_tangent_matvec_apply).
        source = _make_svk_source()
        mod = _import_generated_module(source, tmp_path, name="gen_p4_2_op")
        assert hasattr(mod, "svk_tangent_matvec_apply"), (
            "generated module is missing the P3-2 @ti.kernel matrix-free tangent"
        )

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
            coords, conn, _LAM, _MU, bc_mask, bc_values, f_ext_np, tol=1e-10, cg_tol=1e-12
        )
        assert len(res_ref) >= 2, "expected a nonlinear (Newton-iterated) solve"

        # Load the mesh + BCs into the generated module's fields.
        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.f_ext.from_numpy(f_ext_np)

        free = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        bc_val = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        free.from_numpy((~bc_mask).astype(np.float64))
        bc_val.from_numpy(bc_values)

        # ── Inject the P3-2 GENERATED operator into the apply_A seam ──────────
        v_bc = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)

        def apply_A(out_field, x_field):
            _mask_free(v_bc, x_field, free)  # zero constrained DOFs of the direction
            mod.svk_tangent_matvec_apply(out_field, v_bc, _LAM, _MU)
            _set_constrained(out_field, x_field, free)  # identity rows on constrained DOFs

        ctx = LinearSolveContext()
        ctx.set_operator(apply_A)
        ctx.set_preconditioner(IdentityPreconditioner())
        # ── Inject the GENERATED PCG body into the set_solver seam ────────────
        bind_generated_pcg_solver(ctx)

        # Thin Newton loop: generated internal-force kernel + generated tangent
        # operator + generated PCG solver, all over the seam.
        resid = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        du = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
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
            # Solve K(u)·du = R via the GENERATED PCG injected at set_solver.
            ctx.solver.solve(resid, du, 1e-12, 2000)
            _mask_free(du, du, free)
            vops.axpy(mod.u, 1.0, du)
        else:
            pytest.fail("generated-PCG Newton solve did not converge")

        u_gen = mod.u.to_numpy()  # boundary extraction only (verification output)
        assert np.max(np.abs(u_gen)) > 1e-3, "expected a nonzero converged displacement"
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < _GATE_TOL, (
            f"generated-PCG seam solve differs from reference: "
            f"max|u_gen - u_ref| = {max_diff:.3e} >= {_GATE_TOL:.0e}"
        )

    @pytest.mark.slow
    def test_generated_pcg_matches_canonical_pcg_behaviour(self):
        """AC-2: generated PCG matches the canonical PCG behaviour (converged + max-iter).

        Drives the generated PCG and the PJ-1 spike ``pcg`` (the hand-written
        realisation of the same canonical PCG LaTeX) over the **same** injected
        SPD operator + fields, on device.  Asserts they agree on:
          * the converged path (same solution, same iteration count), and
          * the max-iteration-exhausted path (same partial iterate + iter count).
        This is the behavioural parity the canonical PCG LaTeX pins; a bitwise
        NumPy-vs-Taichi parity is not meaningful (Option 1 note).
        """
        import taichi as ti

        from tests.spike.svk_hex8_taichi import _PCGWorkspace
        from tests.spike.svk_hex8_taichi import pcg as spike_pcg
        from ti_runtime import vector_ops as vops
        from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        # Block-diagonal SPD operator (mirrors test_p2_2 / ti-runtime test_seams).
        m_np = np.array([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]])

        @ti.kernel
        def apply_M(out: ti.template(), x: ti.template()):
            mat = ti.Matrix([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]], dt=ti.f64)
            for i in out:
                out[i] = mat @ x[i]

        rng = np.random.default_rng(7)
        n = 5
        b_np = rng.standard_normal((n, 3))

        def _vfield(vals):
            vals = np.ascontiguousarray(vals, dtype=np.float64)
            f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
            f.from_numpy(vals)
            return f

        generated_pcg = build_seam_pcg()

        def _seam_ctx():
            ctx = LinearSolveContext().set_operator(apply_M)
            ctx.set_preconditioner(IdentityPreconditioner())
            return ctx

        def _run_generated(b, x, tol, maxiter):
            ctx = _seam_ctx()

            def operator_A(out, vec):
                ctx.apply_A(out, vec)

            def precond_M_inv(r_in, z_out):
                ctx.apply_preconditioner(z_out, r_in)

            return generated_pcg(operator_A, b, x, precond_M_inv, tol, maxiter)

        def _run_spike(b, x, tol, maxiter):
            ctx = _seam_ctx()
            ws = _PCGWorkspace.alloc(x.shape[0])
            return spike_pcg(ctx, ws, b, x, tol, maxiter)

        # ── Converged path: tol loose enough to converge before maxiter ──────
        x_gen = ti.Vector.field(3, ti.f64, shape=n)
        x_spk = ti.Vector.field(3, ti.f64, shape=n)
        _, k_gen, _, conv_gen = _run_generated(_vfield(b_np), x_gen, 1e-12, 200)
        k_spk, _ = _run_spike(_vfield(b_np), x_spk, 1e-12, 200)

        expected = np.linalg.solve(m_np, b_np.T).T
        np.testing.assert_allclose(x_gen.to_numpy(), expected, atol=1e-9, rtol=0)
        np.testing.assert_allclose(x_gen.to_numpy(), x_spk.to_numpy(), atol=1e-10, rtol=0)
        assert int(k_gen) == int(k_spk), (
            f"converged-path iteration counts differ: generated={int(k_gen)}, spike={int(k_spk)}"
        )
        assert int(conv_gen) == 1, (
            f"converged path must report converged=1; got {int(conv_gen)} (WI-2)"
        )

        # ── Max-iter-exhausted path: tol unreachable in `maxiter` iters ──────
        max_it = 2
        xg = ti.Vector.field(3, ti.f64, shape=n)
        xs = ti.Vector.field(3, ti.f64, shape=n)
        _, kg, rg, conv_g = _run_generated(_vfield(b_np), xg, 1e-30, max_it)
        ks, rs = _run_spike(_vfield(b_np), xs, 1e-30, max_it)

        assert int(kg) == max_it and int(ks) == max_it, (
            f"max-iter path should exhaust to {max_it}; generated={int(kg)}, spike={int(ks)}"
        )
        assert int(conv_g) == 0, (
            f"max-iter-exhausted path must report converged=0; got {int(conv_g)} (WI-2)"
        )
        np.testing.assert_allclose(xg.to_numpy(), xs.to_numpy(), atol=1e-10, rtol=0)
        assert abs(float(rg) - float(rs)) < 1e-10, (
            f"max-iter residual norms differ: generated={float(rg)}, spike={float(rs)}"
        )

        # Residual sanity on the converged solution (on device, no NumPy in solve).
        ax = ti.Vector.field(3, ti.f64, shape=n)
        apply_M(ax, x_gen)
        vops.axpy(ax, -1.0, _vfield(b_np))
        assert vops.norm2(ax) < 1e-9

    def test_generated_pcg_no_numpy_in_solve(self):
        """AC-3: the generated solver body has no NumPy / .to_numpy() in the hot path.

        Source + AST check on the transpiled ``pcg`` body (mirrors how
        test_pj1_svk_spike checks the spike's hot path).  The generated PCG must
        call only the matrix-free operator ``A(out, x)``, the preconditioner
        ``M_inv(r, z)``, and ``ti_runtime.vector_ops`` primitives — never NumPy.
        """
        code = transpile_seam_pcg()

        # Source-level: no numpy import, no .to_numpy() / np. in the body.
        assert "import numpy" not in code, f"generated PCG must not import numpy:\n{code}"
        assert ".to_numpy(" not in code, f"generated PCG must not call .to_numpy():\n{code}"
        assert "np." not in code, f"generated PCG must not reference np.:\n{code}"
        # It must be matrix-free: no dense _matvec emitted or called.
        assert "def _matvec(" not in code and "_matvec(" not in code, (
            f"generated PCG must be matrix-free (no dense _matvec):\n{code}"
        )

        # AST-level: parse the generated module, isolate the `pcg` function, and
        # walk every node — assert no attribute access named `to_numpy` and no
        # name `np`/`numpy` is referenced inside the solver body.
        tree = ast.parse(code)
        pcg_fn = next(
            (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "pcg"),
            None,
        )
        assert pcg_fn is not None, "generated module is missing the `pcg` driver function"

        for node in ast.walk(pcg_fn):
            if isinstance(node, ast.Attribute):
                assert node.attr != "to_numpy", "pcg body must not call .to_numpy() (host copy)"
            if isinstance(node, ast.Name):
                assert node.id not in ("np", "numpy"), (
                    "pcg body must not reference numpy in the solve hot path"
                )

        # And the on-device primitives the body DOES use are the ti_runtime ones.
        assert "from ti_runtime import vector_ops as _v" in code
        for prim in ("_v.dot(", "_v.norm2(", "_v.vec_add(", "_v.copy("):
            assert prim in code, f"expected ti_runtime primitive {prim} in the generated body"

    @pytest.mark.slow
    def test_generated_pcg_with_generated_jacobi_cuts_iterations(self):
        """The GENERATED PCG bound with the GENERATED Jacobi converges in fewer
        iterations than with identity — exercising the ``M_inv(r, z)`` (out-last)
        seam binding end-to-end with a *non-trivial* preconditioner.

        Identity-preconditioner tests cannot catch a preconditioner mis-binding:
        CG converges to the right answer for any SPD ``M``, so only the iteration
        *rate* would change. This is the one test where a wrong ``M_inv`` mapping
        through the generated PCG would actually fail.
        """
        import taichi as ti

        from mechdsl.solver import GeneratedJacobiPreconditioner, make_seam_solver
        from ti_runtime.seams import IdentityPreconditioner

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        def _vfield(vals):
            vals = np.ascontiguousarray(vals, dtype=np.float64)
            f = ti.Vector.field(vals.shape[1], ti.f64, shape=vals.shape[0])
            f.from_numpy(vals)
            return f

        n = 6
        # Diagonal SPD operator A = diag(d) with 3 distinct eigenvalues {2, 5, 11}:
        # unpreconditioned CG converges in 3 iterations; Jacobi (M = diag(d)) gives
        # M^{-1} A = I -> 1 iteration. A wrong M_inv binding loses that speedup.
        dv = np.tile([2.0, 5.0, 11.0], (n, 1))
        diag = _vfield(dv)

        @ti.kernel
        def apply_A(out: ti.template(), x: ti.template()):
            for i in out:
                out[i] = diag[i] * x[i]

        bv = np.random.default_rng(5).standard_normal((n, 3))
        expected = bv / dv  # A = diag(d) -> x = b / d

        def _solve(precond):
            ctx = make_seam_solver(operator=apply_A, preconditioner=precond)
            x = ti.Vector.field(3, ti.f64, shape=n)  # zero initial guess
            result = ctx.solver.solve(_vfield(bv), x, 1e-12, 100)
            return int(result[1]), x.to_numpy()

        jac_iters, x_jac = _solve(GeneratedJacobiPreconditioner(diag=diag))
        id_iters, x_id = _solve(IdentityPreconditioner())

        np.testing.assert_allclose(x_jac, expected, atol=1e-9)
        np.testing.assert_allclose(x_id, expected, atol=1e-9)
        assert jac_iters < id_iters, (
            "generated Jacobi must cut PCG iterations vs identity through the "
            f"generated PCG; jacobi={jac_iters}, identity={id_iters}"
        )
        assert jac_iters <= 2, (
            f"Jacobi on a diagonal operator should converge ~1 iter; got {jac_iters}"
        )

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_issue_307_pcg_parity_suite_stays_green(self, tmp_path):
        """AC-4: the issue #307 / PCG-parity suite stays green alongside P4-2.

        Runs the canonical-PCG transpiler-parity gate functions in-process (the
        same gate ``recovery_plan_latex_contract/test_pcg_transpiler_parity.py``
        enforces) so a P4-2 regression on the shared algo2code PCG codegen path is
        caught here too.  Authoring ``dev/algorithms/pcg.tex`` must not perturb
        the canonical matrix-``A`` PCG codegen — the generated bodies share the
        same algo2code pipeline.
        """
        from tests.plan_tests.recovery_plan_latex_contract.test_pcg_transpiler_parity import (
            test_converged_path_is_identical_to_machine_precision,
            test_maxiter_exhaust_path_matches,
        )

        # Each re-inits Taichi and rebuilds its own generated PCG + hand twin.
        # The parity gate functions take pytest's ``tmp_path`` (issue #307 W6
        # wrote the generated module to a managed temp dir); forward this test's
        # own ``tmp_path`` fixture since we call them directly, not via pytest.
        test_converged_path_is_identical_to_machine_precision(tmp_path)
        test_maxiter_exhaust_path_matches(tmp_path)
