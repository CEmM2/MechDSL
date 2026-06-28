"""Tests for Task P4-3 (PlanJune14 Phase 4) — the final Phase-4 task.

Validate the all-Taichi generated **seam** solve path (generated matrix-free PCG
over the ``ti_runtime`` ``set_solver`` seam + the P3-2 generated SVK tangent
operator via ``set_operator``, optionally the P4-1 generated Jacobi via
``set_preconditioner``) against the **imported** solvers (``ScipyCGSolver`` /
``PCGSolver``) on the reference SVK problem, and expose it as a SELECTABLE
runtime entry point (:func:`mechdsl.solver.import_adapter.make_seam_solver`).

DECISION (Option 1, all-Taichi seam, opt-in): P4-3 does **not** flip the global
``get_default_solver`` default — ``ScipyCGSolver`` stays the fallback; the
guarded global flip is deferred until broader regression coverage (Phase 5 J2 +
Phase 7 governance).

The seam path's interface (``LinearSolveContext`` + on-device
``ti.Vector.field`` DOF vectors) is deliberately distinct from the host-NumPy
``LinearSolverInterface`` (matvec callback) consumed by ``newton.py``. The two
are kept as separate, selectable paths; the seam solver is NOT forced through
the NumPy callback.

Acceptance criteria covered:
  AC-1  The all-Taichi seam solve matches ``ScipyCGSolver``/``PCGSolver`` to
        <1e-10 on the reference SVK patch (slow — Taichi JIT).
  AC-2  The generated seam path is selectable via :func:`make_seam_solver`.
  AC-3  ``get_default_solver()`` still returns ``ScipyCGSolver`` (default NOT
        flipped, per the Option-1 decision).
  AC-4  The imported solver fallback (``build_solver('fallback')`` /
        ``build_solver('generated')``) is still selectable and correct.
"""

# NOTE: no ``from __future__ import annotations`` — this test imports the spike
# and the generated seam PCG, both of which define @ti.kernel bodies whose
# ti.template() annotations Taichi must evaluate eagerly (PEP 563 breaks JIT).

import numpy as np
import pytest

from mechdsl.solver.import_adapter import (
    Algo2CodePCGSolver,
    LinearSolverInterface,
    PCGSolver,
    ScipyCGSolver,
    build_solver,
    get_default_solver,
    make_seam_solver,
)

# Steel-like SVK (matches test_p3_2.py / test_p4_2.py / test_pj1_svk_spike.py).
_E_YOUNG = 200.0e3
_NU = 0.3
_LAM = _E_YOUNG * _NU / ((1 + _NU) * (1 - 2 * _NU))
_MU = _E_YOUNG / (2 * (1 + _NU))

# Generated-vs-imported tolerance (PlanJune14 / 07-CONVENTIONS §6).
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


def _svk_patch_bcs(coords: np.ndarray):
    """Uniaxial-stretch single-Hex8 patch BCs (the PJ-1 / P4-2 gate problem)."""
    n_nodes = coords.shape[0]
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    left = np.abs(coords[:, 0]) < 1e-12
    right = np.abs(coords[:, 0] - 1.0) < 1e-12
    bc_mask[left, :] = True
    bc_mask[right, 0] = True
    bc_values[right, 0] = 0.1
    return bc_mask, bc_values


def _solve_svk_patch_numpy(solver: LinearSolverInterface) -> np.ndarray:
    """Solve the SVK patch with a host-NumPy Newton loop using ``solver``.

    This is the *imported-solver* reference path: a NumPy Newton loop whose
    inner linear solve is driven by the given ``LinearSolverInterface``
    (``ScipyCGSolver`` or ``PCGSolver``).  Returns the converged displacement
    field, used as the <1e-10 oracle for the all-Taichi seam solve.
    """
    from tests.ref.ref_hex8_elastic import (
        apply_dirichlet,
        apply_tangent_matvec,
        assemble_internal_force,
        generate_hex8_mesh,
    )

    coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
    n_nodes = coords.shape[0]
    ndof = n_nodes * 3
    bc_mask, bc_values = _svk_patch_bcs(coords)
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

    u = apply_dirichlet(np.zeros((n_nodes, 3), dtype=np.float64), bc_mask, bc_values)
    r0_norm: float | None = None

    for _ in range(50):
        f_int = assemble_internal_force(u, coords, conn, _LAM, _MU)
        R = f_ext - f_int
        R[bc_mask] = 0.0
        r_norm = float(np.linalg.norm(R))
        if r0_norm is None:
            r0_norm = r_norm
        if r0_norm < 1e-15 or r_norm < 1e-10 * r0_norm:
            break

        def matvec(v_flat: np.ndarray, _u: np.ndarray = u) -> np.ndarray:
            v = v_flat.reshape((n_nodes, 3))
            return apply_tangent_matvec(_u, v, coords, conn, _LAM, _MU, bc_mask).ravel()

        du_flat, _it, _res = solver.solve(
            matvec, R.ravel(), np.zeros(ndof, dtype=np.float64), 1e-12, 2000
        )
        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:  # pragma: no cover - convergence is asserted by the caller
        raise RuntimeError("imported-solver Newton solve did not converge")

    return u


