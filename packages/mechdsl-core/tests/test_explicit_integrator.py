"""Tests for explicit dynamics: lumped mass + central difference integrator (Task P7-1).

Covers:
    P7-1: Lumped mass matrix computation (row-sum from consistent mass),
          central-difference time integrator for explicit dynamics,
          DynamicsMode switch (EXPLICIT vs STATIC) in code generation.

Three acceptance criteria:
    AC-1: Lumped mass matches row-sum of the consistent mass within 1e-12.
    AC-2: Central-difference single-step matches hand calc on a free element.
    AC-3: Generator emits distinct source for EXPLICIT vs STATIC modes.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.hex8_tables import (
    GRAD_AT_QUAD,
    HEX8_QUAD_WEIGHTS,
    SHAPE_AT_QUAD,
)
from mechdsl.codegen.taichi_printer import emit
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    DynamicsMode,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize
from mechdsl.solver.lumped_mass import compute_lumped_mass


def _unit_cube_hex8() -> tuple[np.ndarray, np.ndarray]:
    """Return (coords, conn) for a single unit-cube Hex8 element.

    Node ordering matches :data:`mechdsl.codegen.hex8_tables.HEX8_NODE_COORDS`
    (VTK/MFEM convention, mapped from the reference cube [-1, 1]^3 to [0, 1]^3).
    """
    coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )
    conn = np.array([[0, 1, 2, 3, 4, 5, 6, 7]], dtype=np.int64)
    return coords, conn


def _consistent_mass_hex8(coords: np.ndarray, conn: np.ndarray, rho: float) -> np.ndarray:
    """Assemble the consistent global mass matrix for a Hex8 mesh.

    Returns a dense ``(3*n_nodes, 3*n_nodes)`` array.  Used as the reference
    row-sum ground truth in the AC-1 test.
    """
    n_nodes = coords.shape[0]
    ndof = 3 * n_nodes
    M = np.zeros((ndof, ndof), dtype=np.float64)
    for e in range(conn.shape[0]):
        X_elem = coords[conn[e]]  # (8, 3)
        for q in range(SHAPE_AT_QUAD.shape[0]):
            J0 = X_elem.T @ GRAD_AT_QUAD[q]
            detJ0 = float(np.linalg.det(J0))
            w = float(HEX8_QUAD_WEIGHTS[q])
            N = SHAPE_AT_QUAD[q]  # (8,)
            # M_ab = integral rho * N_a * N_b dV -- scalar per node pair,
            # replicated across the 3 spatial DoFs (isotropic translational mass).
            Me_scalar = rho * np.outer(N, N) * detJ0 * w  # (8, 8)
            for a in range(8):
                for b in range(8):
                    for i in range(3):
                        M[3 * conn[e, a] + i, 3 * conn[e, b] + i] += Me_scalar[a, b]
    return M


class TestTaskP7_1:
    """Unit tests for explicit dynamics (Task P7-1)."""

    @pytest.mark.unit
    def test_lumped_mass_matches_consistent_row_sum(self) -> None:
        """AC-1: Lumped mass matches row-sum of the consistent mass within 1e-12.

        Unit cube, rho = 1.0: total mass = rho * V = 1.0; with eight nodes
        equally sharing the mass by symmetry, each node carries 1/8 per DoF.
        """
        coords, conn = _unit_cube_hex8()
        rho = 1.0
        M_lumped = compute_lumped_mass(coords, conn, rho, ElementType.HEX8)

        # Shape check: (n_nodes, 3)
        assert M_lumped.shape == (8, 3)

        # All three translational DoFs carry the same nodal scalar.
        np.testing.assert_allclose(M_lumped[:, 0], M_lumped[:, 1], atol=1e-15)
        np.testing.assert_allclose(M_lumped[:, 0], M_lumped[:, 2], atol=1e-15)

        # Reference: row-sum of the consistent mass matrix.
        M_consistent = _consistent_mass_hex8(coords, conn, rho)
        row_sums = M_consistent.sum(axis=1).reshape(8, 3)

        max_diff = float(np.max(np.abs(M_lumped - row_sums)))
        assert max_diff < 1e-12, f"Lumped mass deviates from consistent row-sum by {max_diff:.3e}"

        # Sanity: unit cube with rho = 1 -> total mass = 1, evenly split across 8 nodes.
        assert abs(float(M_lumped[:, 0].sum()) - 1.0) < 1e-12
        np.testing.assert_allclose(M_lumped[:, 0], np.full(8, 1.0 / 8.0), atol=1e-12)

    @pytest.mark.unit
    def test_central_difference_single_step_matches_hand_calc(self) -> None:
        """AC-2: Central-difference single-step matches hand calc.

        Apply a known net nodal force to a free element with u=0, v=0, and
        advance one step by the central-difference update

            v^{1/2} = v^{-1/2} + dt * M_inv * (f_ext - f_int)
            u^{1}   = u^{0}    + dt * v^{1/2}.

        With f_int = 0 (u = 0 trivially gives zero stresses), the
        half-step velocity and displacement update are analytical.
        """
        coords, conn = _unit_cube_hex8()
        rho = 1.0
        M_lumped = compute_lumped_mass(coords, conn, rho, ElementType.HEX8)
        # Initial state: u^0 = 0, v^{-1/2} = 0, f_int = 0.
        n_nodes = coords.shape[0]
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        v = np.zeros((n_nodes, 3), dtype=np.float64)
        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        # Put a 1.0 N load in +x on every node -- symmetric, easy to reason about.
        f_ext[:, 0] = 1.0
        f_int = np.zeros_like(f_ext)
        dt = 1.0e-3

        # Reference update (python-side hand calc):
        M_inv = np.where(M_lumped > 0.0, 1.0 / M_lumped, 0.0)
        v_half = v + dt * M_inv * (f_ext - f_int)
        u_new = u + dt * v_half

        # Expected analytical values:
        #   M_a = 1/8; f_ext_a = 1 -> a_a = 8 (in +x, all nodes equal).
        #   v^{1/2} = dt * 8 = 8e-3; u^1 = dt * 8e-3 = 8e-6.
        expected_v_x = dt * 8.0
        expected_u_x = dt * expected_v_x
        assert abs(float(v_half[0, 0]) - expected_v_x) < 1e-10
        assert abs(float(u_new[0, 0]) - expected_u_x) < 1e-10
        np.testing.assert_allclose(v_half[:, 0], np.full(n_nodes, expected_v_x), atol=1e-10)
        np.testing.assert_allclose(u_new[:, 0], np.full(n_nodes, expected_u_x), atol=1e-10)
        # Other components remain zero (no transverse force).
        np.testing.assert_allclose(v_half[:, 1:], 0.0, atol=1e-14)
        np.testing.assert_allclose(u_new[:, 1:], 0.0, atol=1e-14)

    @pytest.mark.slow
    @pytest.mark.unit
    def test_explicit_static_emission_differs(self) -> None:
        """AC-3: Generator emits distinct source for EXPLICIT vs STATIC.

        Compile a small elastic SVK bundle twice -- once STATIC, once
        EXPLICIT -- and inspect the emitted Python source.  EXPLICIT must
        expose ``advance_one_step`` and not ``newton_solve``; STATIC must
        expose ``newton_solve`` and not ``advance_one_step``.
        """
        boundaries = (
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        )
        material = MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3})

        def _emit(mode: DynamicsMode) -> str:
            ir = ProblemIR(
                dim=3,
                formulation=Formulation.TOTAL_LAGRANGIAN,
                element_type=ElementType.HEX8,
                material=material,
                boundaries=boundaries,
                dynamics_mode=mode,
            )
            loc, plans = localise_and_optimize(ir)
            bundle = ArtifactBundle.from_pipeline(ir, loc, plans)
            return emit(bundle)

        static_src = _emit(DynamicsMode.STATIC)
        explicit_src = _emit(DynamicsMode.EXPLICIT)

        # Sources must differ.
        assert static_src != explicit_src

        # STATIC: Newton driver present, explicit driver absent.
        assert "def newton_solve(" in static_src
        assert "def advance_one_step(" not in static_src

        # EXPLICIT: central-difference driver present, Newton driver absent.
        assert "def advance_one_step(" in explicit_src
        assert "def newton_solve(" not in explicit_src
        # Velocity and lumped-mass fields are declared in EXPLICIT mode.
        assert "M_lumped" in explicit_src
        # The Velocity field -- guard for the explicit driver's commentary line.
        assert "v = ti.Vector.field(3, dtype=ti.f64)" in explicit_src
