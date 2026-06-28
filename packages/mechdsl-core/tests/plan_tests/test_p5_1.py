"""Tests for Task P5-1 (PlanJune14 Phase 5) — J2 plasticity through the seams.

Wire the **matrix-free algorithmic consistent tangent** for the J2 plastic branch
(the linearisation of the radial return map — NOT ∂²Ψ/∂E², per
``.claude/rules/symbolic.md``) through the **PJ-3 generated ``@ti.kernel`` matvec
path** (``emit_j2_tangent_matvec_kernel`` → ``apply_A`` seam → opt_einsum
``ContractionPlan``). The J2 scalar return-map already transpiles
(``mechdsl/lib/plasticity.py`` execs ``transpile_radial_return_j2``); P5-1 connects
its algorithmic tangent to the generated matrix-free operator, manages the history
fields (eps_p, α) **on-device**, and validates against ``tests/ref/ref_hex8_plastic``.

This is deliberately distinct from the existing **host-NumPy** ``tangent_matvec``
path (covered by ``test_plastic_emission.py`` / ``test_e2e_plastic.py``), which
snapshots ``alpha.to_numpy()`` per quadrature point. P5-1 requires **no NumPy in
the plastic operator/solve hot path**.

Acceptance criteria covered:
  AC-1  The generated matrix-free J2 algorithmic tangent matvec matches
        ``tests/ref/ref_hex8_plastic`` within tolerance (slow — Taichi JIT).
  AC-2  History/state fields (eps_p, α) evolve correctly across Newton steps
        **on-device** — no ``.to_numpy()`` in the matvec/solve hot path.
  AC-3  The plastic branch passes the JIT-budget counter
        (``estimate_unrolled_lines ≤ MAX_LINES_TI_FUNC``); split via the
        optimizer path if needed — never hand-unroll.

NOTE: no ``from __future__ import annotations`` — the generated module defines
``@ti.kernel`` bodies whose ``ti.template()`` annotations Taichi must evaluate
eagerly (PEP 563 breaks JIT — see ``test_p3_2.py`` / ``test_p4_3.py``).
"""

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.einsum_optimizer import (
    MAX_LINES_ABSOLUTE,
    MAX_LINES_TI_FUNC,
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

# Steel-like J2 power-law (matches test_e2e_plastic.py / ref_hex8_plastic).
_E_YOUNG = 200.0e3
_NU = 0.3
_SIGMA_Y0 = 200.0
_K_HARD = 100.0
_N_HARD = 0.3
_LAM = _E_YOUNG * _NU / ((1 + _NU) * (1 - 2 * _NU))
_MU = _E_YOUNG / (2 * (1 + _NU))

# Generated-vs-reference tolerance (PlanJune14 / 07-CONVENTIONS §6).
_GATE_TOL = 1e-10


def _make_j2_source() -> str:
    """Emit the J2 Taichi solver source (carries the P5-1 generated kernel)."""
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": _E_YOUNG,
                "nu": _NU,
                "sigma_y0": _SIGMA_Y0,
                "K": _K_HARD,
                "n": _N_HARD,
            },
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


def _j2_material():
    """The reference J2 material matching the emitted solver's parameters."""
    from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial

    return J2PowerLawMaterial(E=_E_YOUNG, nu=_NU, sigma_y0=_SIGMA_Y0, K=_K_HARD, n=_N_HARD)


def _matvec_body(source: str) -> str:
    """Slice the generated ``j2_tangent_matvec_apply`` kernel body from *source*."""
    marker = "def j2_tangent_matvec_apply("
    start = source.find(marker)
    assert start >= 0, "generated module is missing the P5-1 @ti.kernel J2 tangent"
    rest = source[start:]
    next_boundary = len(rest)
    for boundary in ("\ndef ", "\nclass ", "\n@ti.kernel", "\n# ===="):
        idx = rest.find(boundary, 1)
        if idx != -1 and idx < next_boundary:
            next_boundary = idx
    return rest[:next_boundary]


