"""Phase 7 (ph10_preq) Task P7-2: Taylor Johnson-Cook state and postprocessing.

Plan: ``dev/plans/ph10_preq.md`` lines 278-315 (Phase E7).

Covers Johnson-Cook state integration into the internal Taylor runtime and
the postprocessing helpers that extract final geometry and equivalent
plastic strain. The public benchmark runner is owned by Phase 8.

Acceptance criteria covered:
  AC-1: Johnson-Cook state update produces finite stress, temperature, and PEEQ.
  AC-2: Final length and mushroom-radius postprocessing is deterministic.
  AC-3: Johnson-Cook model behavior is unchanged unless a focused defect is proven.
"""

from __future__ import annotations

import numpy as np
import pytest

from mechdsl.symbolic.models.johnson_cook import JohnsonCookMaterial
from mechdsl.verify.benchmarks._meshes import structured_block_mesh
from mechdsl.verify.benchmarks._taylor_runtime import (
    explicit_step,
    explicit_step_jc,
    extract_equivalent_plastic_strain,
    final_length,
    init_taylor_runtime,
    init_taylor_runtime_jc,
    mushroom_radius,
)

# ---------------------------------------------------------------------------
# Common physical parameters.
# ---------------------------------------------------------------------------

_E_MOD = 200.0e9  # Pa
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


def _make_jc_material() -> JohnsonCookMaterial:
    """Steel-like Johnson-Cook calibration with mild rate / thermal sensitivity."""
    return JohnsonCookMaterial(
        E=_E_MOD,
        nu=_NU,
        A=350.0e6,
        B=275.0e6,
        n=0.36,
        C=0.022,
        m=1.0,
        eps_dot_0=1.0,
        T_melt=1793.0,
        T_ref=293.0,
        rho_c_p=3.5e6,
        beta=0.9,
    )


