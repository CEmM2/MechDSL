"""Tests for P8.1, P8.2, P8.4 -- plastic constitutive emission and kernel switch.

Covers:
1.  J2 constitutive emitted: source contains ``constitutive_update_plastic``.
2.  Radial return loop: source contains Newton iteration for delta_lambda.
3.  Von Mises guard: source contains sigma_eq check against 1e-12.
4.  Alpha update: source contains alpha_new assignment.
5.  Yield function: source contains ``sigma_eq - 3.0 * mu * dl - sy`` pattern.
6.  History field in kernel: J2 source reads/writes alpha field.
7.  Elastic path unchanged: SVK source still correct after changes.
8.  Branch dispatch: J2 kernel calls ``constitutive_update_plastic``,
    SVK calls ``constitutive_update``.
9.  Syntactically valid: both SVK and J2 source parse with ``ast.parse``.
10. Deterministic: J2 emission is deterministic.
11. Material params in J2: source contains sigma_y0, K_hard, n_hard params.
12. Tangent works for both: tangent matvec emitted for both models.
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
from mechdsl.lowering.fe_localise import localise_and_optimize

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
# Test 1: J2 constitutive emitted
# ---------------------------------------------------------------------------


class TestJ2ConstitutiveEmitted:
    def test_constitutive_update_plastic_defined(self, j2_source: str) -> None:
        """J2 source defines constitutive_update_plastic function."""
        assert "def constitutive_update_plastic(" in j2_source

    def test_ti_func_decorator(self, j2_source: str) -> None:
        """The constitutive function has @ti.func decorator."""
        assert "@ti.func" in j2_source


# ---------------------------------------------------------------------------
# Test 2: Radial return loop
# ---------------------------------------------------------------------------


class TestRadialReturnLoop:
    def test_newton_iteration_present(self, j2_source: str) -> None:
        """Source contains Newton iteration loop for radial return."""
        assert "for _it in range(20):" in j2_source

    def test_delta_lambda_variable(self, j2_source: str) -> None:
        """Source contains delta_lambda (dl) variable."""
        assert "dl = ti.f64(0.0)" in j2_source

    def test_convergence_check(self, j2_source: str) -> None:
        """Newton loop has convergence check."""
        assert "ti.abs(f) < 1e-12" in j2_source

    def test_derivative_computation(self, j2_source: str) -> None:
        """Newton loop computes derivative for update."""
        assert "df = -3.0 * mu - H_prime" in j2_source
        assert "dl -= f / df" in j2_source


# ---------------------------------------------------------------------------
# Test 3: Von Mises guard
# ---------------------------------------------------------------------------


class TestVonMisesGuard:
    def test_sigma_eq_near_zero_guard(self, j2_source: str) -> None:
        """Source contains the near-zero sigma_eq guard."""
        assert "1e-12 * sigma_y" in j2_source

    def test_sigma_eq_computation(self, j2_source: str) -> None:
        """Source computes sigma_eq from deviatoric stress."""
        assert "sigma_eq = ti.sqrt(1.5 * s_sq)" in j2_source


# ---------------------------------------------------------------------------
# Test 4: Alpha update
# ---------------------------------------------------------------------------


class TestAlphaUpdate:
    def test_alpha_new_assigned(self, j2_source: str) -> None:
        """Source contains alpha_new assignment."""
        assert "alpha_new = alpha_old + dl" in j2_source

    def test_alpha_new_initial(self, j2_source: str) -> None:
        """Alpha initialized to old value before yield check."""
        assert "alpha_new = alpha_old" in j2_source


# ---------------------------------------------------------------------------
# Test 5: Yield function
# ---------------------------------------------------------------------------


class TestYieldFunction:
    def test_yield_residual(self, j2_source: str) -> None:
        """Source contains yield function residual: sigma_eq - 3*mu*dl - sy."""
        assert "sigma_eq - 3.0 * mu * dl - sy" in j2_source

    def test_hardening_law(self, j2_source: str) -> None:
        """Source contains power-law hardening evaluation."""
        assert "sigma_y0 + K_hard * ti.pow(alpha_old, n_hard)" in j2_source


# ---------------------------------------------------------------------------
# Test 6: History field in kernel
# ---------------------------------------------------------------------------


class TestHistoryFieldInKernel:
    def test_alpha_field_read(self, j2_source: str) -> None:
        """J2 kernel reads alpha history from field."""
        assert "alpha_old = alpha[e, q]" in j2_source

    def test_alpha_field_write(self, j2_source: str) -> None:
        """J2 kernel writes updated alpha back to field."""
        assert "alpha[e, q] = alpha_new" in j2_source

    def test_alpha_field_declared(self, j2_source: str) -> None:
        """J2 source declares the alpha field."""
        assert "alpha = ti.field(dtype=ti.f64)" in j2_source

    def test_alpha_field_allocated(self, j2_source: str) -> None:
        """J2 source allocates the alpha field per element per quad point."""
        assert "(n_elem, N_QP)).place(alpha)" in j2_source


# ---------------------------------------------------------------------------
# Test 7: Elastic path unchanged
# ---------------------------------------------------------------------------


class TestElasticPathUnchanged:
    def test_svk_constitutive_update_present(self, svk_source: str) -> None:
        """SVK source still defines constitutive_update (elastic)."""
        assert "def constitutive_update(" in svk_source

    def test_svk_stress_formula(self, svk_source: str) -> None:
        """SVK stress formula unchanged: S = lam*tr_E*I + 2*mu*E."""
        assert "S = lam * tr_E * I3 + 2.0 * mu * E" in svk_source

    def test_svk_cauchy_green(self, svk_source: str) -> None:
        """SVK still computes C = F^T @ F."""
        assert "C = F.transpose() @ F" in svk_source

    def test_svk_no_alpha(self, svk_source: str) -> None:
        """SVK source does not contain alpha history field."""
        assert "alpha = ti.field" not in svk_source

    def test_svk_no_plastic_function(self, svk_source: str) -> None:
        """SVK source does not define constitutive_update_plastic."""
        assert "constitutive_update_plastic" not in svk_source


# ---------------------------------------------------------------------------
# Test 8: Branch dispatch
# ---------------------------------------------------------------------------


class TestBranchDispatch:
    def test_j2_kernel_calls_plastic(self, j2_source: str) -> None:
        """J2 internal force kernel calls constitutive_update_plastic."""
        assert "constitutive_update_plastic(" in j2_source

    def test_svk_kernel_calls_elastic(self, svk_source: str) -> None:
        """SVK internal force kernel calls constitutive_update."""
        assert "S = constitutive_update(F, lam, mu)" in svk_source

    def test_svk_kernel_no_plastic_call(self, svk_source: str) -> None:
        """SVK kernel does not call constitutive_update_plastic."""
        # Count occurrences -- SVK should have zero
        assert svk_source.count("constitutive_update_plastic") == 0

    def test_j2_kernel_extra_params(self, j2_source: str) -> None:
        """J2 kernel signature includes plasticity parameters."""
        assert "sigma_y0: ti.f64" in j2_source
        assert "K_hard: ti.f64" in j2_source
        assert "n_hard: ti.f64" in j2_source


# ---------------------------------------------------------------------------
# Test 9: Syntactically valid
# ---------------------------------------------------------------------------


class TestSyntacticallyValid:
    def test_svk_parses(self, svk_source: str) -> None:
        """SVK emitted source parses as valid Python."""
        try:
            ast.parse(svk_source)
        except SyntaxError as exc:
            pytest.fail(f"SVK source has syntax error: {exc}")

    def test_j2_parses(self, j2_source: str) -> None:
        """J2 emitted source parses as valid Python."""
        try:
            ast.parse(j2_source)
        except SyntaxError as exc:
            pytest.fail(f"J2 source has syntax error: {exc}")


# ---------------------------------------------------------------------------
# Test 10: Deterministic
# ---------------------------------------------------------------------------


class TestDeterministic:
    def test_j2_deterministic(self, j2_bundle: ArtifactBundle) -> None:
        """Two J2 emissions produce identical source."""
        source_a = emit(j2_bundle)
        source_b = emit(j2_bundle)
        assert source_a == source_b


# ---------------------------------------------------------------------------
# Test 11: Material params in J2
# ---------------------------------------------------------------------------


class TestMaterialParamsInJ2:
    def test_sigma_y0_param(self, j2_source: str) -> None:
        """J2 source contains sigma_y0 parameter."""
        assert "sigma_y0" in j2_source

    def test_k_hard_param(self, j2_source: str) -> None:
        """J2 source contains K_hard parameter."""
        assert "K_hard" in j2_source

    def test_n_hard_param(self, j2_source: str) -> None:
        """J2 source contains n_hard parameter."""
        assert "n_hard" in j2_source

    def test_params_in_constitutive_signature(self, j2_source: str) -> None:
        """J2 constitutive function signature has all plasticity params."""
        # Check the function definition line includes the params
        assert "sigma_y0: ti.f64, K_hard: ti.f64, n_hard: ti.f64" in j2_source


# ---------------------------------------------------------------------------
# Test 12: Tangent works for both
# ---------------------------------------------------------------------------


class TestTangentForBoth:
    """Both SVK and J2 emit an analytical consistent-tangent matvec.

    PLAN-A §A7.5 / §A9.2: the emitted ``tangent_matvec`` is the analytical
    linearisation of the internal force (constant SVK tangent for elastic,
    algorithmic consistent tangent for J2) — no finite-difference
    perturbation and no ``compute_internal_force`` round-trip.
    """

    def test_svk_tangent_matvec(self, svk_source: str) -> None:
        """SVK source contains tangent_matvec function."""
        assert "def tangent_matvec(" in svk_source

    def test_j2_tangent_matvec(self, j2_source: str) -> None:
        """J2 source contains tangent_matvec function."""
        assert "def tangent_matvec(" in j2_source

    def test_svk_tangent_is_analytical(self, svk_source: str) -> None:
        """SVK tangent uses analytical push-forward, not FD perturbation."""
        assert "FD_EPS" not in svk_source
        assert "dP = grad_v @ S + F @ dS" in svk_source

    def test_j2_tangent_is_analytical(self, j2_source: str) -> None:
        """J2 tangent calls radial_return for the consistent tangent per QP."""
        assert "FD_EPS" not in j2_source
        assert "from mechdsl.symbolic.models.j2_power_law import" in j2_source
        assert "radial_return(_j2_mat, E, float(alpha_np[e, q]))" in j2_source

    def test_j2_tangent_does_not_mutate_alpha(self, j2_source: str) -> None:
        """Analytical J2 tangent reads alpha once and never writes it back."""
        assert "alpha_np = alpha.to_numpy()" in j2_source
        assert "alpha.from_numpy" not in j2_source
        # The FD save/restore pattern must be gone.
        assert "alpha_save" not in j2_source

    def test_svk_tangent_no_alpha(self, svk_source: str) -> None:
        """SVK tangent does not touch alpha history at all."""
        # alpha is a J2-only history field; the SVK field layout never
        # allocates it, and the tangent must not reference it.
        assert "alpha[e, q]" not in svk_source
        assert "alpha_np" not in svk_source

    def test_tangent_does_not_call_internal_force(self, svk_source: str, j2_source: str) -> None:
        """Neither tangent invokes compute_internal_force (analytical is one-shot).

        The Newton driver still calls compute_internal_force to evaluate the
        residual; the tangent matvec itself must not.  We verify this by
        extracting the tangent_matvec function body through a simple
        indent-aware slice rather than importing a helper across test files.
        """
        for source in (svk_source, j2_source):
            start = source.find("def tangent_matvec(")
            assert start >= 0, "tangent_matvec definition not found"
            # Find the next top-level def/class after tangent_matvec.
            rest = source[start:]
            next_boundary = len(rest)
            for marker in ("\ndef ", "\nclass ", "\n@ti.kernel"):
                idx = rest.find(marker, 1)
                if idx != -1 and idx < next_boundary:
                    next_boundary = idx
            matvec_body = rest[:next_boundary]
            assert "compute_internal_force(" not in matvec_body, (
                "Analytical tangent_matvec must not call compute_internal_force"
            )

    def test_j2_tangent_accepts_plastic_params(self, j2_source: str) -> None:
        """J2 tangent_matvec signature includes the plasticity parameters."""
        assert "def tangent_matvec(v_flat: np.ndarray, lam: float, mu: float," in j2_source
        assert "sigma_y0: float, K_hard: float," in j2_source
        assert "n_hard: float)" in j2_source

    def test_svk_tangent_elastic_params_only(self, svk_source: str) -> None:
        """SVK tangent_matvec signature only takes (v_flat, lam, mu)."""
        assert (
            "def tangent_matvec(v_flat: np.ndarray, lam: float, mu: float) -> np.ndarray:"
            in svk_source
        )


# ---------------------------------------------------------------------------
# Phase 4 audit stubs
# ---------------------------------------------------------------------------


class TestTaskP4T1Audit:
    """Task P4-T1: Audit J2 constitutive emission against symbolic model.

    Verifies emitted radial return matches j2_power_law.py::radial_return()
    step-by-step (all 7 algorithm steps in correct order).
    """

    def test_j2_emission_matches_symbolic_algorithm_steps(self):
        """Verifies: All 7 radial return steps emitted in correct order.

        Acceptance criterion: Emitted radial return matches symbolic algorithm.
        Passes when: elastic predictor, deviatoric split, von Mises,
        yield check, scalar Newton, stress update, alpha update all present
        and ordered correctly in emitted source.
        """
        source = emit(_make_j2_bundle())

        # Step 1: Kinematics — right Cauchy-Green and Green-Lagrange strain
        step1_c = "C = F.transpose() @ F"
        step1_e = "E = 0.5 * (C - I3)"

        # Step 2: Elastic trial stress
        step2 = "S_trial = lam * tr_E * I3 + 2.0 * mu * E"

        # Step 3: Deviatoric / volumetric split
        step3_dev = "S_dev = S_trial - (tr_S / 3.0) * I3"

        # Step 4: Von Mises equivalent stress with near-zero guard
        step4_eq = "sigma_eq = ti.sqrt(1.5 * s_sq)"
        step4_guard = "1e-12 * sigma_y"

        # Step 5: Yield check — combined guard and yield condition
        step5 = "sigma_eq > 1e-12 * sigma_y and sigma_eq > sigma_y"

        # Step 6: Newton iteration for delta_lambda
        step6_loop = "for _it in range(20):"
        step6_residual = "sigma_eq - 3.0 * mu * dl - sy"
        step6_update = "dl -= f / df"

        # Step 7: Stress and alpha update
        step7_factor = "factor = 1.0 - 3.0 * mu * dl / sigma_eq"
        step7_stress = "S = S_vol + factor * S_dev"
        step7_alpha = "alpha_new = alpha_old + dl"

        # Verify all steps are present
        all_patterns = [
            ("Step 1 - C = F^T F", step1_c),
            ("Step 1 - E = 0.5*(C-I)", step1_e),
            ("Step 2 - elastic trial S_trial", step2),
            ("Step 3 - deviatoric split", step3_dev),
            ("Step 4 - von Mises sigma_eq", step4_eq),
            ("Step 4 - near-zero guard", step4_guard),
            ("Step 5 - yield check condition", step5),
            ("Step 6 - Newton loop", step6_loop),
            ("Step 6 - yield residual", step6_residual),
            ("Step 6 - Newton update", step6_update),
            ("Step 7 - stress factor", step7_factor),
            ("Step 7 - stress update", step7_stress),
            ("Step 7 - alpha update", step7_alpha),
        ]
        for label, pattern in all_patterns:
            assert pattern in source, f"Missing {label}: pattern {pattern!r} not found"

        # Verify ordering: steps must appear in the correct sequence
        positions = {label: source.index(pattern) for label, pattern in all_patterns}

        # Kinematics before trial stress
        assert positions["Step 1 - C = F^T F"] < positions["Step 2 - elastic trial S_trial"], (
            "Kinematics (C) must come before elastic trial stress"
        )
        assert positions["Step 1 - E = 0.5*(C-I)"] < positions["Step 2 - elastic trial S_trial"], (
            "Kinematics (E) must come before elastic trial stress"
        )

        # Trial stress before deviatoric split
        assert (
            positions["Step 2 - elastic trial S_trial"] < positions["Step 3 - deviatoric split"]
        ), "Elastic trial must come before deviatoric split"

        # Deviatoric split before von Mises
        assert positions["Step 3 - deviatoric split"] < positions["Step 4 - von Mises sigma_eq"], (
            "Deviatoric split must come before von Mises computation"
        )

        # Von Mises before yield check
        assert (
            positions["Step 4 - von Mises sigma_eq"] < positions["Step 5 - yield check condition"]
        ), "Von Mises must come before yield check"

        # Yield check before Newton loop
        assert positions["Step 5 - yield check condition"] < positions["Step 6 - Newton loop"], (
            "Yield check must come before Newton iteration"
        )

        # Newton residual before Newton update (inside the loop)
        assert positions["Step 6 - yield residual"] < positions["Step 6 - Newton update"], (
            "Newton residual evaluation must come before the Newton step update"
        )

        # Newton loop before stress update
        assert positions["Step 6 - Newton loop"] < positions["Step 7 - stress update"], (
            "Newton iteration must come before stress update"
        )

        # Stress update before alpha update
        assert positions["Step 7 - stress update"] < positions["Step 7 - alpha update"], (
            "Stress update must come before alpha update"
        )


class TestTaskP4T4Safeguards:
    """Task P4-T4: Verify numerical safeguards in emitted J2 code.

    Checks 4 safeguards per 07-CONVENTIONS.md section 6:
    J > 1e-15, sigma_eq > tol, delta_lambda >= 0, hardening derivative floor.
    """

    def test_j_guard_in_emitted_code(self):
        """Verifies: J > 1e-15 guard present in emitted element code.

        Acceptance criterion: All 4 safeguards present in emitted code
        Passes when: Jacobian positivity check found in emitted source
        """
        source = emit(_make_j2_bundle())
        # The guard must appear after detJ0 is computed and before J0_inv / dNdX
        assert "if detJ0 > 1e-15:" in source, (
            "J > 1e-15 degenerate-element guard missing from emitted code (07-CONVENTIONS.md §6)"
        )
        pos_det = source.find("detJ0 = J0.determinant()")
        pos_guard = source.find("if detJ0 > 1e-15:")
        pos_inv = source.find("J0_inv = J0.inverse()")
        assert pos_det < pos_guard, "detJ0 guard must appear after detJ0 is computed"
        assert pos_guard < pos_inv, (
            "J0.inverse() must be called only inside the detJ0 > 1e-15 guard"
        )

    def test_hardening_derivative_guard_in_emitted_code(self):
        """Verifies: alpha^(n-1) hardening derivative has 1e-30 floor in emitted code.

        Acceptance criterion: Safeguards match 07-CONVENTIONS.md section 6
        Passes when: floor guard on hardening derivative found in emitted Taichi source
        """
        source = emit(_make_j2_bundle())
        # Guard pattern: ternary that checks alpha_trial > 1e-30 before ti.pow(alpha_trial, n_hard - 1.0)
        assert "alpha_trial > 1e-30" in source, (
            "Hardening derivative 1e-30 floor guard missing from emitted J2 code "
            "(07-CONVENTIONS.md §6)"
        )
        # The guarded expression must fall back to 0.0 when alpha_trial is near zero
        assert "else 0.0" in source, (
            "Hardening derivative guard must fall back to 0.0 when alpha_trial <= 1e-30"
        )
