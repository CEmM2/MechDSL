"""Task P10-5: Plate-with-hole benchmark (K_t vs Kirsch analytical solution).

Reference: Kirsch analytical stress-concentration factor K_t = 3.0 for an
infinite plate with a circular hole under uniaxial tension.

Acceptance criteria (from dev/tasks/PLAN-B/json/P10-5.json):
  1. Hex20 K_t within 5% of 3.0.
  2. Hex8 K_t within 15% of 3.0 (documented expected lower accuracy —
     context summary Phase 10 allowed-deviation).

"""

from __future__ import annotations

import pytest

from mechdsl.verify.benchmarks import PlateWithHoleParameters, run_plate_with_hole_benchmark


@pytest.fixture(scope="module")
def plate_with_hole_hex20_result():
    """Run the Hex20 Kirsch benchmark once per module."""
    return run_plate_with_hole_benchmark(params=PlateWithHoleParameters(element_type="hex20"))


@pytest.fixture(scope="module")
def plate_with_hole_hex8_result():
    """Run the Hex8 Kirsch benchmark once per module."""
    return run_plate_with_hole_benchmark(params=PlateWithHoleParameters(element_type="hex8"))


class TestTaskP10_5:
    """Tests for Task P10-5: Plate-with-hole benchmark (TL × SVK × Hex8/Hex20)."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_plate_with_hole_hex20_kt_within_5pct(self, plate_with_hole_hex20_result) -> None:
        """Hex20 stress-concentration factor K_t within 5% of 3.0 (Kirsch)."""
        k_t = plate_with_hole_hex20_result.extras["k_t"]
        rel_error = plate_with_hole_hex20_result.extras["relative_error"]

        assert k_t > 0.0, f"Expected positive stress concentration factor, got {k_t:.6f}"
        assert rel_error < 0.05, (
            f"Hex20 K_t = {k_t:.6f} differs from Kirsch 3.0 by {rel_error:.2%} (> 5%)"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_plate_with_hole_hex8_kt_within_15pct(self, plate_with_hole_hex8_result) -> None:
        """Hex8 K_t within 15% of 3.0 — coarse linear element, allowed deviation."""
        k_t = plate_with_hole_hex8_result.extras["k_t"]
        rel_error = plate_with_hole_hex8_result.extras["relative_error"]

        assert k_t > 0.0, f"Expected positive stress concentration factor, got {k_t:.6f}"
        assert rel_error < 0.15, (
            f"Hex8 K_t = {k_t:.6f} differs from Kirsch 3.0 by {rel_error:.2%} (> 15%)"
        )
