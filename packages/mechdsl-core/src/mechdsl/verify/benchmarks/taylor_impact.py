"""Public Taylor impact benchmark API (Phase 10 prerequisite — Phase E8 / P8-1).

This module wraps the *internal* Phase E7 Taylor explicit runtime
(:mod:`mechdsl.verify.benchmarks._taylor_runtime`) into a public, deterministic
benchmark runner that mirrors the shape of every other Phase 10 runner
(see :mod:`mechdsl.verify.benchmarks.cantilever`):

- A frozen ``TaylorImpactParameters`` dataclass with ``smoke()`` and
  ``nightly()`` classmethod profiles.
- ``run_taylor_impact_benchmark(params=...) -> BenchmarkResult`` that returns
  the shared :class:`BenchmarkResult` schema unchanged. Taylor-specific
  metrics (final length, mushroom radius, mushroom diameter, peak PEEQ) are
  packed into ``BenchmarkResult.extras`` so AC-3 — *no shared benchmark
  result schema changes are required* — is satisfied.

The runtime building blocks (``init_taylor_runtime_jc``, ``explicit_step_jc``,
``apply_rigid_wall_contact``, ``final_length``, ``mushroom_radius``,
``extract_equivalent_plastic_strain``) are consumed verbatim — Phase E7's
public signatures must remain bit-for-bit unchanged.

Bar geometry / impact convention
--------------------------------
The bar is modelled as a rectangular Hex8 block extending along +z with a
square cross section. The impact face is **z_min** (the bottom face). The
rigid wall sits at ``z = wall_z`` with outward normal ``+z`` so the valid
half-space is ``z >= wall_z`` (the bar). The impact velocity must be
**strictly negative** (the bar moves toward the wall in the -z direction).

dt sizing (carry-forward Phase 6 wave-physics gate)
---------------------------------------------------
The explicit central-difference integrator requires ``dt <= dt_crit ≈
h_min / c`` where ``c = sqrt(E/rho)`` is the longitudinal wave speed and
``h_min`` is the smallest element edge. For the steel-like smoke
calibration (E≈200 GPa, rho≈7800) the wave speed is ≈5060 m/s. With a
2x2x8 mesh of a 25.4 x 7.62 x 7.62 mm bar the smallest edge is
≈ 3.18 mm so ``dt_crit ≈ 6.3e-7 s``. Both ``smoke()`` and ``nightly()``
profiles pick ``dt`` an order of magnitude below that bound; the
``n_steps * dt`` horizon spans at least one longitudinal wave traversal of
the bar so the run is physically meaningful.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from mechdsl.symbolic.models.johnson_cook import JohnsonCookMaterial
from mechdsl.verify.benchmarks._core import BenchmarkResult
from mechdsl.verify.benchmarks._meshes import structured_block_mesh
from mechdsl.verify.benchmarks._taylor_runtime import (
    RigidWallSpec,
    apply_rigid_wall_contact,
    explicit_step_jc,
    extract_equivalent_plastic_strain,
    final_length,
    init_taylor_runtime_jc,
    mushroom_radius,
)

__all__ = [
    "TaylorImpactParameters",
    "run_taylor_impact_benchmark",
]


# Conventional axis index for the bar; the mesh is built with the bar
# extending in +z, so axis 2 is the impact axis.
_BAR_AXIS = 2


@dataclass(frozen=True)
class TaylorImpactParameters:
    """Public Taylor impact benchmark parameters.

    Defaults are smoke-sized for local CI. Use :meth:`nightly` to construct the
    full plan-sized mesh and integration horizon without changing the public
    runner contract. Both profiles produce **bit-for-bit deterministic** runs:
    NumPy-only, no random state, no dict-iteration-order dependence.

    The bar extends along +z. The impact face is ``z_min`` (the face nearest
    the wall). The rigid wall plane is at ``z = wall_z`` with outward normal
    +z; the valid half-space is ``z >= wall_z``. The impact velocity must be
    strictly negative (bar moves in -z, toward the wall).

    Attributes
    ----------
    length, width, height
        Bar dimensions in metres (length is along +z; width/height span the
        cross section). Defaults follow the Johnson & Cook (1985) Taylor
        impact reference: a 25.4 mm bar with a 7.62 mm square cross section
        (modelling the cylindrical reference as a rectangular Hex8 block).
    nx, ny, nz
        Mesh subdivisions. Smoke defaults are tiny (2 x 2 x 8) so the
        smoke run finishes in O(seconds). ``nightly()`` ramps to a full
        plan-sized mesh.
    E, nu, rho, A, B, n, C, m, eps_dot_0, T_ref, T_melt, rho_c_p, beta
        Johnson-Cook material calibration. Defaults are a steel-like
        calibration (matching ``test_phase10_taylor_state.py``) that exercises
        rate and thermal sensitivity at impact velocities of O(100 m/s).
    impact_velocity
        Initial uniform z-velocity (m/s). Must be strictly negative.
    dt
        Explicit-integration time step (s). Must be positive and chosen to
        respect the critical timestep ``dt_crit ≈ h_min / sqrt(E/rho)``.
    n_steps
        Number of explicit steps. ``smoke()`` keeps this small; ``nightly()``
        runs a horizon long enough to develop the mushroom shape.
    lambda_h
        Flanagan-Belytschko hourglass control coefficient (default 0.05,
        matches the FB hourglass force default).
    wall_z
        z-coordinate of the rigid wall plane. Must be **at or below** the
        bar's reference ``z_min``; placing the wall *behind* the bar
        (``wall_z`` strictly greater than the bar's reference ``z_min``,
        i.e. inside or past the bar) is rejected at construction time.
    element_type
        Mesh element type. Currently only ``"hex8"`` is supported (lumped
        mass + reduced-Hex8 internal force are HEX8-only in the runtime).
    profile
        Free-form telemetry tag (``"smoke"`` or ``"nightly"`` by default).
    """

    # --- Geometry (Johnson & Cook 1985 reference, SI units) ---
    length: float = 25.4e-3  # m, bar length along +z
    width: float = 7.62e-3
    height: float = 7.62e-3
    nx: int = 2
    ny: int = 2
    nz: int = 8

    # --- Material (steel-like JC, matching test_phase10_taylor_state.py) ---
    E: float = 200.0e9
    nu: float = 0.30
    rho: float = 7800.0
    A: float = 350.0e6
    B: float = 275.0e6
    n: float = 0.36
    C: float = 0.022
    m: float = 1.0
    eps_dot_0: float = 1.0
    T_ref: float = 293.0
    T_melt: float = 1793.0
    rho_c_p: float = 3.5e6
    beta: float = 0.9

    # --- Impact + integration ---
    impact_velocity: float = -190.0  # m/s, must be < 0 (toward -z wall)
    dt: float = 2.0e-8  # s, ~30x below dt_crit for the smoke mesh
    n_steps: int = 10  # smoke horizon: ~0.2 us — enough for a sanity run
    lambda_h: float = 0.05

    # --- Wall (default rigid plane at z=0, normal +z) ---
    wall_z: float = 0.0

    # --- Topology / telemetry ---
    element_type: str = "hex8"
    profile: str = "smoke"

    @classmethod
    def smoke(cls, **overrides: Any) -> TaylorImpactParameters:
        """Return local smoke-sized Taylor impact parameters.

        Small mesh (2 x 2 x 8 Hex8), short horizon (~0.2 us at dt=2e-8 s).
        Designed to run in O(seconds) on a developer laptop while still
        exercising the full JC return mapping + rigid-wall contact path
        end-to-end.
        """
        return replace(cls(profile="smoke"), **overrides)

    @classmethod
    def nightly(cls, **overrides: Any) -> TaylorImpactParameters:
        """Return full plan-sized Taylor impact parameters for nightly CI.

        Refined mesh (6 x 6 x 20 Hex8) with a longer horizon (~20 us at
        dt=5e-8 s, i.e. several longitudinal wave traversals) so the
        mushroom shape and peak plastic strain develop fully. ``dt`` is
        reduced from the smoke value to keep the explicit integration
        comfortably below the refined-mesh ``dt_crit``.
        """
        return replace(
            cls(
                nx=6,
                ny=6,
                nz=20,
                dt=5.0e-8,
                n_steps=400,
                profile="nightly",
            ),
            **overrides,
        )

    @property
    def horizon_s(self) -> float:
        """Total integration horizon ``n_steps * dt`` in seconds."""
        return float(self.n_steps) * float(self.dt)


def run_taylor_impact_benchmark(
    *,
    params: TaylorImpactParameters | None = None,
) -> BenchmarkResult:
    """Run the public Taylor impact benchmark and return a :class:`BenchmarkResult`.

    Composes the Phase E7 internal Taylor runtime (Johnson-Cook radial-return
    return mapping + reduced-Hex8 internal force + Flanagan-Belytschko
    hourglass control + frictionless rigid-wall contact) into a deterministic
    public runner. Taylor-specific metrics are packed into ``extras``; the
    shared :class:`BenchmarkResult` schema is reused unchanged (AC-3).

    Parameters
    ----------
    params
        Benchmark parameters. ``None`` (default) uses
        :meth:`TaylorImpactParameters.smoke`.

    Returns
    -------
    BenchmarkResult
        With:

        - ``displacements`` — final nodal displacements ``(n_nodes, 3)``.
        - ``newton_iters`` — ``0`` (the integrator is explicit; documented
          here so downstream telemetry that aggregates Newton counts does
          not double-count).
        - ``wallclock_s`` — total wallclock for the explicit loop (s).
        - ``extras`` — dict with keys ``final_length``, ``mushroom_radius``,
          ``mushroom_diameter``, ``peak_peeq``, ``profile``, ``n_steps``,
          ``dt``, ``horizon_s``, ``impact_velocity``, ``mesh_n_nodes``,
          ``mesh_n_elem``.
    """
    params = params or TaylorImpactParameters.smoke()
    _validate_params(params)

    mesh = structured_block_mesh(
        params.element_type,
        length=params.width,  # x-extent
        width=params.height,  # y-extent
        height=params.length,  # z-extent (bar axis)
        nx=params.nx,
        ny=params.ny,
        nz=params.nz,
    )

    jc_material = JohnsonCookMaterial(
        E=params.E,
        nu=params.nu,
        A=params.A,
        B=params.B,
        n=params.n,
        C=params.C,
        m=params.m,
        eps_dot_0=params.eps_dot_0,
        T_melt=params.T_melt,
        T_ref=params.T_ref,
        rho_c_p=params.rho_c_p,
        beta=params.beta,
    )

    # Initial velocity: uniform impact velocity in -z on every node. The
    # rigid wall + JC return mapping does the rest of the physics.
    v0 = np.zeros_like(mesh.coordinates)
    v0[:, _BAR_AXIS] = params.impact_velocity

    state = init_taylor_runtime_jc(
        mesh,
        rho=params.rho,
        jc_material=jc_material,
        lambda_h=params.lambda_h,
        initial_velocity=v0,
    )

    # Wall plane at z = wall_z with outward normal +z.
    wall = RigidWallSpec(
        point=np.array([0.0, 0.0, params.wall_z], dtype=np.float64),
        normal=np.array([0.0, 0.0, 1.0], dtype=np.float64),
    )

    t0 = time.perf_counter()
    for _ in range(params.n_steps):
        state = explicit_step_jc(
            state,
            dt=params.dt,
            jc_material=jc_material,
            rho=params.rho,
            lambda_h=params.lambda_h,
        )
        # Apply contact after the leapfrog update so the next step starts
        # from a non-penetrating configuration.
        state = apply_rigid_wall_contact(state, wall)
    wallclock = float(time.perf_counter() - t0)

    # --- Postprocessing: deterministic Taylor-impact metrics ---
    bar_axis = _BAR_AXIS
    L_final = final_length(state, axis=bar_axis)
    r_mush = mushroom_radius(state, axis=bar_axis, face="min")
    peak_peeq = float(extract_equivalent_plastic_strain(state).max())

    extras = {
        "final_length": float(L_final),
        "mushroom_radius": float(r_mush),
        "mushroom_diameter": float(2.0 * r_mush),
        "peak_peeq": peak_peeq,
        "profile": params.profile,
        "n_steps": int(params.n_steps),
        "dt": float(params.dt),
        "horizon_s": params.horizon_s,
        "impact_velocity": float(params.impact_velocity),
        "wall_z": float(params.wall_z),
        "mesh_n_nodes": int(mesh.n_nodes),
        "mesh_n_elem": int(mesh.n_elements),
        "element_type": params.element_type,
    }

    return BenchmarkResult(
        displacements=state.displacement.copy(),
        newton_iters=0,  # explicit integrator — no Newton iterations
        wallclock_s=wallclock,
        extras=extras,
    )


def _validate_params(params: TaylorImpactParameters) -> None:
    """Validate a :class:`TaylorImpactParameters` instance.

    Each invalid configuration raises :class:`ValueError` with a message
    that names the offending field. Five failure modes are covered (in
    addition to all-positive sanity checks on the JC calibration):

    1. ``impact_velocity`` zero or non-negative.
    2. ``dt`` non-positive.
    3. Any of ``length``, ``width``, ``height`` non-positive.
    4. ``element_type`` other than ``"hex8"``.
    5. ``wall_z`` placed behind the bar (strictly above the reference
       ``z_min`` of the bar, i.e. inside or past it).
    """
    if params.impact_velocity == 0.0:
        raise ValueError(
            "TaylorImpactParameters.impact_velocity must be non-zero "
            f"(strictly negative for an inward impact); got {params.impact_velocity}."
        )
    if params.impact_velocity > 0.0:
        raise ValueError(
            "TaylorImpactParameters.impact_velocity must be strictly negative "
            "(the bar must move in -z toward the wall); "
            f"got impact_velocity={params.impact_velocity}."
        )
    if params.dt <= 0.0:
        raise ValueError(f"TaylorImpactParameters.dt must be positive; got dt={params.dt}.")
    if params.length <= 0.0:
        raise ValueError(
            f"TaylorImpactParameters.length must be positive; got length={params.length}."
        )
    if params.width <= 0.0:
        raise ValueError(
            f"TaylorImpactParameters.width must be positive; got width={params.width}."
        )
    if params.height <= 0.0:
        raise ValueError(
            f"TaylorImpactParameters.height must be positive; got height={params.height}."
        )
    if params.nx <= 0 or params.ny <= 0 or params.nz <= 0:
        raise ValueError(
            "TaylorImpactParameters.{nx,ny,nz} must be positive; "
            f"got nx={params.nx}, ny={params.ny}, nz={params.nz}."
        )
    if params.n_steps <= 0:
        raise ValueError(
            f"TaylorImpactParameters.n_steps must be positive; got n_steps={params.n_steps}."
        )
    if params.element_type != "hex8":
        raise ValueError(
            "TaylorImpactParameters.element_type must be 'hex8' "
            "(reduced-Hex8 + lumped mass is HEX8-only in the Taylor runtime); "
            f"got element_type={params.element_type!r}."
        )
    # Wall must sit at or below the bar's reference z_min (which is 0.0 for
    # structured_block_mesh). Placing the wall strictly above z_min puts it
    # behind / inside the bar — geometrically inadmissible.
    bar_z_min = 0.0
    if params.wall_z > bar_z_min:
        raise ValueError(
            "TaylorImpactParameters.wall_z must be at or below the bar's reference "
            f"z_min={bar_z_min} (the wall cannot sit behind or inside the bar); "
            f"got wall_z={params.wall_z}."
        )
    # JC calibration sanity (mirrors JohnsonCookMaterial.__post_init__ but
    # raises here so the user sees the named field on TaylorImpactParameters
    # before paying the JC construction cost).
    if params.E <= 0.0:
        raise ValueError(f"TaylorImpactParameters.E must be positive; got E={params.E}.")
    if not (-1.0 < params.nu < 0.5):
        raise ValueError(
            f"TaylorImpactParameters.nu must satisfy -1 < nu < 0.5; got nu={params.nu}."
        )
    if params.rho <= 0.0:
        raise ValueError(f"TaylorImpactParameters.rho must be positive; got rho={params.rho}.")
