"""Tests for Task P7-2: Critical time step computation (Plan B Phase 7).

Covers critical time step computation for the central-difference integrator via
the Courant condition: dt_crit = L_min / c_d, where L_min is the minimum element
characteristic length and c_d is the dilatational wave speed.

This test suite validates:
1. Analytical correctness on regular meshes (unit-cube Hex8).
2. Safety on irregular meshes (dt below per-element minimum).
3. Correct application of the safety factor (default 0.9).

Acceptance Criteria (ACs):
- AC 1: Regular unit-cube mesh: computed dt matches L/c_d within 1e-8.
- AC 2: Irregular mesh: dt is below the min-element limit (safety check).
- AC 3: Safety factor applied correctly (default 0.9).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mechdsl.ir.mechanics_ir import ElementType
from mechdsl.solver.critical_timestep import critical_timestep

# ── Mesh helpers ─────────────────────────────────────────────────────────────


def _unit_cube_hex8() -> tuple[np.ndarray, np.ndarray]:
    """Single 1×1×1 Hex8 element (8 nodes, 1 element).

    Node ordering matches the MFEM/VTK convention used in hex8_tables.py:
        0:(-,-,-), 1:(+,-,-), 2:(+,+,-), 3:(-,+,-)
        4:(-,-,+), 5:(+,-,+), 6:(+,+,+), 7:(-,+,+)
    mapped from reference [-1,1]^3 to [0,1]^3.
    """
    coords = np.array(
        [
            [0.0, 0.0, 0.0],  # node 0
            [1.0, 0.0, 0.0],  # node 1
            [1.0, 1.0, 0.0],  # node 2
            [0.0, 1.0, 0.0],  # node 3
            [0.0, 0.0, 1.0],  # node 4
            [1.0, 0.0, 1.0],  # node 5
            [1.0, 1.0, 1.0],  # node 6
            [0.0, 1.0, 1.0],  # node 7
        ],
        dtype=np.float64,
    )
    conn = np.array([[0, 1, 2, 3, 4, 5, 6, 7]], dtype=np.int64)
    return coords, conn


def _two_element_hex8_stretched() -> tuple[np.ndarray, np.ndarray]:
    """Two-element Hex8 mesh where element 0 is deliberately thin (dx=0.1).

    Element 0: x in [0, 0.1], y in [0, 1], z in [0, 1]  → V = 0.1, L = 0.1^(1/3)
    Element 1: x in [0.1, 1.1], y in [0, 1], z in [0, 1] → V = 1.0, L = 1.0

    Nodes (12 total):
      Layer x=0.0:  0..3
      Layer x=0.1:  4..7
      Layer x=1.1:  8..11
    """
    coords = np.array(
        [
            # x=0.0 face (shared by elem 0, bottom)
            [0.0, 0.0, 0.0],  # 0
            [0.0, 1.0, 0.0],  # 1
            [0.0, 1.0, 1.0],  # 2
            [0.0, 0.0, 1.0],  # 3
            # x=0.1 face (shared between elem 0 and elem 1)
            [0.1, 0.0, 0.0],  # 4
            [0.1, 1.0, 0.0],  # 5
            [0.1, 1.0, 1.0],  # 6
            [0.1, 0.0, 1.0],  # 7
            # x=1.1 face (elem 1 far side)
            [1.1, 0.0, 0.0],  # 8
            [1.1, 1.0, 0.0],  # 9
            [1.1, 1.0, 1.0],  # 10
            [1.1, 0.0, 1.0],  # 11
        ],
        dtype=np.float64,
    )
    # Connectivity in MFEM node order: bottom-face CCW then top-face CCW
    conn = np.array(
        [
            [0, 4, 5, 1, 3, 7, 6, 2],  # elem 0: thin slab dx=0.1
            [4, 8, 9, 5, 7, 11, 10, 6],  # elem 1: unit slab dx=1.0
        ],
        dtype=np.int64,
    )
    return coords, conn


class TestTaskP7_2:
    """Tests for Task P7-2: Critical time step computation.

    This class covers all three acceptance criteria for computing the critical
    time step via the Courant condition for explicit central-difference time
    integration.
    """

    # ── AC 1: Unit-cube Hex8 analytical correctness ────────────────────────

    @pytest.mark.unit
    def test_unit_cube_hex8_dt_matches_analytical(self) -> None:
        """Verify analytical dt on a regular unit-cube Hex8 mesh.

        For a unit-cube mesh (L = 1.0, V = 1.0) with lam=mu=rho=1.0:
            c_d = sqrt((1 + 2*1) / 1) = sqrt(3)
            L_e = V^(1/3) = 1.0^(1/3) = 1.0
            dt  = safety * L_e / c_d = 0.9 * 1.0 / sqrt(3)

        Acceptance Criterion: AC 1
        Regular unit-cube mesh: computed dt matches L/c_d within 1e-8.
        """
        coords, conn = _unit_cube_hex8()
        lam = 1.0
        mu = 1.0
        rho = 1.0
        safety = 0.9

        c_d = math.sqrt((lam + 2.0 * mu) / rho)
        expected = safety * 1.0 / c_d

        dt = critical_timestep(coords, conn, lam, mu, rho, ElementType.HEX8, safety=safety)

        assert abs(dt - expected) < 1e-8, (
            f"Expected dt={expected:.15f}, got dt={dt:.15f}, diff={abs(dt - expected):.2e}"
        )

    # ── AC 2: Irregular mesh safety check ────────────────────────────────────

    @pytest.mark.unit
    def test_irregular_mesh_dt_below_element_min(self) -> None:
        """Verify dt is bounded by the smallest element on an irregular mesh.

        The two-element mesh has:
          - elem 0: thin slab dx=0.1, dy=dz=1 → V=0.1, L=0.1^(1/3) ≈ 0.464
          - elem 1: near-unit slab dx=1.0, dy=dz=1 → V=1.0, L=1.0

        The global dt must be limited by the small element (elem 0), so the
        returned dt must satisfy dt ≤ safety * L_min / c_d.

        Acceptance Criterion: AC 2
        Irregular mesh: dt is below the min-element limit (safety check).
        """
        coords, conn = _two_element_hex8_stretched()
        lam = 1.0
        mu = 1.0
        rho = 1.0
        safety = 0.9

        c_d = math.sqrt((lam + 2.0 * mu) / rho)

        # Characteristic length of the thin element (elem 0): V=0.1
        L_min = (0.1) ** (1.0 / 3.0)
        dt_upper = safety * L_min / c_d

        dt = critical_timestep(coords, conn, lam, mu, rho, ElementType.HEX8, safety=safety)

        assert dt > 0.0, f"dt must be positive; got {dt}"

        # dt must be controlled by the smallest element (within float tolerance)
        assert dt <= dt_upper + 1e-10, (
            f"Expected dt ≤ {dt_upper:.10f} (safety * L_min / c_d), but got dt={dt:.10f}"
        )

        # Also confirm dt is strictly less than the large-element dt
        L_large = 1.0 ** (1.0 / 3.0)
        dt_large = safety * L_large / c_d
        assert dt < dt_large, f"dt={dt:.10f} should be less than large-element dt={dt_large:.10f}"

    # ── AC 3: Safety factor application ──────────────────────────────────────

    @pytest.mark.unit
    def test_safety_factor_applied(self) -> None:
        """Verify the safety factor (default 0.9) is applied correctly.

        The critical time step should be scaled by a configurable safety factor
        (default 0.9) to add margin and ensure numerical stability:

            dt_safe = 0.9 * (L_min / c_d)

        We verify:
        1. dt(safety=0.5) == 0.5 * dt(safety=1.0)  (half the raw dt)
        2. The default safety argument is 0.9.

        Acceptance Criterion: AC 3
        Safety factor applied correctly (default 0.9).
        """
        import inspect

        coords, conn = _unit_cube_hex8()
        lam = 1.0
        mu = 1.0
        rho = 1.0

        dt_full = critical_timestep(coords, conn, lam, mu, rho, ElementType.HEX8, safety=1.0)
        dt_half = critical_timestep(coords, conn, lam, mu, rho, ElementType.HEX8, safety=0.5)

        # Half safety factor → half the dt
        assert abs(dt_half - 0.5 * dt_full) < 1e-14, (
            f"dt(safety=0.5)={dt_half:.15f} should equal 0.5 * dt(safety=1.0)={0.5 * dt_full:.15f}"
        )

        # Verify default safety is 0.9
        sig = inspect.signature(critical_timestep)
        default_safety = sig.parameters["safety"].default
        assert default_safety == 0.9, f"Default safety should be 0.9, got {default_safety}"

        # Cross-check: dt_default == 0.9 * dt_full
        dt_default = critical_timestep(coords, conn, lam, mu, rho, ElementType.HEX8)
        assert abs(dt_default - 0.9 * dt_full) < 1e-14, (
            f"dt(default)={dt_default:.15f} should equal 0.9 * dt(safety=1.0)={0.9 * dt_full:.15f}"
        )