class TestTaskP51:
    """Tests for Task P5-1: J2 plasticity through the seams. AC covered: 1, 2, 3."""

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_j2_algorithmic_tangent_matvec_parity_vs_ref(self, tmp_path):
        """Verifies: the generated matrix-free J2 algorithmic consistent-tangent
        matvec (PJ-3 ``@ti.kernel`` path) reproduces the reference plastic tangent.
        AC-1. Passes when: K(u)·v from the generated operator matches
        ``tests/ref/ref_hex8_plastic`` to < 1e-10 (07-CONVENTIONS §6)."""
        import taichi as ti

        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.ref.ref_hex8_plastic import element_tangent_matvec_plastic

        source = _make_j2_source()
        mod = _import_generated_module(source, tmp_path, name="gen_p5_1_matvec")
        assert hasattr(mod, "j2_tangent_matvec_apply"), (
            "generated module is missing the P5-1 @ti.kernel matrix-free J2 tangent"
        )

        # 2x1x1 mesh, finite displacement large enough to drive the plastic
        # branch (eps_yield ~ sigma_y0/E ~ 1e-3; a ~4% axial stretch yields).
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        rng = np.random.default_rng(11)
        u_np = np.zeros((n_nodes, 3))
        u_np[:, 0] = 0.04 * coords[:, 0]
        u_np[:, 1] = -0.012 * coords[:, 1]
        v_np = rng.standard_normal((n_nodes, 3)) * 1e-2

        mat = _j2_material()

        # Per-element alpha history: pre-yielded state (alpha_old > 0) so the
        # algorithmic-tangent plastic branch is exercised, AND a guarantee that
        # n_hard < 1's H' singularity at alpha=0 is avoided. Build it by running
        # the reference internal-force update once at u_np from alpha_old = 0.
        from tests.ref.ref_hex8_plastic import element_internal_force_plastic

        alpha_hist = np.zeros((n_elem, 8), dtype=np.float64)
        for e in range(n_elem):
            nodes = conn[e]
            _f, alpha_new_e = element_internal_force_plastic(
                u_np[nodes], coords[nodes], mat, np.zeros(8)
            )
            alpha_hist[e] = alpha_new_e
        assert float(np.max(alpha_hist)) > 1e-6, (
            "test setup failed to drive any quadrature point plastic — "
            "the algorithmic plastic-branch tangent would not be exercised"
        )

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.u.from_numpy(u_np)
        mod.alpha.from_numpy(alpha_hist)

        out = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field.from_numpy(v_np)

        # Generated matrix-free J2 algorithmic-tangent matvec: out = K(u) · v.
        mod.j2_tangent_matvec_apply(out, v_field, _LAM, _MU, _SIGMA_Y0, _K_HARD, _N_HARD)
        kv_gen = out.to_numpy()

        # Reference: assemble the handwritten plastic element tangent matvec with
        # the SAME alpha history (the tangent linearises about the stored state).
        kv_ref = np.zeros((n_nodes, 3))
        for e in range(n_elem):
            nodes = conn[e]
            kv_e = element_tangent_matvec_plastic(
                u_np[nodes], coords[nodes], v_np[nodes], mat, alpha_hist[e]
            )
            for a in range(8):
                kv_ref[nodes[a]] += kv_e[a]

        max_diff = float(np.max(np.abs(kv_gen - kv_ref)))
        assert max_diff < _GATE_TOL, (
            f"generated J2 algorithmic-tangent matvec differs from reference: "
            f"max|Kv_gen - Kv_ref| = {max_diff:.3e} >= {_GATE_TOL:.0e}"
        )

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_j2_tangent_matvec_parity_near_first_yield_n_lt_1(self, tmp_path):
        """Verifies: WI-3 near-first-yield coverage of the previously-untested
        committed-alpha sliver ``(1e-30, 1e-12]`` with ``n_hard < 1``.

        At a committed ``alpha_old`` in this sliver the reference
        ``yield_stress_derivative`` returns 0 (its ``alpha <= 1e-12`` n<1
        singularity guard), while the *naive* ``K*n*alpha^(n-1)`` diverges
        (~1e10). The old emitted ``1e-30`` floor used the naive value during the
        return-map's first Newton iteration; the WI-3 ``1e-12`` floor makes the
        generated H' agree with the reference (0) instead. This test drives every
        quadrature point plastic from a committed alpha seeded *inside* the
        sliver and asserts the generated matrix-free tangent still matches
        ``element_tangent_matvec_plastic`` to < 1e-10 — i.e. the floor change
        keeps generated/reference agreement in the regime that
        ``test_j2_algorithmic_tangent_matvec_parity_vs_ref`` (alpha > 1e-6) never
        touches. The existing ``test_p5_1.py`` parity case forces alpha > 1e-6,
        so this regime had zero coverage.

        COUPLING (cognitive-debt mitigation, dev/plans/pj14_fix.md): the H' floor
        (1e-12) must equal the reference ``yield_stress_derivative`` boundary, and
        the in-loop convergence check sets the ``converged`` flag that the
        post-loop non-convergence guard keys off — both anchored on the same
        ``effective_tol``. Those relationships are asserted below so they fail
        loudly if a future edit drifts one without the other.
        """
        import taichi as ti

        from mechdsl.symbolic.models.j2_power_law import yield_stress_derivative
        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.ref.ref_hex8_plastic import element_tangent_matvec_plastic

        source = _make_j2_source()

        # Structural coupling guards (cheap, no JIT): the emitted floor matches the
        # reference boundary, and the convergence check sets the converged flag the
        # non-convergence guard keys off (action-at-a-distance between two blocks).
        matvec_body = _matvec_body(source)
        assert "if alpha_trial > 1e-12 else 0.0" in matvec_body, (
            "emitted H' floor must be 1e-12 (matches reference yield_stress_derivative)"
        )
        assert "if alpha_new > 1e-12 else 0.0" in matvec_body, (
            "emitted tangent-assembly H' floor must be 1e-12"
        )
        assert "effective_tol = ti.max(1e-12, 1e-12 * stress_ref)" in matvec_body
        assert "ti.abs(f) < effective_tol" in matvec_body, (
            "return-map convergence check must key off effective_tol"
        )
        # WI-C: the non-convergence guard is the explicit converged flag (closes the
        # (effective_tol, 1e3*effective_tol] band the old f_final magnitude test let
        # through). The flag is SET by the effective_tol convergence check above.
        assert "converged = 1" in matvec_body, (
            "convergence check must set the converged flag (keyed off effective_tol)"
        )
        assert "if converged == 0:" in matvec_body, (
            "non-convergence guard must key off the converged flag set on convergence"
        )

        # The reference is the source of truth: in the sliver it returns 0, and the
        # naive formula it guards against diverges. This is exactly the regime the
        # 1e-12 floor protects.
        mat = _j2_material()
        assert mat.n < 1.0, "near-yield singularity guard only matters for n_hard < 1"
        alpha_sliver = 5.0e-13  # in (1e-30, 1e-12]
        assert 1e-30 < alpha_sliver <= 1e-12
        assert yield_stress_derivative(mat, alpha_sliver) == 0.0, (
            "reference must return H'=0 in the (1e-30, 1e-12] sliver"
        )
        assert mat.K * mat.n * alpha_sliver ** (mat.n - 1.0) > 1e9, (
            "naive H' must diverge in the sliver (this is what the floor guards)"
        )

        mod = _import_generated_module(source, tmp_path, name="gen_p5_1_near_yield")
        assert hasattr(mod, "j2_tangent_matvec_apply")

        # 2x1x1 mesh, displacement large enough to drive every QP plastic.
        coords, conn = generate_hex8_mesh(2, 1, 1, 2.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        rng = np.random.default_rng(7)
        u_np = np.zeros((n_nodes, 3))
        u_np[:, 0] = 0.04 * coords[:, 0]
        u_np[:, 1] = -0.012 * coords[:, 1]
        v_np = rng.standard_normal((n_nodes, 3)) * 1e-2

        # Committed alpha history seeded entirely inside the sliver (n<1 regime).
        alpha_hist = np.full((n_elem, 8), alpha_sliver, dtype=np.float64)

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.u.from_numpy(u_np)
        mod.alpha.from_numpy(alpha_hist)

        out = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field = ti.Vector.field(3, dtype=ti.f64, shape=n_nodes)
        v_field.from_numpy(v_np)

        mod.j2_tangent_matvec_apply(out, v_field, _LAM, _MU, _SIGMA_Y0, _K_HARD, _N_HARD)
        kv_gen = out.to_numpy()

        # Reference linearises about the SAME committed sliver alpha.
        kv_ref = np.zeros((n_nodes, 3))
        for e in range(n_elem):
            nodes = conn[e]
            kv_e = element_tangent_matvec_plastic(
                u_np[nodes], coords[nodes], v_np[nodes], mat, alpha_hist[e]
            )
            for a in range(8):
                kv_ref[nodes[a]] += kv_e[a]

        max_diff = float(np.max(np.abs(kv_gen - kv_ref)))
        assert np.all(np.isfinite(kv_gen)), (
            "generated near-yield tangent produced non-finite values — the return "
            "map likely diverged (the 1e-12 floor should prevent this)"
        )
        assert max_diff < _GATE_TOL, (
            f"generated near-first-yield (n<1, alpha in (1e-30,1e-12]) tangent "
            f"differs from reference: max|Kv_gen - Kv_ref| = {max_diff:.3e} "
            f">= {_GATE_TOL:.0e}"
        )

    @pytest.mark.slow
    def test_history_state_evolves_on_device_across_newton(self, tmp_path):
        """Verifies: history fields (eps_p, α) advance correctly across Newton
        steps with the matvec kept on-device. AC-2. Passes when: committed α
        matches the reference history evolution AND no ``.to_numpy()`` appears in
        the plastic operator/solve hot path (on-device archival only at step
        boundary)."""

        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.ref.ref_hex8_plastic import element_internal_force_plastic

        source = _make_j2_source()

        # (a) The generated J2 operator hot path must contain NO NumPy: the kernel
        #     reads alpha from the device field and never snapshots it. This is
        #     the structural guarantee that history is managed on-device.
        matvec_body = _matvec_body(source)
        assert ".to_numpy()" not in matvec_body, (
            "generated J2 tangent operator must not call .to_numpy() — history "
            "(alpha) must be read on-device, not snapshotted to NumPy"
        )
        assert "alpha.from_numpy" not in matvec_body, (
            "generated J2 tangent operator must not write the alpha field — "
            "history advances only in compute_internal_force, never in the matvec"
        )
        # It DOES read the device history field directly (read-only).
        assert "alpha[e, q]" in matvec_body, (
            "generated J2 tangent operator must read alpha[e, q] from the device field"
        )
        # And it runs the return map on-device (algorithmic tangent, not d2Psi/dE2).
        assert "for _it in range(20):" in matvec_body, (
            "generated J2 tangent must re-run the radial-return Newton loop on-device"
        )

        # (b) On-device history evolution: compute_internal_force advances alpha[e, q]
        #     on the device. Drive a small displacement-controlled step and check
        #     the committed alpha matches the reference return-map evolution.
        mod = _import_generated_module(source, tmp_path, name="gen_p5_1_history")
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]
        mat = _j2_material()

        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))

        # A displacement past yield (eps ~ 0.6% > eps_yield ~ 0.1%).
        u_np = np.zeros((n_nodes, 3))
        u_np[:, 0] = 0.006 * coords[:, 0]
        mod.u.from_numpy(u_np)
        mod.alpha.from_numpy(np.zeros((n_elem, 8)))

        # On-device history advance (the residual kernel writes alpha[e, q]).
        mod.compute_internal_force(_LAM, _MU, _SIGMA_Y0, _K_HARD, _N_HARD)
        alpha_dev = mod.alpha.to_numpy()  # step-boundary archival only

        # Reference history evolution from alpha_old = 0 at the same displacement.
        alpha_ref = np.zeros((n_elem, 8), dtype=np.float64)
        for e in range(n_elem):
            nodes = conn[e]
            _f, alpha_new_e = element_internal_force_plastic(
                u_np[nodes], coords[nodes], mat, np.zeros(8)
            )
            alpha_ref[e] = alpha_new_e

        assert float(np.max(alpha_ref)) > 1e-6, (
            "test setup failed to drive any quadrature point plastic"
        )
        max_diff = float(np.max(np.abs(alpha_dev - alpha_ref)))
        assert max_diff < 1e-10, (
            f"on-device history (alpha) diverged from the reference return-map "
            f"evolution: max|alpha_dev - alpha_ref| = {max_diff:.3e}"
        )

    def test_jit_budget_respected_plastic_branch(self):
        """Verifies: the J2 re-linearised matrix-free branch stays within the JIT
        budget (the primary PJ risk). AC-3. Passes when:
        ``estimate_unrolled_lines(...) <= MAX_LINES_TI_FUNC`` for the emitted
        plastic tangent kernel (split via the optimizer ContractionPlan if
        needed; no hand-unrolling)."""
        element_ir = create_hex8_element_ir()
        plan = build_tangent_matvec_plan(element_ir)
        spec = tangent_matvec_apply_spec(element_ir)

        # The J2 plastic branch rides the SAME optimiser-recorded contraction as
        # SVK; only the per-QP A-formation differs. Re-run the budget counter over
        # the recorded path: the contraction must fit the 512-line @ti.func budget
        # and stay Tier <= 2 (no Tier-3 restructuring).
        lines = estimate_unrolled_lines(
            spec.einsum_string,
            list(spec.operand_shapes),
            plan.contraction_path,
        )
        assert lines <= MAX_LINES_TI_FUNC, (
            f"J2 tangent contraction is {lines} lines > {MAX_LINES_TI_FUNC} @ti.func budget"
        )
        assert plan.tier <= int(Tier.TIER_2)

    def test_full_j2_kernel_within_absolute_budget(self):
        """The FULL emitted ``j2_tangent_matvec_apply`` @ti.kernel honours the
        absolute JIT ceiling — the honest budget test (PlanJune14 WI-1).

        The pre-existing ``test_jit_budget_respected_plastic_branch`` only gated
        the inner contraction ``@ti.func`` (~203 lines); Codex correctly flagged
        that it never measured the *full* kernel, whose C_ep (3⁴) + A-transform
        (3⁶) physics nesting once multiplied by a ``ti.static`` N_QP=8 q-loop ran
        ~18k unrolled lines (well over both limits). WI-1's runtime-q lever
        divides the per-QP unroll by 8, bringing the full kernel under the 5000
        absolute ceiling. The count is the project's "unrolled lines" weighting
        (07-CONVENTIONS §JIT-budget) via :func:`count_unrolled_kernel_lines`.

        NOTE: the J2 kernel lands at ~2268 unrolled — under the 5000 ABSOLUTE
        ceiling (the must-have) but marginally OVER the 2000 ``@ti.kernel`` soft
        target. Driving it under 2000 requires a *second* lever (Tier-3 on the
        C_ep/A physics loops, or optimiser-routing the A-formation), which
        inverts the "physics indices → ti.static" convention and is a deliberate
        out-of-scope decision for WI-1 (see ``dev/plans/pj14_fix.md``). The hard
        assertion here is therefore the absolute ceiling; the @ti.kernel target
        is asserted for the SVK kernel (which clears it) in ``test_p3_2.py``.
        """
        from tests._e2e_helpers import count_unrolled_kernel_lines

        source = _make_j2_source()
        unrolled = count_unrolled_kernel_lines(source, "j2_tangent_matvec_apply")
        assert unrolled <= MAX_LINES_ABSOLUTE, (
            f"full j2_tangent_matvec_apply is {unrolled} unrolled lines > "
            f"{MAX_LINES_ABSOLUTE} absolute ceiling"
        )

    def test_j2_generated_kernel_routes_through_optimizer_not_handrolled(self):
        """The J2 matvec consumes the opt_einsum ContractionPlan (no hand-rolled
        contraction) — the SAME path as the SVK P3-2 kernel."""
        source = _make_j2_source()

        # The generated kernel must exist and target the ti_runtime seam.
        assert "def j2_tangent_matvec_apply(" in source
        assert "from ti_runtime import tensor_ti as _tt" in source

        # The optimiser-recorded path must be embedded in the emitted source.
        element_ir = create_hex8_element_ir()
        plan = build_tangent_matvec_plan(element_ir)
        assert plan.einsum_string == TANGENT_MATVEC_APPLY_EINSUM
        assert str(list(plan.contraction_path)) in source, (
            "the emitted J2 kernel must embed the opt_einsum ContractionPlan path "
            f"{list(plan.contraction_path)}"
        )
        assert plan.einsum_string in source

        # The three recorded pairwise steps are realised as step comments.
        assert "step 1" in source and "step 2" in source and "step 3" in source

    def test_j2_generated_kernel_uses_algorithmic_not_energy_tangent(self):
        """The dissipative-model rule: the generated J2 tangent is the algorithmic
        consistent tangent (linearisation of the return map), NOT ∂²Ψ/∂E²."""
        body = _matvec_body(_make_j2_source())

        # Algorithmic markers: the return-map Newton loop, the plastic multiplier,
        # and the Simo-Hughes Box 3.5 consistent-tangent terms are all present.
        assert "for _it in range(20):" in body, "return-map Newton loop missing"
        assert "dl -= f / df" in body, "plastic-multiplier Newton update missing"
        assert "sigma_eq - 3.0 * mu * dl - sy" in body, "yield residual missing"
        # Consistent-tangent assembly (theta scaling + deviatoric/flow structure).
        assert "theta = 1.0 - 3.0 * mu * dl / sigma_eq" in body, (
            "algorithmic-tangent return-map scaling (theta) missing"
        )
        assert "n_flow = S_dev_trial / sigma_eq" in body, (
            "algorithmic-tangent flow direction (n) missing"
        )
        # It must NOT differentiate a stored energy: no SymPy / energy-diff hooks.
        # (The kernel comment legitimately states it is "NOT d2Psi/dE2"; what must
        # be absent is an actual symbolic-differentiation call site.)
        assert "sympy" not in body.lower()
        assert ".diff(" not in body
        assert "hessian" not in body.lower()

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_generated_newton_driver_committed_alpha_vs_ref_multistep(self, tmp_path):
        """WI-2 (PlanJune14 / dev/plans/pj14_fix.md): decisive multi-step,
        multi-iteration plastic Newton regression for the *generated* driver's
        single-``alpha``-field history management.

        Codex finding #2 (CONFIRMED, then FIXED): the generated J2 path uses a
        single ``alpha`` field as both committed and trial plastic history.
        ``compute_internal_force`` reads ``alpha[e, q]`` as ``alpha_old``, runs
        the radial return, and writes ``alpha_new`` back into the SAME field.
        Before the WI-2 fix the generated ``newton_solve`` driver did NO
        snapshot/restore of ``alpha`` between residual evaluations, so iteration
        k read iteration k-1's *trial* alpha as ``alpha_old`` — plastic strain
        ratcheted and Newton stalled (diverged on plasticity). The reference
        ``solve_plastic`` instead keeps ``alpha_old``/``alpha_current`` separate,
        assembles every Newton iteration from the COMMITTED ``alpha_old``, and
        ``commit()``s only on convergence.

        WI-2 fix (faithful to the reference, gated to the plastic path): the
        generated ``newton_solve`` snapshots the committed history
        (``_alpha_committed.copy_from(alpha)``) before the Newton loop and
        restores it (``alpha.copy_from(_alpha_committed)``) at the top of every
        iteration before ``compute_internal_force`` — so each residual/tangent
        evaluation starts from the committed step-start state. On non-convergence
        it restores the committed history before raising (mirrors the reference
        ``rollback()``). The snapshot/restore is an on-device ``copy_from`` into
        the device-resident ``_alpha_committed`` mirror field (no host round-trip).

        This test drives the *generated* ``newton_solve`` across multiple
        displacement-controlled load steps well past yield (step-boundary commit
        only, matching the reference ``commit()``) and asserts the converged
        displacement AND the committed alpha match the reference ``solve_plastic``
        within the strict 1e-10 gate tolerance (07-CONVENTIONS §6).

        It is genuinely decisive because it asserts (1) plasticity is active
        (committed alpha > 0 at yielded QPs), and (2) >1 Newton iteration occurs
        in at least one load step — otherwise the single-field aliasing would
        never be exercised across iterations.
        """
        from tests._e2e_helpers import _import_generated_module
        from tests.ref.ref_hex8_elastic import generate_hex8_mesh
        from tests.ref.ref_hex8_plastic import solve_plastic

        source = _make_j2_source()

        # --- Structural guard (WI-2 fix): the generated driver snapshots the
        #     committed plastic history before the Newton loop and restores it
        #     each iteration before compute_internal_force, so every residual eval
        #     reads the committed alpha_old (not the previous iteration's trial).
        #     This is the single-field committed/trial separation under test; if a
        #     future edit removes the snapshot/restore the guard fails loudly and
        #     the numerical drift below would re-confirm finding #2.
        ns_start = source.find("def newton_solve(")
        assert ns_start >= 0, "generated module missing newton_solve driver"
        ns_body = source[ns_start : source.find("\ndef ", ns_start + 1)]
        assert "_alpha_committed.copy_from(alpha)" in ns_body, (
            "newton_solve must snapshot the committed plastic history before the "
            "Newton loop (the WI-2 fix for single-field committed/trial aliasing), "
            "now via on-device copy_from into the _alpha_committed mirror field"
        )
        assert "alpha.copy_from(_alpha_committed)" in ns_body, (
            "newton_solve must restore the committed plastic history each iteration "
            "(and on non-convergence) — matches reference solve_plastic alpha_old; "
            "now via on-device copy_from from the _alpha_committed mirror field"
        )
        assert "compute_internal_force(" in ns_body, (
            "newton_solve must call compute_internal_force, which mutates alpha in place"
        )

        mat = _j2_material()

        # 1-element unit cube, displacement-controlled uniaxial tension.
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]

        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]

        # eps_yield ~ sigma_y0/E ~ 1e-3; 0.01 total strain over 5 steps is ~10x
        # yield => strongly plastic, several Newton iterations per step.
        total_disp = 0.01
        n_steps = 5

        # bc_mask: fixed left face (all DOFs) + prescribed right face x-DOF.
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_mask[left_nodes, :] = True
        bc_mask[right_nodes, 0] = True

        # --- Generated solver: drive newton_solve once per load step, with only
        #     step-boundary alpha commit (matching the reference commit()). No
        #     per-iteration alpha reset — the generated driver mutates the single
        #     field in place across its own Newton iterations.
        mod = _import_generated_module(source, tmp_path, name="gen_p5_1_wi2_driver")
        mod.allocate_fields(n_nodes, n_elem)
        mod.x_ref.from_numpy(coords)
        mod.elem_nodes.from_numpy(conn.astype(np.int32))
        mod.u.from_numpy(np.zeros((n_nodes, 3)))
        mod.f_ext.from_numpy(np.zeros((n_nodes, 3)))

        # Committed history at step boundaries (the generated analogue of the
        # reference HistoryFields.alpha_old). Initialised to zero (virgin state).
        alpha_committed = np.zeros((n_elem, 8), dtype=np.float64)

        # Flat constrained-DOF indices for newton_solve's BC enforcement.
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        iters_per_step: list[int] = []
        for step in range(1, n_steps + 1):
            fraction = step / n_steps
            bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
            bc_values[right_nodes, 0] = fraction * total_disp
            bc_values_flat = bc_values.ravel()[bc_dofs]

            # Seed the live alpha field with the COMMITTED state for this step.
            # newton_solve will mutate it in place across its iterations.
            mod.alpha.from_numpy(alpha_committed)

            n_iters = mod.newton_solve(
                _LAM,
                _MU,
                _SIGMA_Y0,
                _K_HARD,
                _N_HARD,
                bc_dofs=bc_dofs,
                bc_values=bc_values_flat,
                max_iter=50,
                tol_abs=1e-12,
                tol_rel=1e-8,
            )
            iters_per_step.append(int(n_iters))

            # Commit: the converged live alpha becomes the next step's committed
            # state (the generated analogue of HistoryFields.commit()).
            alpha_committed = mod.alpha.to_numpy().copy()

        u_gen = mod.u.to_numpy()
        alpha_gen = alpha_committed

        # --- Reference solver: identical problem, internal load stepping with
        #     committed/trial separation + commit()/rollback().
        bc_values_ref = np.zeros((n_nodes, 3), dtype=np.float64)
        bc_values_ref[right_nodes, 0] = total_disp
        f_ext_ref = np.zeros((n_nodes, 3), dtype=np.float64)

        u_ref, history_ref, ref_residuals = solve_plastic(
            coords,
            conn,
            mat,
            bc_mask,
            bc_values_ref,
            f_ext_ref,
            n_steps=n_steps,
            tol=1e-8,
            max_iter=50,
        )
        alpha_ref = history_ref.alpha_old  # committed history at full load

        # --- Yielding + multi-iteration evidence (else the drift is untested). ---
        assert float(np.max(alpha_gen)) > 1e-6, (
            f"generated committed alpha never yielded (max={np.max(alpha_gen):.3e}); "
            "the single-field history drift would not be exercised"
        )
        assert float(np.max(alpha_ref)) > 1e-6, "reference never yielded — bad test setup"
        # At least one step took >1 Newton iteration (so alpha is read+written
        # more than once within that step from the single field).
        assert max(iters_per_step) > 1, (
            f"no load step took >1 Newton iteration (iters/step={iters_per_step}); "
            "the multi-iteration single-field aliasing is not exercised"
        )
        # The reference must also show multi-iteration steps (same regime).
        assert any(len(r) > 2 for r in ref_residuals), (
            f"reference Newton converged in <=1 update every step "
            f"(residual lengths={[len(r) for r in ref_residuals]})"
        )

        # --- Decisive comparison: displacement AND committed alpha. ---
        max_u_diff = float(np.max(np.abs(u_gen - u_ref)))
        max_alpha_diff = float(np.max(np.abs(alpha_gen - alpha_ref)))

        assert max_u_diff < _GATE_TOL, (
            f"generated driver displacement drifted from reference solve_plastic: "
            f"max|u_gen - u_ref| = {max_u_diff:.3e} >= {_GATE_TOL:.0e} "
            f"(iters/step={iters_per_step})"
        )
        assert max_alpha_diff < _GATE_TOL, (
            f"generated driver COMMITTED ALPHA drifted from reference solve_plastic "
            f"across multi-iteration Newton steps: "
            f"max|alpha_gen - alpha_ref| = {max_alpha_diff:.3e} >= {_GATE_TOL:.0e} "
            f"(max alpha_gen={np.max(alpha_gen):.3e}, max alpha_ref={np.max(alpha_ref):.3e}, "
            f"iters/step={iters_per_step}) — finding #2 (single-field history "
            f"drift) is CONFIRMED if this fails"
        )

    def test_svk_source_has_no_j2_kernel(self):
        """The J2 generated kernel is gated to the J2 path only — SVK source
        must not carry it (keeps every non-J2 golden byte-identical)."""
        svk_ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(model="svk", params={"E": _E_YOUNG, "nu": _NU}),
            boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
        )
        loc_result, plans = localise_and_optimize(svk_ir)
        svk_source = emit(ArtifactBundle.from_pipeline(svk_ir, loc_result, plans))
        assert "def j2_tangent_matvec_apply(" not in svk_source
        # SVK keeps its own generated kernel.
        assert "def svk_tangent_matvec_apply(" in svk_source