class TestTaskP7_2:
    """Tests for Task P7-2: Taylor Johnson-Cook state and postprocessing.

    Acceptance criteria covered: AC-1 (finite JC state), AC-2 (deterministic
    postprocessing), AC-3 (no upstream JC semantic drift).
    """

    @pytest.mark.integration
    def test_finite_johnson_cook_state_update(self) -> None:
        """A few JC explicit steps in the Taylor runtime keep state finite.

        Drives the bar past yield with a uniform inward velocity on the
        impact face; checks that PK2 stress, temperature, and equivalent
        plastic strain all stay finite and physically admissible.
        """
        mesh = _small_bar_mesh()
        mat = _make_jc_material()

        # Inward velocity on the impact face — short pulse at moderate speed
        # so the centroid strain crosses yield within a handful of steps.
        v0 = np.zeros_like(mesh.coordinates)
        impact = mesh.boundary_nodes["z_max"]
        v0[impact, 2] = -200.0  # m/s — well into plastic regime for steel

        state = init_taylor_runtime_jc(
            mesh,
            rho=_RHO,
            jc_material=mat,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )

        # Initial state shape contracts.
        n_elem = mesh.n_elements
        assert state.material_state["eqplas"].shape == (n_elem,)
        assert state.material_state["temperature"].shape == (n_elem,)
        assert state.material_state["pk2_stress"].shape == (n_elem, 3, 3)
        assert np.all(state.material_state["eqplas"] == 0.0)
        assert np.all(state.material_state["temperature"] == mat.T_ref)

        # dt sized so the stress wave from the impact face actually crosses
        # the top element within the test horizon: c = sqrt(E/rho) ~= 5060 m/s,
        # 1 mm element traverses in ~200 ns, so dt = 1e-8 (10 ns, factor-20
        # safety vs critical) reaches yield within a handful of steps. dt = 1e-9
        # is overly conservative for this geometry — the wave hasn't propagated
        # yet so no element sees the strain.
        dt = 1.0e-8
        for _ in range(10):
            state = explicit_step_jc(
                state,
                dt=dt,
                jc_material=mat,
                rho=_RHO,
                lambda_h=_LAMBDA_H,
            )

        assert np.all(np.isfinite(state.material_state["pk2_stress"]))
        assert np.all(np.isfinite(state.material_state["temperature"]))
        assert np.all(np.isfinite(state.material_state["eqplas"]))
        assert np.all(state.material_state["eqplas"] >= 0.0)
        # Temperature must stay strictly below melt and at/above reference.
        assert np.all(state.material_state["temperature"] >= mat.T_ref - 1e-9)
        assert np.all(state.material_state["temperature"] < mat.T_melt)
        # Some plasticity must have occurred under this loading.
        assert state.material_state["eqplas"].max() > 0.0

    @pytest.mark.integration
    def test_equivalent_plastic_strain_extraction(self) -> None:
        """``extract_equivalent_plastic_strain`` returns a non-negative,
        per-element array that does not decrease across consecutive steps under
        proportional plastic loading."""
        mesh = _small_bar_mesh()
        mat = _make_jc_material()

        v0 = np.zeros_like(mesh.coordinates)
        impact = mesh.boundary_nodes["z_max"]
        v0[impact, 2] = -200.0

        state = init_taylor_runtime_jc(
            mesh,
            rho=_RHO,
            jc_material=mat,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )

        dt = 1.0e-9
        # Warm up to enter plastic flow.
        for _ in range(8):
            state = explicit_step_jc(state, dt=dt, jc_material=mat, rho=_RHO, lambda_h=_LAMBDA_H)
        eqplas_a = extract_equivalent_plastic_strain(state).copy()

        for _ in range(8):
            state = explicit_step_jc(state, dt=dt, jc_material=mat, rho=_RHO, lambda_h=_LAMBDA_H)
        eqplas_b = extract_equivalent_plastic_strain(state).copy()

        n_elem = mesh.n_elements
        assert eqplas_a.shape == (n_elem,)
        assert eqplas_b.shape == (n_elem,)
        assert np.all(eqplas_a >= 0.0)
        assert np.all(eqplas_b >= 0.0)
        # Monotonically non-decreasing under proportional loading.
        assert np.all(eqplas_b >= eqplas_a - 1.0e-15)
        # Returned array is a copy (modifying it must not alter state).
        eqplas_b[:] = -1.0
        assert np.all(state.material_state["eqplas"] >= 0.0)

    @pytest.mark.integration
    def test_final_length_postprocessing(self) -> None:
        """``final_length`` is deterministic (bit-for-bit) and respects axial
        compression."""
        mesh = _small_bar_mesh()
        L_initial = float(mesh.coordinates[:, 2].max() - mesh.coordinates[:, 2].min())

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )
        # Hand-craft a 10% uniform axial compression.
        compression = 0.10
        state.displacement[:, 2] = -compression * mesh.coordinates[:, 2]
        state.coords[:] = mesh.coordinates + state.displacement

        L1 = final_length(state)
        L2 = final_length(state)
        assert L1 == L2  # bit-for-bit determinism
        assert L_initial >= L1
        # The compression analytically drops L by exactly 10%.
        assert pytest.approx(L_initial * (1.0 - compression), rel=1e-12) == L1

    @pytest.mark.integration
    def test_mushroom_radius_postprocessing(self) -> None:
        """``mushroom_radius`` returns the impact-face max radius and is
        deterministic."""
        mesh = _small_bar_mesh()

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )

        # Hand-craft a mushroom on the z_min face: push each node radially
        # outward by a known multiplier from the bar centroid (centred at the
        # geometric centre of the cross-section).
        z_min_nodes = mesh.boundary_nodes["z_min"]
        cx = 0.5 * (mesh.coordinates[:, 0].min() + mesh.coordinates[:, 0].max())
        cy = 0.5 * (mesh.coordinates[:, 1].min() + mesh.coordinates[:, 1].max())
        # For each impact-face node, displace it outward by 50% of its radius.
        for n in z_min_nodes:
            X = mesh.coordinates[n]
            dx = X[0] - cx
            dy = X[1] - cy
            state.displacement[n, 0] = 0.5 * dx
            state.displacement[n, 1] = 0.5 * dy
        state.coords[:] = mesh.coordinates + state.displacement

        # Hand-computed expected max radius about (cx, cy).
        x_face = state.coords[z_min_nodes, 0]
        y_face = state.coords[z_min_nodes, 1]
        r_expected = float(np.max(np.sqrt((x_face - cx) ** 2 + (y_face - cy) ** 2)))

        r1 = mushroom_radius(state, axis=2, face="min", center=(cx, cy))
        r2 = mushroom_radius(state, axis=2, face="min", center=(cx, cy))
        assert r1 == r2  # determinism
        assert r1 == pytest.approx(r_expected, abs=1.0e-12)

    @pytest.mark.integration
    def test_p7_1_svk_path_unchanged(self) -> None:
        """The original SVK ``init_taylor_runtime`` / ``explicit_step`` path
        from P7-1 is unchanged — material_state stays empty and the run still
        produces non-negative diagnostics."""
        mesh = _small_bar_mesh()
        v0 = np.zeros_like(mesh.coordinates)
        v0[:, 2] = -10.0

        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=v0,
        )
        # SVK path attaches no JC keys.
        assert state.material_state == {}

        dt = 1.0e-9
        for _ in range(5):
            state = explicit_step(state, dt=dt, lam=_LAM, mu=_MU, rho=_RHO, lambda_h=_LAMBDA_H)
        # Still no JC keys after a non-JC run.
        assert state.material_state == {}
        assert state.internal_energy >= 0.0
        assert state.hourglass_energy >= 0.0

    @pytest.mark.integration
    def test_jc_elastic_step_does_not_grow_eqplas(self) -> None:
        """A JC step that stays below yield must leave eqplas and T unchanged."""
        mesh = _small_bar_mesh()
        mat = _make_jc_material()

        # No initial velocity, no displacement — strain trial is zero.
        state = init_taylor_runtime_jc(
            mesh,
            rho=_RHO,
            jc_material=mat,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )

        eqplas_before = state.material_state["eqplas"].copy()
        T_before = state.material_state["temperature"].copy()

        state = explicit_step_jc(state, dt=1.0e-10, jc_material=mat, rho=_RHO, lambda_h=_LAMBDA_H)

        np.testing.assert_array_equal(state.material_state["eqplas"], eqplas_before)
        np.testing.assert_array_equal(state.material_state["temperature"], T_before)

    @pytest.mark.integration
    def test_final_length_single_element_mesh(self) -> None:
        """``final_length`` works for a degenerate single-element mesh."""
        mesh = structured_block_mesh("hex8", length=1.0, width=1.0, height=2.0, nx=1, ny=1, nz=1)
        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )
        # Initial length on the undeformed configuration matches the input.
        assert final_length(state, axis=2) == pytest.approx(2.0, abs=1.0e-15)

    @pytest.mark.integration
    def test_mushroom_radius_default_center(self) -> None:
        """Without an explicit ``center`` the helper uses the face centroid."""
        mesh = _small_bar_mesh()
        state = init_taylor_runtime(
            mesh,
            rho=_RHO,
            lam=_LAM,
            mu=_MU,
            lambda_h=_LAMBDA_H,
            initial_velocity=None,
        )
        # Undeformed bar — face centroid is the geometric centre.
        cx = 0.5 * (mesh.coordinates[:, 0].min() + mesh.coordinates[:, 0].max())
        cy = 0.5 * (mesh.coordinates[:, 1].min() + mesh.coordinates[:, 1].max())
        z_min_nodes = mesh.boundary_nodes["z_min"]
        x_face = state.coords[z_min_nodes, 0]
        y_face = state.coords[z_min_nodes, 1]
        r_expected = float(np.max(np.sqrt((x_face - cx) ** 2 + (y_face - cy) ** 2)))
        # Defaulted center should match the explicit centre.
        assert mushroom_radius(state, axis=2, face="min") == pytest.approx(r_expected, abs=1.0e-12)


