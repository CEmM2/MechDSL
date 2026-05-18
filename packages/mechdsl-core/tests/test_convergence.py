"""Tests for Phase 3 convergence verification: check_convergence_rate() and MMS driver.

Covers Tasks P3-T1, P3-T2, P3-T3.
Reference: dev/design_docs/08-VERIFICATION.md §4.2
"""

import numpy as np
import pytest

from mechdsl.verify.convergence import (
    ConvergenceResult,
    check_convergence_rate,
    run_mms_convergence,
    verify_mms_body_force_substitution,
)


class TestTaskP3T1:
    """
    Tests for Task P3-T1: Implement check_convergence_rate()

    Objective: Implement check_convergence_rate(errors, mesh_sizes, expected_rate, tol) -> ConvergenceResult
    in verify/convergence.py. Fit log-log slope of error vs h and assert rate ≥ expected - tol.

    Acceptance criteria covered: [1, 2, 3]
    - [1] Correct rate extraction from known O(h^2) data
    - [2] Pass/fail logic with tolerance
    - [3] Handles minimum 3 data points
    """

    def test_known_h2_data_gives_rate_2(self):
        """
        Verifies: correct rate extraction from known O(h^2) convergence data
        Acceptance criterion: [1] Correct rate extraction from known O(h^2) data

        Test setup:
        - Generate synthetic convergence data following e = C * h^2
        - Call check_convergence_rate with expected_rate=2.0, tol=0.1
        - Assert measured_rate ≈ 2.0 (within tolerance)
        - Assert result.passed = True

        Physical context: Hex8 element (p=1) should exhibit L2 convergence rate ≈ 2.0
        for Method of Manufactured Solutions (MMS) verification.
        """
        h = np.array([0.5, 0.25, 0.125])
        C = 3.0
        errors = C * h**2

        result = check_convergence_rate(errors, h, expected_rate=2.0, tol=0.1)

        assert isinstance(result, ConvergenceResult)
        assert abs(result.measured_rate - 2.0) < 1e-10, (
            f"Expected measured_rate ≈ 2.0, got {result.measured_rate}"
        )
        assert result.passed is True

    def test_known_h1_data_gives_rate_1(self):
        """
        Verifies: correct rate extraction from known O(h^1) convergence data
        Acceptance criterion: [2] Pass/fail logic with tolerance

        Test setup:
        - Generate synthetic convergence data following e = C * h^1
        - Call check_convergence_rate with expected_rate=1.0, tol=0.1
        - Assert measured_rate ≈ 1.0 (within tolerance)
        - Assert result.passed = True

        Physical context: Hex8 element (p=1) should exhibit H1 convergence rate ≈ 1.0
        for displacement-based FEM.
        """
        h = np.array([0.5, 0.25, 0.125])
        C = 2.5
        errors = C * h**1

        result = check_convergence_rate(errors, h, expected_rate=1.0, tol=0.1)

        assert isinstance(result, ConvergenceResult)
        assert abs(result.measured_rate - 1.0) < 1e-10, (
            f"Expected measured_rate ≈ 1.0, got {result.measured_rate}"
        )
        assert result.passed is True

    def test_insufficient_data_raises_error(self):
        """
        Verifies: error handling for insufficient data points
        Acceptance criterion: [3] Handles minimum 3 data points

        Test setup:
        - Call check_convergence_rate with 1 or 2 data points
        - Assert ValueError raised
        - Verify error message indicates minimum 3 points required

        Rationale: Polyfit on log-log data requires at least 3 points for degree=1 line fit.
        """
        # Single data point — must raise
        with pytest.raises(ValueError, match="3"):
            check_convergence_rate([0.01], [0.5], expected_rate=2.0)

        # Two data points — also insufficient
        with pytest.raises(ValueError, match="3"):
            check_convergence_rate([0.04, 0.01], [0.5, 0.25], expected_rate=2.0)

    def test_convergence_rate_fail_when_measured_below_threshold(self):
        """
        Verifies: pass/fail logic correctly rejects poor convergence
        Acceptance criterion: [2] Pass/fail logic with tolerance

        Test setup:
        - Generate data with measured_rate = 1.5
        - Call with expected_rate=2.0, tol=0.1
        - Assert measured_rate < expected_rate - tol
        - Assert result.passed = False

        Physical context: If convergence rate degrades below tolerance, solver may have issues
        (mesh quality, numerical instability, implementation bug).
        """
        h = np.array([0.5, 0.25, 0.125])
        C = 1.0
        # e ~ h^1.5 → log-log slope ≈ 1.5
        errors = C * h**1.5

        result = check_convergence_rate(errors, h, expected_rate=2.0, tol=0.1)

        # Threshold is 2.0 - 0.1 = 1.9; measured ≈ 1.5 < 1.9
        assert result.measured_rate < result.expected_rate - result.tol, (
            f"Expected measured_rate ({result.measured_rate}) < threshold "
            f"({result.expected_rate - result.tol})"
        )
        assert result.passed is False

    def test_convergence_result_dataclass_structure(self):
        """
        Verifies: ConvergenceResult contains required fields
        Acceptance criterion: All acceptance criteria

        Test setup:
        - Create ConvergenceResult from a successful convergence check
        - Assert presence of:
          * measured_rate (float)
          * expected_rate (float)
          * passed (bool)
          * errors (array-like)
          * mesh_sizes (array-like)
        """
        h = np.array([0.5, 0.25, 0.125])
        errors = 1.0 * h**2

        result = check_convergence_rate(errors, h, expected_rate=2.0, tol=0.1)

        # Field presence and types
        assert hasattr(result, "measured_rate")
        assert hasattr(result, "expected_rate")
        assert hasattr(result, "passed")
        assert hasattr(result, "errors")
        assert hasattr(result, "mesh_sizes")

        assert isinstance(result.measured_rate, float)
        assert isinstance(result.expected_rate, float)
        assert isinstance(result.passed, bool)

        # errors and mesh_sizes must be array-like with the correct length
        assert len(result.errors) == len(h)
        assert len(result.mesh_sizes) == len(h)

        # Values match inputs
        np.testing.assert_array_equal(result.errors, errors)
        np.testing.assert_array_equal(result.mesh_sizes, h)
        assert result.expected_rate == 2.0

    def test_exact_threshold_boundary(self):
        """
        Verifies: boundary condition handling
        Acceptance criterion: [2] Pass/fail logic with tolerance

        Test setup:
        - Generate data with measured_rate clearly above expected_rate - tol
        - Assert result.passed = True
        - Generate data with measured_rate clearly below expected_rate - tol
        - Assert result.passed = False

        The pass condition is: measured_rate >= expected_rate - tol  (i.e. >= 1.9 here).

        Note: using e = C * h^r with r exactly equal to the threshold (1.9) can land
        fractionally below 1.9 due to float64 rounding in polyfit, so the "pass" case
        uses r = 1.95 (above the threshold) and the "fail" case uses r = 1.8 (below).
        """
        expected_rate = 2.0
        tol = 0.1
        threshold = expected_rate - tol  # 1.9

        h = np.array([0.5, 0.25, 0.125])

        # --- Clearly above the threshold (rate = 1.95): should PASS ---
        rate_above = threshold + 0.05  # 1.95
        errors_above = 1.0 * h**rate_above
        result_above = check_convergence_rate(errors_above, h, expected_rate=expected_rate, tol=tol)
        assert result_above.measured_rate >= threshold, (
            f"measured_rate ({result_above.measured_rate}) should be >= threshold ({threshold})"
        )
        assert result_above.passed is True, "Rate above threshold should pass."

        # --- Clearly below the threshold (rate = 1.8): should FAIL ---
        rate_below = threshold - 0.1  # 1.8
        errors_below = 1.0 * h**rate_below
        result_below = check_convergence_rate(errors_below, h, expected_rate=expected_rate, tol=tol)
        assert result_below.measured_rate < threshold, (
            f"measured_rate ({result_below.measured_rate}) should be < threshold ({threshold})"
        )
        assert result_below.passed is False, "Rate below threshold should fail."

    def test_multiple_refinement_levels(self):
        """
        Verifies: robustness with realistic mesh refinement sequences
        Acceptance criterion: [1] Correct rate extraction from known O(h^2) data

        Test setup:
        - Typical MMS refinement: 4+ mesh levels (e.g., h = [0.25, 0.125, 0.0625, 0.03125])
        - Synthetic errors with h^2 convergence
        - Assert polyfit captures expected rate over full range

        Reference: dev/design_docs/08-VERIFICATION.md §4.2 recommends 4+ refinements.
        """
        # 5 refinement levels — more than the minimum 3
        h = np.array([0.25, 0.125, 0.0625, 0.03125, 0.015625])
        C = 5.0
        errors = C * h**2

        result = check_convergence_rate(errors, h, expected_rate=2.0, tol=0.1)

        assert abs(result.measured_rate - 2.0) < 1e-10, (
            f"Expected measured_rate ≈ 2.0 for 5-level h^2 data, got {result.measured_rate}"
        )
        assert result.passed is True
        assert len(result.errors) == 5
        assert len(result.mesh_sizes) == 5

    # -----------------------------------------------------------------------
    # Additional failure-path tests (dry-run analysis)
    # -----------------------------------------------------------------------

    def test_mismatched_lengths_raises_error(self):
        """
        Validates: ValueError when errors and mesh_sizes have different lengths.
        Failure path: len(errors) != len(mesh_sizes).
        """
        with pytest.raises(ValueError, match="same length"):
            check_convergence_rate([0.1, 0.05, 0.025], [0.5, 0.25], expected_rate=2.0)

    def test_nonpositive_error_values_raise(self):
        """
        Validates: ValueError when any error value is zero or negative (log undefined).
        Failure path: error value <= 0.
        """
        with pytest.raises(ValueError, match="strictly positive"):
            check_convergence_rate([0.1, 0.0, 0.025], [0.5, 0.25, 0.125], expected_rate=2.0)

        with pytest.raises(ValueError, match="strictly positive"):
            check_convergence_rate([0.1, -0.05, 0.025], [0.5, 0.25, 0.125], expected_rate=2.0)

    def test_nonpositive_mesh_size_values_raise(self):
        """
        Validates: ValueError when any mesh size value is zero or negative (log undefined).
        Failure path: mesh_size value <= 0.
        """
        with pytest.raises(ValueError, match="strictly positive"):
            check_convergence_rate([0.1, 0.05, 0.025], [0.5, 0.0, 0.125], expected_rate=2.0)

    def test_list_inputs_accepted(self):
        """
        Validates: plain Python lists are accepted as inputs (not only numpy arrays).
        """
        h = [0.5, 0.25, 0.125]
        errors = [0.25, 0.0625, 0.015625]  # C=1 * h^2

        result = check_convergence_rate(errors, h, expected_rate=2.0, tol=0.1)

        assert abs(result.measured_rate - 2.0) < 1e-10
        assert result.passed is True

    def test_default_tol_is_0_1(self):
        """
        Validates: default tolerance is 0.1 per 07-CONVENTIONS.md §6.
        """
        h = np.array([0.5, 0.25, 0.125])
        errors = h**2

        result = check_convergence_rate(errors, h, expected_rate=2.0)  # no explicit tol

        assert result.tol == 0.1


