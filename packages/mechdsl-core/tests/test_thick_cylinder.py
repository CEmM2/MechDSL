"""Task P10-4: Thick-walled internally-pressurised cylinder benchmark.

Reference: Lame closed-form solution for an internally-pressurised thick
cylinder under plane-strain conditions (Timoshenko & Goodier, section 28).

Geometry: r_inner=1, r_outer=2, height=0.1 (plane-strain with a single
element through thickness and both z-faces clamped in u_z).

Mesh: quarter-cylinder (theta in [0, pi/2]) with symmetry BCs on the radial
symmetry planes, nr=24 radial x ntheta=20 angular elements and a mild
radial bias (q=1.05) clustering nodes toward the inner wall where the
hoop-stress gradient peaks.

Acceptance criteria (dev/tasks/PLAN-B/json/P10-4.json):
  1. Radial displacement within 2% of Lame at 5 sample radii.
  2. Hoop stress within 3% of Lame.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.verify.benchmarks import run_thick_cylinder_benchmark
from tests.ref.ref_hex8_elastic import solve_elastic

# Reference problem parameters
_R_INNER = 1.0
_R_OUTER = 2.0
_HEIGHT = 0.1
_PRESSURE = 10.0  # MPa
_E = 200e3  # MPa
_NU = 0.3
_SAMPLE_RADII = np.array([1.1, 1.25, 1.5, 1.75, 1.9])

# Mesh refinement (converged in preliminary sweep: 24x20x1 w/ radial bias 1.05
# gives max u_r rel-err 0.81% and max sigma_theta_theta rel-err 1.75%).
_NR = 24
_NTHETA = 20
_NZ = 1
_RADIAL_BIAS = 1.05


@pytest.fixture(scope="module")
def thick_cylinder_result():
    """Run the benchmark once and share the result across both acceptance tests."""
    return run_thick_cylinder_benchmark(
        r_inner=_R_INNER,
        r_outer=_R_OUTER,
        height=_HEIGHT,
        nr=_NR,
        ntheta=_NTHETA,
        nz=_NZ,
        pressure=_PRESSURE,
        E=_E,
        nu=_NU,
        solve_elastic=solve_elastic,
        sample_radii=_SAMPLE_RADII,
        radial_bias=_RADIAL_BIAS,
    )


class TestTaskP10_4:
    """Tests for Task P10-4: Thick cylinder benchmark (TL x SVK x Hex8)."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_thick_cylinder_radial_displacement_matches_lame(self, thick_cylinder_result) -> None:
        """Radial displacement within 2% of Lame at 5 sample radii."""
        rel_err = thick_cylinder_result.extras["u_r_rel_err"]
        u_r_fem = thick_cylinder_result.extras["u_r_fem"]
        u_r_lame = thick_cylinder_result.extras["u_r_lame"]

        # FEM must be outward (positive) under internal pressure - guards
        # against the pressure-loader sign being silently flipped in future
        # edits.
        assert np.all(u_r_fem > 0), (
            f"Expected outward (positive) radial displacement under internal "
            f"pressure, got u_r_fem={u_r_fem}"
        )
        assert np.all(u_r_lame > 0), f"Lame reference must be positive, got {u_r_lame}"

        max_err = float(rel_err.max())
        assert max_err < 0.02, (
            f"Radial displacement rel-err exceeds 2% tolerance: "
            f"max={max_err:.4%}, per-radius={rel_err}"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_thick_cylinder_hoop_stress_matches_lame(self, thick_cylinder_result) -> None:
        """Hoop stress within 3% of Lame at 5 sample radii."""
        rel_err = thick_cylinder_result.extras["sigma_tt_rel_err"]
        sigma_tt_fem = thick_cylinder_result.extras["sigma_tt_fem"]
        sigma_tt_lame = thick_cylinder_result.extras["sigma_tt_lame"]

        # Hoop stress is tensile under internal pressure.
        assert np.all(sigma_tt_fem > 0), (
            f"Expected tensile hoop stress under internal pressure, got sigma_tt_fem={sigma_tt_fem}"
        )
        assert np.all(sigma_tt_lame > 0), f"Lame hoop stress must be tensile, got {sigma_tt_lame}"

        max_err = float(rel_err.max())
        assert max_err < 0.03, (
            f"Hoop stress rel-err exceeds 3% tolerance: max={max_err:.4%}, per-radius={rel_err}"
        )