class TestTaskP4_3:
    """Tests for Task P4-3: validate seam path + selectable (no default flip). AC 1-4."""

    @pytest.mark.slow
    def test_all_taichi_seam_solve_matches_imported_solvers(self, tmp_path):
        """AC-1: the all-Taichi seam solve matches ScipyCG/PCG to <1e-10 on the reference problem.

        Drives the generated PCG (injected via ``make_seam_solver`` /
        ``set_solver``) against the **P3-2 generated SVK tangent operator**
        (``set_operator``), on device over ``ti.Vector.field`` DOF vectors — no
        NumPy in the seam hot path.  The converged displacement is then compared
        against the SAME SVK patch solved by the **imported** ``ScipyCGSolver``
        AND ``PCGSolver`` (host-NumPy Newton).  All three must agree to <1e-10.
        """
        import taichi as ti

        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.spike.svk_hex8_taichi import (
            _apply_dirichlet,
            _mask_free,
            _set_constrained,
        )
        from ti_runtime import vector_ops as vops
        from ti_runtime.seams import IdentityPreconditioner

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        # ── Imported-solver oracles (host-NumPy Newton + ScipyCG / PCG) ───────
        u_scipy = _solve_svk_patch_numpy(ScipyCGSolver())
        u_pcg = _solve_svk_patch_numpy(PCGSolver())
        # The two imported solvers must themselves agree (sanity on the oracle).
        assert float(np.max(np.abs(u_scipy - u_pcg))) < _GATE_TOL, (
            "imported ScipyCG and PCG disagree on the SVK patch — oracle is unstable"
        )

        # ── All-Taichi seam solve (generated PCG + P3-2 generated operator) ───
        source = _make_svk_source()
        mod = _import_generated_module(source, tmp_path, name="gen_p4_3_op")
        assert hasattr(mod, "svk_tangent_matvec_apply"), (
            "generated module is missing the P3-2 @ti.kernel matrix-free tangent"
        )

        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        bc_mask, bc_values = _svk_patch_bcs(coords)
        f_ext_np = np.zeros((n_nodes, 3), dtype=np.float64)

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.f_ext.from_numpy(f_ext_np)

        free = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        bc_val = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        free.from_numpy((~bc_mask).astype(np.float64))
        bc_val.from_numpy(bc_values)

        v_bc = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)

        def apply_A(out_field, x_field):
            _mask_free(v_bc, x_field, free)  # zero constrained DOFs of the direction
            mod.svk_tangent_matvec_apply(out_field, v_bc, _LAM, _MU)
            _set_constrained(out_field, x_field, free)  # identity rows on constrained DOFs

        # ── SELECTABLE entry point: opt into the all-Taichi seam solver ───────
        ctx = make_seam_solver(
            operator=apply_A,
            preconditioner=IdentityPreconditioner(),
        )

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
            ctx.solver.solve(resid, du, 1e-12, 2000)  # generated PCG over the seam
            _mask_free(du, du, free)
            vops.axpy(mod.u, 1.0, du)
        else:
            pytest.fail("generated-PCG seam Newton solve did not converge")

        u_seam = mod.u.to_numpy()  # boundary extraction only (verification output)
        assert np.max(np.abs(u_seam)) > 1e-3, "expected a nonzero converged displacement"

        diff_scipy = float(np.max(np.abs(u_seam - u_scipy)))
        diff_pcg = float(np.max(np.abs(u_seam - u_pcg)))
        assert diff_scipy < _GATE_TOL, (
            f"seam solve differs from imported ScipyCGSolver: "
            f"max|u_seam - u_scipy| = {diff_scipy:.3e} >= {_GATE_TOL:.0e}"
        )
        assert diff_pcg < _GATE_TOL, (
            f"seam solve differs from imported PCGSolver: "
            f"max|u_seam - u_pcg| = {diff_pcg:.3e} >= {_GATE_TOL:.0e}"
        )

    @pytest.mark.unit
    def test_generated_seam_path_is_selectable(self):
        """AC-2: the all-Taichi generated path is selectable via the new entry point.

        ``make_seam_solver`` is the opt-in selector.  It must be a distinct
        surface from ``build_solver`` (it returns the seam's native
        ``LinearSolveContext`` interface, not a host-NumPy
        ``LinearSolverInterface``), and it must bind the generated PCG at the
        ``set_solver`` seam so ``ctx.solver.solve`` is callable.
        """
        import taichi as ti

        from mechdsl.solver import make_seam_solver as exported_make_seam_solver
        from ti_runtime.seams import IdentityPreconditioner, LinearSolveContext

        ti.init(arch=ti.cpu, default_fp=ti.f64)

        # Re-exported from the package surface (selectable from mechdsl.solver).
        assert exported_make_seam_solver is make_seam_solver
        assert callable(make_seam_solver)

        # A trivial SPD operator over Taichi fields (interface-shape check).
        @ti.kernel
        def apply_identity(out: ti.template(), x: ti.template()):
            for i in out:
                out[i] = x[i]

        ctx = make_seam_solver(operator=apply_identity, preconditioner=IdentityPreconditioner())

        # The seam path returns the seam interface — NOT a NumPy LinearSolverInterface.
        assert isinstance(ctx, LinearSolveContext)
        assert not hasattr(ctx, "solve"), (
            "make_seam_solver must NOT return a LinearSolverInterface — it returns "
            "the on-device LinearSolveContext seam interface (distinct boundary)"
        )
        # The generated PCG is bound at the set_solver seam, so ctx.solver.solve runs it.
        assert callable(ctx.solver.solve)

        # End-to-end on-device sanity: with the identity operator, PCG returns b.
        n = 4
        b = ti.Vector.field(3, ti.f64, shape=n)
        x = ti.Vector.field(3, ti.f64, shape=n)
        rng = np.random.default_rng(3)
        b_np = rng.standard_normal((n, 3))
        b.from_numpy(np.ascontiguousarray(b_np, dtype=np.float64))
        ctx.solver.solve(b, x, 1e-12, 50)
        np.testing.assert_allclose(x.to_numpy(), b_np, atol=1e-10, rtol=0)

    @pytest.mark.unit
    def test_global_default_not_flipped(self):
        """AC-3: get_default_solver() still returns the imported ScipyCGSolver (default NOT flipped).

        Per the Option-1 decision, P4-3 validates + exposes the seam path but
        does NOT flip the global default.  The default must remain the imported
        ``ScipyCGSolver`` (a host-NumPy ``LinearSolverInterface``), never the
        generated/seam path.
        """
        default = get_default_solver()
        assert isinstance(default, ScipyCGSolver), (
            "get_default_solver() must still return ScipyCGSolver — the global "
            "default flip is intentionally deferred (Option-1 decision)."
        )
        assert not isinstance(default, Algo2CodePCGSolver)
        # It is a host-NumPy solver, not the on-device seam interface.
        assert hasattr(default, "solve")

    @pytest.mark.unit
    def test_imported_solver_fallback_still_correct(self):
        """AC-4: imported solver fallback still selectable and correct; no regression.

        ``build_solver('fallback')`` → ``ScipyCGSolver``;
        ``build_solver('generated')`` → ``Algo2CodePCGSolver``.  Both remain
        selectable, satisfy ``LinearSolverInterface``, and solve a known SPD
        system correctly — the seam path's existence must not perturb them.
        """
        fallback = build_solver("fallback")
        generated = build_solver("generated")
        assert isinstance(fallback, ScipyCGSolver)
        assert isinstance(generated, Algo2CodePCGSolver)
        # No-arg default is the fallback.
        assert isinstance(build_solver(), ScipyCGSolver)
        with pytest.raises(ValueError, match="Unknown solver mode"):
            build_solver("seam")  # type: ignore[arg-type]  # seam is NOT a build_solver mode

        # Both imported solvers solve a known 3x3 SPD system correctly.
        A = np.array([[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]], dtype=np.float64)
        b = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        x_ref = np.linalg.solve(A, b)

        def matvec(v: np.ndarray) -> np.ndarray:
            return A @ v

        for solver in (fallback, generated):
            x, _it, _res = solver.solve(matvec, b, np.zeros(3), 1e-12, 100)
            np.testing.assert_allclose(x, x_ref, atol=1e-10)