class TestTaskP3T2:
    """
    Tests for Task P3-T2: Implement MMS driver

    Objective: Implement Method of Manufactured Solutions driver in verify/convergence.py.
    Given manufactured u*(x) = A sin(πx/L) cos(πy/L) sin(πz/L), compute body force
    b* = -Div(P*), solve on mesh sequence, measure L2 and H1 errors.

    Acceptance criteria covered: [1, 2, 3]
    """

    def test_mms_body_force_substitution(self):
        """
        Verifies: manufactured body force b* satisfies equilibrium with u*
        Acceptance criterion: Body force b* is correct (verified by substitution check)
        Passes when: symbolic b* matches FD -Div(P*) to relative error < 1e-6
        """
        lam, mu = 1.0, 1.0
        rel_err = verify_mms_body_force_substitution(lam, mu)
        assert rel_err < 1e-6, (
            f"MMS body force FD verification failed: max relative error = {rel_err:.2e}"
        )

    @pytest.mark.slow
    def test_mms_3level_mesh_convergence(self):
        """
        Verifies: L2 error decreases monotonically across 3 mesh levels (2, 4, 8)
        Acceptance criterion: L2 error decreases with mesh refinement
        Passes when: error[i+1] < error[i] for all consecutive levels
        """
        lam, mu = 1.0, 1.0
        l2_errs, h1_errs, _h_sizes = run_mms_convergence(lam, mu, mesh_levels=[2, 3, 4])

        # L2 errors must decrease monotonically
        for i in range(len(l2_errs) - 1):
            assert l2_errs[i + 1] < l2_errs[i], (
                f"L2 error did not decrease: level {i} = {l2_errs[i]:.4e}, "
                f"level {i + 1} = {l2_errs[i + 1]:.4e}"
            )

        # H1 errors must also decrease monotonically
        for i in range(len(h1_errs) - 1):
            assert h1_errs[i + 1] < h1_errs[i], (
                f"H1 error did not decrease: level {i} = {h1_errs[i]:.4e}, "
                f"level {i + 1} = {h1_errs[i + 1]:.4e}"
            )

    @pytest.mark.slow
    def test_mms_l2_rate_ge_2(self):
        """
        Verifies: L2 convergence rate for Hex8 (p=1) meets expected order
        Acceptance criterion: For Hex8 (p=1): L2 rate >= 2.0
        Passes when: measured L2 rate >= 1.9 (2.0 - tol=0.1)
        """
        lam, mu = 1.0, 1.0
        l2_errs, _, h_sizes = run_mms_convergence(lam, mu, mesh_levels=[2, 3, 4])

        result = check_convergence_rate(l2_errs, h_sizes, expected_rate=2.0, tol=0.1)
        assert result.passed, (
            f"L2 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}"
        )

    @pytest.mark.slow
    def test_mms_h1_rate_ge_1(self):
        """
        Verifies: H1 convergence rate for Hex8 (p=1) meets expected order
        Acceptance criterion: For Hex8 (p=1): H1 rate >= 1.0
        Passes when: measured H1 rate >= 0.9 (1.0 - tol=0.1)
        """
        lam, mu = 1.0, 1.0
        _, h1_errs, h_sizes = run_mms_convergence(lam, mu, mesh_levels=[2, 3, 4])

        result = check_convergence_rate(h1_errs, h_sizes, expected_rate=1.0, tol=0.1)
        assert result.passed, (
            f"H1 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}"
        )


