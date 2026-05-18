"""Tests for Phase 10 prerequisite J2 benchmark solver helpers."""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
from mechdsl.verify.benchmarks._j2_solver import (
    J2BenchmarkHistory,
    assemble_internal_force_j2,
    assert_monotonic_plastic_history,
    element_internal_force_j2,
)
from mechdsl.verify.benchmarks._meshes import structured_block_mesh
from tests.ref.ref_hex8_plastic import element_internal_force_plastic

MAT = J2PowerLawMaterial(E=200.0e3, nu=0.3, sigma_y0=250.0, K=500.0, n=1.0)


def _constant_strain_displacement(coords: np.ndarray, eps_xx: float) -> np.ndarray:
    u = np.zeros_like(coords)
    u[:, 0] = eps_xx * coords[:, 0]
    return u


class TestTaskP2_1:
    """Tests for Task P2-1: TL J2 benchmark solver baseline."""

    @pytest.mark.integration
    def test_tl_hex8_element_force_matches_existing_reference(self) -> None:
        """Verifies TL Hex8 element force agrees with the handwritten reference."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)
        nodes = mesh.connectivity[0]
        X_elem = mesh.coordinates[nodes]
        u_elem = _constant_strain_displacement(X_elem, eps_xx=0.01)
        alpha_old = np.zeros(8, dtype=np.float64)
        element = ElementFactory.create("hex8")

        f_new, alpha_new = element_internal_force_j2(
            u_elem,
            X_elem,
            MAT,
            alpha_old,
            element=element,
        )
        f_ref, alpha_ref = element_internal_force_plastic(
            u_elem,
            X_elem,
            MAT,
            alpha_old,
        )

        np.testing.assert_allclose(f_new, f_ref, rtol=1e-12, atol=1e-9)
        np.testing.assert_allclose(alpha_new, alpha_ref, rtol=1e-12, atol=1e-12)

    @pytest.mark.integration
    def test_history_commit_and_rollback_are_deterministic(self) -> None:
        """Verifies benchmark history supports Newton-style commit/rollback."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)
        history = J2BenchmarkHistory.zeros_for_mesh(mesh)

        history.alpha_current[:] = 0.25
        history.commit()
        history.alpha_current[:] = 0.5
        history.rollback()

        np.testing.assert_allclose(history.alpha_current, 0.25)
        np.testing.assert_allclose(history.alpha_old, 0.25)


class TestTaskP2_2:
    """Tests for Task P2-2: UL and Tet10 J2 benchmark solver extension."""

    @pytest.mark.integration
    def test_updated_lagrangian_rigid_rotation_is_objective(self) -> None:
        """Verifies a rigid rotation produces zero stress and no plastic history."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)
        theta = np.deg2rad(25.0)
        R = np.array(
            [
                [np.cos(theta), -np.sin(theta), 0.0],
                [np.sin(theta), np.cos(theta), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        u = mesh.coordinates @ R.T - mesh.coordinates
        history = J2BenchmarkHistory.zeros_for_mesh(mesh)

        f_int = assemble_internal_force_j2(
            mesh,
            u,
            MAT,
            history,
            formulation="updated_lagrangian",
        )

        np.testing.assert_allclose(f_int, 0.0, atol=1e-8)
        np.testing.assert_allclose(history.alpha_current, 0.0, atol=1e-12)

    @pytest.mark.integration
    def test_plastic_history_increment_is_monotonic(self) -> None:
        """Verifies equivalent plastic strain does not decrease under loading."""
        mesh = structured_block_mesh("hex8", nx=1, ny=1, nz=1)
        u = _constant_strain_displacement(mesh.coordinates, eps_xx=0.01)
        history = J2BenchmarkHistory.zeros_for_mesh(mesh)

        _ = assemble_internal_force_j2(mesh, u, MAT, history)

        assert_monotonic_plastic_history(history)
        assert np.any(history.alpha_increment > 0.0)

    @pytest.mark.integration
    def test_tet10_j2_state_update_is_finite(self) -> None:
        """Verifies Tet10 J2 path runs with finite force and history values."""
        mesh = structured_block_mesh("tet10", nx=1, ny=1, nz=1)
        u = _constant_strain_displacement(mesh.coordinates, eps_xx=0.01)
        history = J2BenchmarkHistory.zeros_for_mesh(mesh)

        f_int = assemble_internal_force_j2(mesh, u, MAT, history)

        assert f_int.shape == mesh.coordinates.shape
        assert history.alpha_current.shape == (mesh.n_elements, 4)
        assert np.all(np.isfinite(f_int))
        assert np.all(np.isfinite(history.alpha_current))
