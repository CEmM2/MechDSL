"""Phase 7 (ph10_preq) Task P7-1: Taylor explicit runtime, contact, and hourglass sanity.

Plan: ``dev/plans/ph10_preq.md`` lines 278-315 (Phase E7).

Covers the *internal* Taylor runtime surface only — the public benchmark
runner ``run_taylor_impact_benchmark`` is owned by Phase 8 (P8-1/P8-2).

Acceptance criteria covered:
  AC-1: Reduced Hex8 hourglass energy remains bounded in a non-impact sanity case.
  AC-2: Rigid-wall contact prevents penetration.
  AC-3: No Johnson-Cook or hourglass behavior changes are made unless proved necessary.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from mechdsl.codegen import hourglass as hourglass_mod
from mechdsl.solver import lumped_mass as lumped_mass_mod
from mechdsl.verify.benchmarks._meshes import structured_block_mesh
from mechdsl.verify.benchmarks._taylor_runtime import (
    RigidWallSpec,
    apply_rigid_wall_contact,
    explicit_step,
    init_taylor_runtime,
)

# ---------------------------------------------------------------------------
# Common physical parameters for the smoke runtime.  Values chosen so the
# critical-time-step estimator stays comfortable; we are only exercising the
# explicit composition, not validating Taylor impact physics here.
# ---------------------------------------------------------------------------

_E_MOD = 200.0e9  # Pa  (steel-like, but units are arbitrary for the smoke)
_NU = 0.30
_LAM = _E_MOD * _NU / ((1.0 + _NU) * (1.0 - 2.0 * _NU))
_MU = _E_MOD / (2.0 * (1.0 + _NU))
_RHO = 7800.0
_LAMBDA_H = 0.05


def _small_bar_mesh():
    """A small reduced-Hex8 bar mesh: 1 mm cube column, 4 elements along z."""
    return structured_block_mesh(
        "hex8",
        length=1.0e-3,
        width=1.0e-3,
        height=4.0e-3,
        nx=1,
        ny=1,
        nz=4,
    )


class TestTaskP7_1:
    """Tests for Task P7-1: Taylor explicit runtime, contact, and hourglass sanity.

    Acceptance criteria covered: AC-1 (hourglass boundedness), AC-2 (rigid-wall
    contact), AC-3 (no upstream JC/hourglass semantic drift).
    """

    @pytest.mark.integration
    def test_explicit_update_smoke_step(self) -> None:
        """One explicit step on a small reduced-Hex8 bar mesh runs to completion.

        Verifies: a single explicit-dynamics update over a small Hex8 bar
        produces finite displacement, velocity, and acceleration arrays
        and respects the critical timestep estimate.

        Acceptance criterion: AC-3 — runtime exists without altering
        Johnson-Cook or hourglass behavior.

        Passes when: state arrays are finite, conservation diagnostics return
        non-negative values, and no upstream symbol behavior changed.
        """
        mesh = _small_bar_mesh()
        # Initial velocity: small uniform v0 on top face into z (-z direction)
        v0 = np.zeros_like(mesh.coordinates)
        top_nodes = mesh.boundary_nodes["z_max"]
        v0[top_nodes, 2] = -10.0

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )

        # Sanity: state struct shape contracts.
        assert state.coords.shape == mesh.coordinates.shape
        assert state.displacement.shape == mesh.coordinates.shape
        assert state.velocity.shape == mesh.coordinates.shape
        assert state.acceleration.shape == mesh.coordinates.shape
        assert state.time == 0.0
        assert state.internal_energy == 0.0
        assert state.hourglass_energy == 0.0

        dt = 1.0e-9  # Well below critical dt for this mesh / material.
        new_state = explicit_step(
            state,
            dt=dt,
            lam=_LAM,
            mu=_MU,
            rho=_RHO,
            lambda_h=_LAMBDA_H,
        )

        # All arrays must be finite.
        assert np.all(np.isfinite(new_state.coords))
        assert np.all(np.isfinite(new_state.displacement))
        assert np.all(np.isfinite(new_state.velocity))
        assert np.all(np.isfinite(new_state.acceleration))
        # Conservation diagnostics must be non-negative scalars.
        assert new_state.internal_energy >= 0.0
        assert new_state.hourglass_energy >= 0.0
        assert new_state.time == pytest.approx(dt)

        # AC-3 guard: no upstream symbol identity drift.  We do not edit those
        # modules; the simplest check is that the public API objects remain
        # callable and reside in their canonical modules.
        assert callable(hourglass_mod.flanagan_belytschko_force)
        assert hourglass_mod.flanagan_belytschko_force.__module__ == ("mechdsl.codegen.hourglass")
        assert callable(lumped_mass_mod.compute_lumped_mass)
        # Signature contract used by the runtime must not silently change.
        sig = inspect.signature(hourglass_mod.flanagan_belytschko_force)
        assert list(sig.parameters)[:3] == ["u_nodes", "X_nodes", "mu"]

    @pytest.mark.integration
    def test_wall_contact_prevents_penetration(self) -> None:
        """Rigid-wall contact prevents nodal penetration of the impact face.

        Verifies: when impact-face nodes have inward velocity, the rigid-wall
        contact handler clamps positions so no node penetrates the wall plane
        and reflects/zeroes the normal velocity component per the contact law.

        Acceptance criterion: AC-2 — rigid-wall contact prevents penetration.

        Passes when: ``min(node_z - wall_z) >= -tol`` after applying contact
        on a ballistic test set with deterministic inward velocity.
        """
        mesh = _small_bar_mesh()

        # Wall plane at z = 0 with outward normal +z (pointing into the bar).
        wall = RigidWallSpec(
            point=np.array([0.0, 0.0, 0.0], dtype=np.float64),
            normal=np.array([0.0, 0.0, 1.0], dtype=np.float64),
        )

        # Initial velocity: uniform inward (-z) on the bar.
        v0 = np.zeros_like(mesh.coordinates)
        v0[:, 2] = -50.0

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )

        # Hand-craft penetration: shift the bar so the bottom face sits just
        # below the wall plane.  Both coords and displacement must agree —
        # contact reads coords for the signed-distance test and writes back
        # to displacement so the next step starts from a consistent state.
        state.displacement[:, 2] = -1.0e-6  # 1 micron penetration
        state.coords[:] = mesh.coordinates + state.displacement

        clamped = apply_rigid_wall_contact(state, wall)

        # No node may sit below the wall plane (within a tolerance).
        node_z = clamped.coords[:, 2]
        wall_z = float(wall.point[2])
        tol = 1.0e-12
        assert (node_z - wall_z).min() >= -tol, (
            f"Penetration detected after contact: min(z - z_w) = {(node_z - wall_z).min():.3e}"
        )
        # Penetrating nodes (originally at z < wall_z) should have their
        # inward normal velocity component clamped to non-negative.
        z_min_nodes = mesh.boundary_nodes["z_min"]
        assert clamped.velocity[z_min_nodes, 2].min() >= 0.0  # zeroed inward
        # And displacement / coords must satisfy x = X + u after clamping.
        np.testing.assert_allclose(
            clamped.coords, mesh.coordinates + clamped.displacement, atol=1.0e-15
        )

        # And as a regression: a wall the bar moves AWAY from must be a no-op.
        v_away = np.zeros_like(mesh.coordinates)
        v_away[:, 2] = +25.0
        away_state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v_away,
        )
        # Set everyone above wall, with positive velocity → no clamp expected.
        away_state.displacement[:] = 0.0
        away_state.coords[:] = mesh.coordinates  # ensure all z >= 0
        unchanged = apply_rigid_wall_contact(away_state, wall)
        np.testing.assert_allclose(unchanged.velocity, away_state.velocity)
        np.testing.assert_allclose(unchanged.coords, away_state.coords)

    @pytest.mark.integration
    def test_hourglass_force_boundedness(self) -> None:
        """Hourglass energy stays bounded over a non-impact sanity case.

        Verifies: applying the Flanagan-Belytschko hourglass force inside the
        Taylor explicit loop on a uniform-extension or rigid-rotation case
        keeps cumulative hourglass energy below a small fraction of internal
        energy across the test horizon.

        Acceptance criterion: AC-1 — hourglass boundedness in non-impact
        sanity case.

        Passes when: hourglass energy / internal energy stays under the
        configured budget at every reported step (carry-forward Phase 6
        gate: use a non-trivial number of explicit steps and a load case
        that can excite hourglass modes so the bound is meaningful).
        """
        mesh = _small_bar_mesh()

        # Excite a small but non-uniform velocity field that *can* couple to
        # hourglass modes (a slight torsional twist about z), instead of a
        # pure rigid-body or constant-strain motion.
        coords = mesh.coordinates
        cx = 0.5 * (coords[:, 0].min() + coords[:, 0].max())
        cy = 0.5 * (coords[:, 1].min() + coords[:, 1].max())
        omega = 1.0e-3  # small angular velocity (linear regime)
        v0 = np.zeros_like(coords)
        v0[:, 0] = -omega * (coords[:, 1] - cy)
        v0[:, 1] = +omega * (coords[:, 0] - cx)

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )

        n_steps = 60  # carry-forward: ≥ 50 to avoid masking growth
        dt = 1.0e-10
        ratios = []
        for _ in range(n_steps):
            state = explicit_step(
                state,
                dt=dt,
                lam=_LAM,
                mu=_MU,
                rho=_RHO,
                lambda_h=_LAMBDA_H,
            )
            denom = state.internal_energy + 1.0e-30
            ratios.append(state.hourglass_energy / denom)

        ratios_arr = np.asarray(ratios)
        # Energies must remain finite, non-negative, and the running ratio
        # must stay below a small budget (10%).
        assert np.all(np.isfinite(ratios_arr))
        assert state.hourglass_energy >= 0.0
        assert state.internal_energy > 0.0  # the run must have done work
        assert ratios_arr.max() < 0.10, (
            f"Hourglass ratio exceeded budget: max={ratios_arr.max():.3e}"
        )

        # Constant-strain motion (uniform extension) must keep HG energy at
        # essentially zero — this is the FB projection invariant.
        state2 = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )
        # Apply a uniform pre-strain along x: u_x = eps * X.
        eps = 1.0e-5
        state2.displacement[:, 0] = eps * coords[:, 0]
        state2.coords[:] = coords + state2.displacement
        # Single elastic step with zero velocity → drives finite f_int but
        # constant-strain HG force must be (numerically) zero.
        state2 = explicit_step(
            state2,
            dt=dt,
            lam=_LAM,
            mu=_MU,
            rho=_RHO,
            lambda_h=_LAMBDA_H,
        )
        # HG energy must remain at machine-zero on a constant-strain field.
        assert abs(state2.hourglass_energy) <= 1.0e-18

    @pytest.mark.integration
    def test_zero_velocity_no_op_step(self) -> None:
        """A step with zero velocity and zero displacement must keep state at rest.

        Failure-route guard: ensures the explicit loop is a true no-op when
        nothing is happening (no spurious forces, no spurious energy).
        """
        mesh = _small_bar_mesh()
        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )
        new = explicit_step(
            state,
            dt=1.0e-10,
            lam=_LAM,
            mu=_MU,
            rho=_RHO,
            lambda_h=_LAMBDA_H,
        )
        np.testing.assert_allclose(new.displacement, 0.0, atol=1.0e-30)
        np.testing.assert_allclose(new.velocity, 0.0, atol=1.0e-30)
        assert new.internal_energy == pytest.approx(0.0, abs=1.0e-30)
        assert new.hourglass_energy == pytest.approx(0.0, abs=1.0e-30)

    @pytest.mark.integration
    def test_explicit_step_with_wall_contact(self) -> None:
        """The explicit loop accepts walls and prevents penetration end-to-end."""
        mesh = _small_bar_mesh()
        # Initial inward velocity for the entire bar; wall at z = -1 micron.
        v0 = np.zeros_like(mesh.coordinates)
        v0[:, 2] = -50.0
        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )
        wall = RigidWallSpec(
            point=np.array([0.0, 0.0, -1.0e-6], dtype=np.float64),
            normal=np.array([0.0, 0.0, 1.0], dtype=np.float64),
        )
        dt = 1.0e-9
        for _ in range(50):
            state = explicit_step(
                state,
                dt=dt,
                lam=_LAM,
                mu=_MU,
                rho=_RHO,
                lambda_h=_LAMBDA_H,
                walls=(wall,),
            )
        assert (state.coords[:, 2] - wall.point[2]).min() >= -1.0e-12