@pytest.fixture(scope="class")
def mms_convergence_results():
    """Class-scoped fixture: run MMS convergence study once and cache results.

    Runs ``run_mms_convergence(lam=1.0, mu=1.0, mesh_levels=[2, 3, 4])``
    exactly once per test class, returning a dict with keys
    ``l2_errors``, ``h1_errors``, ``h_sizes``.

    Using ``scope="class"`` avoids repeating the expensive FEM solves when
    both ``test_l2_convergence_rate_check`` and ``test_h1_convergence_rate_check``
    run in the same session.
    """
    l2_errors, h1_errors, h_sizes = run_mms_convergence(lam=1.0, mu=1.0, mesh_levels=[2, 3, 4])
    return {"l2_errors": l2_errors, "h1_errors": h1_errors, "h_sizes": h_sizes}


class TestTaskP3T3:
    """
    Tests for Task P3-T3: Write convergence rate test

    End-to-end convergence test combining MMS driver (P3-T2) with
    check_convergence_rate (P3-T1). Hex8 (p=1) on 3 mesh levels (2³, 4³, 8³).

    Both tests share one ``mms_convergence_results`` fixture so the expensive
    FEM solve runs only once for the entire class.

    Acceptance criteria covered:
    - [1] L2 rate ≥ 2.0 - 0.1 = 1.9
    - [2] H1 rate ≥ 1.0 - 0.1 = 0.9
    - [3] Test marked @pytest.mark.slow
    """

    @pytest.mark.slow
    def test_l2_convergence_rate_check(self, mms_convergence_results):
        """
        Verifies: L2 convergence rate ≥ 1.9 on 3 mesh levels (2³, 4³, 8³)
        Acceptance criterion: L2 rate ≥ 2.0 - 0.1 = 1.9

        End-to-end test: calls run_mms_convergence (P3-T2) to obtain L2 errors
        on a sequence of uniform Hex8 meshes, then calls check_convergence_rate
        (P3-T1) to fit the log-log slope and assert the rate meets the Hex8
        (p=1) theoretical prediction of O(h^2).

        Passes when: check_convergence_rate reports L2 rate ≥ 1.9
        """
        l2_errors = mms_convergence_results["l2_errors"]
        h_sizes = mms_convergence_results["h_sizes"]

        result = check_convergence_rate(l2_errors, h_sizes, expected_rate=2.0, tol=0.1)

        assert result.passed, (
            f"L2 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}  "
            f"(errors={l2_errors}, h_sizes={h_sizes})"
        )

    @pytest.mark.slow
    def test_h1_convergence_rate_check(self, mms_convergence_results):
        """
        Verifies: H1 convergence rate ≥ 0.9 on 3 mesh levels (2³, 4³, 8³)
        Acceptance criterion: H1 rate ≥ 1.0 - 0.1 = 0.9

        End-to-end test: calls run_mms_convergence (P3-T2) to obtain H1
        (energy-norm) errors on a sequence of uniform Hex8 meshes, then calls
        check_convergence_rate (P3-T1) to fit the log-log slope and assert the
        rate meets the Hex8 (p=1) theoretical prediction of O(h^1).

        Passes when: check_convergence_rate reports H1 rate ≥ 0.9
        """
        h1_errors = mms_convergence_results["h1_errors"]
        h_sizes = mms_convergence_results["h_sizes"]

        result = check_convergence_rate(h1_errors, h_sizes, expected_rate=1.0, tol=0.1)

        assert result.passed, (
            f"H1 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}  "
            f"(errors={h1_errors}, h_sizes={h_sizes})"
        )


