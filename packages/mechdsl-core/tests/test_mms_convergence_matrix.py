"""Task P10-1: active MMS convergence matrix tests."""

from __future__ import annotations

import pytest

from mechdsl.verify.convergence import run_mms_convergence
from mechdsl.verify.mms_matrix import (
    MMSMatrixCase,
    MMSMatrixResult,
    default_mms_matrix_cases,
    run_mms_convergence_matrix,
)


@pytest.fixture(scope="module")
def mms_matrix_result() -> MMSMatrixResult:
    """Run the default Phase 10 MMS matrix once for shared assertions."""

    return run_mms_convergence_matrix()


class TestTaskP10_1:
    """Tests for Task P10-1: generalized MMS convergence matrix."""

    @pytest.mark.regression
    def test_existing_hex8_mms_api_contract_is_unchanged(self) -> None:
        """Legacy run_mms_convergence still returns the original three lists."""
        l2_errors, h1_errors, h_sizes = run_mms_convergence(
            lam=1.0,
            mu=1.0,
            mesh_levels=[2, 3, 4],
        )

        assert isinstance(l2_errors, list)
        assert isinstance(h1_errors, list)
        assert isinstance(h_sizes, list)
        assert len(l2_errors) == len(h1_errors) == len(h_sizes) == 3
        assert all(err > 0.0 for err in l2_errors)
        assert all(err > 0.0 for err in h1_errors)

    @pytest.mark.regression
    def test_new_matrix_api_import_and_smoke_run(self) -> None:
        """The additive MMS matrix API returns structured convergence results."""
        result = run_mms_convergence_matrix(
            cases=[
                MMSMatrixCase("hex8", "svk", expected_l2_rate=2.0, expected_h1_rate=1.0),
                MMSMatrixCase("tet10", "svk", expected_l2_rate=3.0, expected_h1_rate=2.0),
                MMSMatrixCase("hex20", "svk", expected_l2_rate=3.0, expected_h1_rate=2.0),
            ],
        )

        assert isinstance(result, MMSMatrixResult)
        assert result.passed
        assert len(result.entries) == 3
        for entry in result.entries:
            assert entry.passed
            assert len(entry.mesh_sizes) == 3
            assert len(entry.l2_errors) == 3
            assert len(entry.h1_errors) == 3
            assert entry.diagnostics["case_id"] == entry.case.id
            assert "l2_measured_rate" in entry.diagnostics
            assert "h1_measured_rate" in entry.diagnostics

    @pytest.mark.regression
    @pytest.mark.parametrize("case", default_mms_matrix_cases())
    def test_planned_matrix_entries_are_active(
        self, case: MMSMatrixCase, mms_matrix_result: MMSMatrixResult
    ) -> None:
        """Planned element/material entries pass their structured convergence checks."""
        entry = mms_matrix_result.by_id()[case.id]

        assert entry.case == case
        assert entry.passed
        assert entry.l2_check.measured_rate >= case.expected_l2_rate - entry.l2_check.tol
        assert entry.h1_check.measured_rate >= case.expected_h1_rate - entry.h1_check.tol

    @pytest.mark.regression
    def test_dissipative_material_policy_is_explicit(
        self, mms_matrix_result: MMSMatrixResult
    ) -> None:
        """Dissipative entries are explicitly marked as elastic-regime MMS checks."""
        entries = [
            entry
            for entry in mms_matrix_result.entries
            if entry.case.material in {"j2_power_law", "perzyna", "lemaitre_d0"}
        ]

        assert entries
        for entry in entries:
            assert entry.case.policy == "elastic_regime_interpolation"
            assert "elastic-regime MMS policy" in str(entry.diagnostics["policy_note"])
            assert entry.diagnostics["material"] == entry.case.material