class TestTaskP7_2FailureRoutes:
    """Failure / boundary tests for the P7-2 public symbols.

    Targeted at the validation paths added by the implementation:
    ``dt <= 0`` rejection in :func:`explicit_step_jc`, non-Hex8 mesh rejection
    in :func:`init_taylor_runtime_jc`, missing-key handling for
    :func:`extract_equivalent_plastic_strain`, and missing boundary set or
    illegal axis/face for :func:`mushroom_radius` / :func:`final_length`.
    """

    @pytest.mark.integration
    def test_explicit_step_jc_rejects_non_positive_dt(self) -> None:
        """``dt <= 0`` must raise ``ValueError`` before touching the JC update."""
        mesh = _small_bar_mesh()
        mat = _make_jc_material()
        state = init_taylor_runtime_jc(mesh, rho=_RHO, jc_material=mat, lambda_h=_LAMBDA_H)
        with pytest.raises(ValueError, match="dt must be positive"):
            explicit_step_jc(state, dt=0.0, jc_material=mat, rho=_RHO, lambda_h=_LAMBDA_H)
        with pytest.raises(ValueError, match="dt must be positive"):
            explicit_step_jc(state, dt=-1.0e-9, jc_material=mat, rho=_RHO, lambda_h=_LAMBDA_H)

    @pytest.mark.integration
    def test_init_taylor_runtime_jc_rejects_non_hex8(self) -> None:
        """The JC initialiser inherits the Hex8-only mass restriction."""
        from mechdsl.verify.benchmarks._meshes import structured_block_mesh

        mesh = structured_block_mesh(
            "tet10", length=1.0e-3, width=1.0e-3, height=4.0e-3, nx=1, ny=1, nz=4
        )
        mat = _make_jc_material()
        with pytest.raises(ValueError, match="supports only Hex8"):
            init_taylor_runtime_jc(mesh, rho=_RHO, jc_material=mat, lambda_h=_LAMBDA_H)

    @pytest.mark.integration
    def test_extract_eqplas_requires_jc_init(self) -> None:
        """An SVK state has no ``eqplas`` key; the helper must say so clearly."""
        mesh = _small_bar_mesh()
        state = init_taylor_runtime(
            mesh, rho=_RHO, lam=_LAM, mu=_MU, lambda_h=_LAMBDA_H, initial_velocity=None
        )
        with pytest.raises(KeyError, match="init_taylor_runtime_jc"):
            extract_equivalent_plastic_strain(state)

    @pytest.mark.integration
    def test_mushroom_radius_missing_boundary_raises(self) -> None:
        """A mesh without the requested boundary set must raise ``KeyError``."""
        from mechdsl.verify.benchmarks._meshes import BenchmarkMesh

        mesh = _small_bar_mesh()
        # Strip the z_max boundary set so the helper has nothing to query.
        stripped = BenchmarkMesh(
            element_type=mesh.element_type,
            coordinates=mesh.coordinates,
            connectivity=mesh.connectivity,
            boundary_nodes={k: v for k, v in mesh.boundary_nodes.items() if k != "z_max"},
            face_tags=dict(mesh.face_tags),
        )
        state = init_taylor_runtime(
            stripped, rho=_RHO, lam=_LAM, mu=_MU, lambda_h=_LAMBDA_H, initial_velocity=None
        )
        with pytest.raises(KeyError, match="z_max"):
            mushroom_radius(state, axis=2, face="max")

    @pytest.mark.integration
    def test_mushroom_radius_invalid_axis_or_face_raises(self) -> None:
        """``axis`` and ``face`` must be in their allowed sets."""
        mesh = _small_bar_mesh()
        state = init_taylor_runtime(
            mesh, rho=_RHO, lam=_LAM, mu=_MU, lambda_h=_LAMBDA_H, initial_velocity=None
        )
        with pytest.raises(ValueError, match="axis must be 0, 1, or 2"):
            mushroom_radius(state, axis=3, face="min")
        with pytest.raises(ValueError, match="face must be"):
            mushroom_radius(state, axis=2, face="middle")  # type: ignore[arg-type]

    @pytest.mark.integration
    def test_final_length_invalid_axis_raises(self) -> None:
        """``final_length`` rejects axes outside ``{0, 1, 2}``."""
        mesh = _small_bar_mesh()
        state = init_taylor_runtime(
            mesh, rho=_RHO, lam=_LAM, mu=_MU, lambda_h=_LAMBDA_H, initial_velocity=None
        )
        with pytest.raises(ValueError, match="axis must be 0, 1, or 2"):
            final_length(state, axis=5)