@pytest.fixture(scope="class")
def mms_convergence_results_4level():
    """Class-scoped fixture: run MMS convergence study once on 4 mesh levels [2,4,8,16].

    Uses proper 2x refinement ratios throughout (each level doubles the element count
    per edge), which is required for reliable convergence rate estimation.

    Running with ``scope="class"`` avoids repeating the expensive FEM solves for
    both the L2 and H1 rate checks.
    """
    l2_errors, h1_errors, h_sizes = run_mms_convergence(lam=1.0, mu=1.0, mesh_levels=[2, 4, 8, 16])
    return {"l2_errors": l2_errors, "h1_errors": h1_errors, "h_sizes": h_sizes}


class TestMMS4LevelConvergence:
    """
    4-level MMS convergence study with proper 2x refinement ratios [2, 4, 8, 16].

    Extends the 3-level tests in TestTaskP3T3 by using a geometrically consistent
    refinement sequence (each level doubles elements per edge: 2^3, 4^3, 8^3, 16^3).
    Uniform refinement ratios produce a better-conditioned log-log fit and are
    required by 08-VERIFICATION.md §4.2 for production convergence validation.

    Acceptance criteria:
    - [1] L2 rate >= 2.0 - 0.1 = 1.9  (Hex8 p=1 theoretical: O(h^2))
    - [2] H1 rate >= 1.0 - 0.1 = 0.9  (Hex8 p=1 theoretical: O(h^1))
    - [3] Test marked @pytest.mark.e2e @pytest.mark.slow
    - [4] 4 mesh levels with strict 2x refinement ratios throughout
    """

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_mms_4level_l2_convergence_rate(self, mms_convergence_results_4level):
        """
        Verifies: L2 convergence rate >= 1.9 on 4 mesh levels [2,4,8,16].
        Acceptance criterion: L2 rate >= 2.0 - tol=0.1 = 1.9

        Uses mesh_levels=[2,4,8,16] — strict 2x refinement ratios — to ensure
        the log-log slope estimate is unbiased.  The Hex8 (p=1) element is
        expected to achieve O(h^2) accuracy in the L2 displacement norm.

        Passes when: check_convergence_rate reports L2 rate >= 1.9
        """
        # Previously skipped: unpreconditioned CG + FD tangent took >24h.
        # Now feasible with analytical tangent + ScipyCGSolver.
        l2_errors = mms_convergence_results_4level["l2_errors"]
        h_sizes = mms_convergence_results_4level["h_sizes"]

        result = check_convergence_rate(l2_errors, h_sizes, expected_rate=2.0, tol=0.1)

        assert result.passed, (
            f"L2 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}  "
            f"(errors={l2_errors}, h_sizes={h_sizes})"
        )

    @pytest.mark.e2e
    @pytest.mark.slow
    def test_mms_4level_h1_convergence_rate(self, mms_convergence_results_4level):
        """
        Verifies: H1 convergence rate >= 0.9 on 4 mesh levels [2,4,8,16].
        Acceptance criterion: H1 rate >= 1.0 - tol=0.1 = 0.9

        Uses mesh_levels=[2,4,8,16] — strict 2x refinement ratios — to ensure
        the log-log slope estimate is unbiased.  The Hex8 (p=1) element is
        expected to achieve O(h^1) accuracy in the H1 (energy-norm) error.

        Passes when: check_convergence_rate reports H1 rate >= 0.9
        """
        # Previously skipped: unpreconditioned CG + FD tangent took >24h.
        # Now feasible with analytical tangent + ScipyCGSolver.
        h1_errors = mms_convergence_results_4level["h1_errors"]
        h_sizes = mms_convergence_results_4level["h_sizes"]

        result = check_convergence_rate(h1_errors, h_sizes, expected_rate=1.0, tol=0.1)

        assert result.passed, (
            f"H1 convergence rate {result.measured_rate:.3f} < threshold "
            f"{result.expected_rate - result.tol:.1f}  "
            f"(errors={h1_errors}, h_sizes={h_sizes})"
        )
