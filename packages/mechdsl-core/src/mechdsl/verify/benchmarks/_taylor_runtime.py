"""Benchmark-local explicit Taylor runtime (Phase 10 prerequisite — Phase E7).

This module is intentionally internal to ``mechdsl.verify.benchmarks``. It
composes the explicit-dynamics building blocks (reduced-Hex8 internal force,
Flanagan-Belytschko hourglass force, lumped mass) into a NumPy-only
central-difference loop suitable for **Taylor impact runtime sanity** work.

Scope
-----
This is the runtime *enablement* phase (Plan E7). It deliberately does not
expose the public Taylor benchmark runner — that surface is owned by the
next phase (E8, ``run_taylor_impact_benchmark``).

What is implemented here:

- :class:`ExplicitTaylorState` — central-difference state container with
  room for material-state arrays added by P7-2 (Johnson-Cook).
- :class:`RigidWallSpec` — half-space rigid wall (point + outward normal).
- :func:`init_taylor_runtime` — initial state allocator with optional
  initial velocity field.
- :func:`explicit_step` — one half-step velocity / full-step position update
  built from reduced-Hex8 SVK internal force and FB hourglass control,
  followed by optional rigid-wall contact.
- :func:`apply_rigid_wall_contact` — penetration prevention by clamping to
  the wall plane and zeroing the inward normal velocity component.
- :func:`hourglass_energy_increment` — incremental ``f_HG · du`` work used
  by the explicit loop to track cumulative hourglass energy.

All operations are pure NumPy. Taichi codegen for the explicit loop is out
of scope for this prerequisite phase.

Material model
~~~~~~~~~~~~~~
P7-1 ships a simple Saint Venant-Kirchhoff (SVK) constitutive update at the
Hex8 centroid (one-point reduced quadrature). The Johnson-Cook integration
and per-quadrature-point state arrays are P7-2's responsibility — the state
container leaves a generic ``material_state`` slot for that work to attach
arrays without restructuring the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from mechdsl.codegen.hex8_tables import shape_gradients
from mechdsl.codegen.hourglass import flanagan_belytschko_force
from mechdsl.ir.mechanics_ir import ElementType
from mechdsl.solver.lumped_mass import compute_lumped_mass
from mechdsl.symbolic.models.johnson_cook import JohnsonCookMaterial, radial_return

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.verify.benchmarks._meshes import BenchmarkMesh


__all__ = [
    "ExplicitTaylorState",
    "RigidWallSpec",
    "apply_rigid_wall_contact",
    "explicit_step",
    "explicit_step_jc",
    "extract_equivalent_plastic_strain",
    "final_length",
    "hourglass_energy_increment",
    "init_taylor_runtime",
    "init_taylor_runtime_jc",
    "mushroom_radius",
]


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------


@dataclass
class ExplicitTaylorState:
    """Central-difference state for the internal Taylor explicit runtime.

    Mutability is intentional: the explicit loop updates arrays in place
    where possible to avoid per-step allocations. The container is a
    *plain dataclass* (not frozen) so that P7-2 can attach Johnson-Cook
    state arrays to ``material_state`` without restructuring the runtime.

    Attributes
    ----------
    mesh
        Reference to the source :class:`BenchmarkMesh`. Held by reference
        so consumers can map nodal arrays back to topology.
    coords
        Current nodal coordinates in the deformed configuration,
        ``(n_nodes, 3)``.
    displacement
        Cumulative displacement ``u = coords - mesh.coordinates``,
        ``(n_nodes, 3)``.
    velocity
        Nodal velocity at the *current* time level (full-step in this
        leapfrog implementation), ``(n_nodes, 3)``.
    acceleration
        Nodal acceleration at the *current* time level, ``(n_nodes, 3)``.
    mass
        Lumped nodal mass per DoF (same scalar across the 3 components),
        ``(n_nodes, 3)``. Computed once at init from
        :func:`mechdsl.solver.lumped_mass.compute_lumped_mass`.
    time
        Wall-clock time accumulated by the integrator (s).
    internal_energy
        Running estimate of the work done by the internal force,
        ``sum f_int · du`` accumulated across explicit steps.
    hourglass_energy
        Running estimate of the work done by the hourglass force,
        ``sum f_HG · du`` accumulated across explicit steps. Used by the
        AC-1 boundedness test.
    material_state
        Free-form dict reserved for material-history arrays attached by
        P7-2 (e.g. ``{"eqplas": ndarray, "back_stress": ndarray, ...}``).
        Empty by default in P7-1.
    """

    mesh: BenchmarkMesh
    coords: NDArray[np.float64]
    displacement: NDArray[np.float64]
    velocity: NDArray[np.float64]
    acceleration: NDArray[np.float64]
    mass: NDArray[np.float64]
    time: float = 0.0
    internal_energy: float = 0.0
    hourglass_energy: float = 0.0
    material_state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RigidWallSpec:
    """Frictionless rigid half-space wall.

    The wall occupies the half-space ``(x - point) . normal <= 0``; valid
    (non-penetrating) configurations satisfy ``(x - point) . normal >= 0``
    for all nodes. ``normal`` must be a unit vector.

    Attributes
    ----------
    point
        Any point on the wall plane, shape ``(3,)``.
    normal
        Outward unit normal of the wall (pointing into the valid
        half-space), shape ``(3,)``. Validated unit-length at construction.
    restitution
        Coefficient of restitution applied to the inward normal velocity
        component on impact. ``0.0`` (default) gives a perfectly inelastic
        wall — the simplest valid penetration-prevention contact law and
        the only one P7-1 needs to demonstrate AC-2.
    """

    point: NDArray[np.float64]
    normal: NDArray[np.float64]
    restitution: float = 0.0

    def __post_init__(self) -> None:
        point = np.asarray(self.point, dtype=np.float64)
        normal = np.asarray(self.normal, dtype=np.float64)
        if point.shape != (3,):
            msg = f"RigidWallSpec.point must have shape (3,); got {point.shape}."
            raise ValueError(msg)
        if normal.shape != (3,):
            msg = f"RigidWallSpec.normal must have shape (3,); got {normal.shape}."
            raise ValueError(msg)
        norm = float(np.linalg.norm(normal))
        if norm <= 0.0:
            msg = "RigidWallSpec.normal must be non-zero."
            raise ValueError(msg)
        if not np.isclose(norm, 1.0, atol=1.0e-12):
            msg = (
                f"RigidWallSpec.normal must be a unit vector; "
                f"got ||normal||={norm:.6e}. Pass a unit-length vector or "
                f"normalise before constructing the wall."
            )
            raise ValueError(msg)
        if not (0.0 <= float(self.restitution) <= 1.0):
            msg = f"RigidWallSpec.restitution must be in [0, 1]; got {self.restitution}."
            raise ValueError(msg)
        # Normalise the stored arrays (frozen dataclass workaround).
        object.__setattr__(self, "point", point)
        object.__setattr__(self, "normal", normal)


# ---------------------------------------------------------------------------
# Reduced-Hex8 SVK internal force (centroid quadrature)
# ---------------------------------------------------------------------------


def _reduced_hex8_svk_internal_force(
    u_elem: NDArray[np.float64],
    X_elem: NDArray[np.float64],
    lam: float,
    mu: float,
) -> NDArray[np.float64]:
    """One-point centroid SVK internal force for a reduced Hex8 element.

    Mirrors the reference helper used in
    ``tests/test_hourglass_control.py::_one_point_svk_force``:

    - dN/dxi at the centroid (``shape_gradients(0,0,0)``)
    - J0 = X^T @ dN/dxi, dN/dX = dN/dxi @ J0^{-1}
    - F = I + grad_u, E = (F^T F - I) / 2
    - SVK PK2: ``S = lam tr(E) I + 2 mu E``, P = F @ S
    - 1-point rule, w_q = 8 (volume of [-1,1]^3)

    Parameters
    ----------
    u_elem
        Element nodal displacements, shape ``(8, 3)``.
    X_elem
        Element nodal reference coordinates, shape ``(8, 3)``.
    lam, mu
        Lamé parameters.

    Returns
    -------
    f_int : ndarray, shape (8, 3)
        Element internal force in the same sign convention as the rest of
        the codebase (resisting force; add to the residual).
    """
    dN_dxi = shape_gradients(0.0, 0.0, 0.0)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = (
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at element "
            f"centroid. Element inverted in the reference configuration."
        )
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv

    grad_u = u_elem.T @ dN_dX
    F = np.eye(3) + grad_u
    E = 0.5 * (F.T @ F - np.eye(3))
    tr_E = float(np.trace(E))
    S = lam * tr_E * np.eye(3) + 2.0 * mu * E
    P = F @ S
    f_int: NDArray[np.float64] = 8.0 * detJ0 * (dN_dX @ P.T)
    return f_int


def _assemble_internal_force(
    coords_ref: NDArray[np.float64],
    conn: NDArray[np.int64],
    u: NDArray[np.float64],
    lam: float,
    mu: float,
    lambda_h: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Assemble the global SVK + hourglass nodal internal force.

    Returns
    -------
    f_int : ndarray, shape (n_nodes, 3)
        Nodal internal force from reduced-Hex8 SVK at the centroid.
    f_hg : ndarray, shape (n_nodes, 3)
        Nodal hourglass force from FB stabilisation.

    The two components are returned separately so the caller can attribute
    work increments to internal vs hourglass energy, which AC-1 needs.
    """
    f_int = np.zeros_like(u, dtype=np.float64)
    f_hg = np.zeros_like(u, dtype=np.float64)
    for elem_nodes in conn:
        nodes = elem_nodes.astype(np.int64)
        X_e = coords_ref[nodes]
        u_e = u[nodes]
        f_int_e = _reduced_hex8_svk_internal_force(u_e, X_e, lam, mu)
        f_hg_e = flanagan_belytschko_force(u_e, X_e, mu=mu, lambda_h=lambda_h)
        for local_idx, n in enumerate(nodes):
            f_int[n] += f_int_e[local_idx]
            f_hg[n] += f_hg_e[local_idx]
    return f_int, f_hg


# ---------------------------------------------------------------------------
# Public runtime helpers
# ---------------------------------------------------------------------------


def init_taylor_runtime(
    mesh: BenchmarkMesh,
    *,
    rho: float,
    lam: float,
    mu: float,
    lambda_h: float = 0.05,
    initial_velocity: NDArray[np.float64] | None = None,
) -> ExplicitTaylorState:
    """Allocate the initial :class:`ExplicitTaylorState` for an explicit run.

    Parameters
    ----------
    mesh
        Source mesh. Must have ``element_type == 'hex8'`` (the only topology
        supported by :func:`compute_lumped_mass` in the MVP).
    rho
        Mass density (kg/m^3). Must be positive.
    lam, mu
        Lamé parameters (Pa). Stored on the state implicitly via subsequent
        :func:`explicit_step` calls — kept on the call surface so callers
        can pass them per-step if a future variant wants temperature- or
        history-dependent moduli.
    lambda_h
        Hourglass control coefficient (default 0.05, matches
        :func:`flanagan_belytschko_force` default).
    initial_velocity
        Optional initial nodal velocity field, shape ``(n_nodes, 3)``.
        ``None`` (default) yields a quiescent initial state.

    Returns
    -------
    ExplicitTaylorState
        Freshly allocated state with zero displacement / acceleration and
        the supplied (or zero) initial velocity. ``time`` and energies start
        at zero.
    """
    if mesh.element_type != "hex8":
        msg = (
            f"Taylor explicit runtime currently supports only Hex8 meshes; "
            f"got {mesh.element_type!r}."
        )
        raise ValueError(msg)

    # Explicitly silence unused-arg warnings — these participate in the
    # downstream :func:`explicit_step` interface but the validator
    # signature documents them here for self-consistency.
    del lam, mu, lambda_h

    coords = mesh.coordinates.copy()
    displacement = np.zeros_like(coords)
    if initial_velocity is None:
        velocity = np.zeros_like(coords)
    else:
        v0 = np.asarray(initial_velocity, dtype=np.float64)
        if v0.shape != coords.shape:
            msg = f"initial_velocity must have shape {coords.shape}; got {v0.shape}."
            raise ValueError(msg)
        velocity = v0.copy()
    acceleration = np.zeros_like(coords)

    mass = compute_lumped_mass(mesh.coordinates, mesh.connectivity, rho, ElementType.HEX8)

    return ExplicitTaylorState(
        mesh=mesh,
        coords=coords,
        displacement=displacement,
        velocity=velocity,
        acceleration=acceleration,
        mass=mass,
        time=0.0,
        internal_energy=0.0,
        hourglass_energy=0.0,
    )


def explicit_step(
    state: ExplicitTaylorState,
    *,
    dt: float,
    lam: float,
    mu: float,
    rho: float,
    lambda_h: float = 0.05,
    walls: tuple[RigidWallSpec, ...] = (),
) -> ExplicitTaylorState:
    """Advance the state by one central-difference explicit step.

    Pseudocode::

        f_int, f_HG <- assemble(coords_ref, u, lam, mu, lambda_h)
        a           <- -(f_int + f_HG) / m
        v           <- v + dt * a
        du          <- dt * v
        u           <- u + du
        coords      <- coords_ref + u
        contact     <- apply_rigid_wall_contact for each wall
        time        <- time + dt
        E_int       <- E_int + |f_int . du|
        E_hg        <- E_hg + |f_HG  . du|

    The energy bookkeeping uses the magnitude of ``f · du`` so the running
    quantities are non-negative and directly usable by the AC-1 boundedness
    test (a ratio test on dissipation budgets, not a signed work integral).

    Parameters
    ----------
    state
        Input state (mutated in place and returned).
    dt
        Time-step size. Must be positive. The caller is responsible for
        respecting the critical timestep (use
        :func:`mechdsl.solver.critical_timestep.critical_timestep`).
    lam, mu
        Lamé parameters used by the centroid SVK update and the hourglass
        stiffness scalar.
    rho
        Mass density. Currently unused (mass is precomputed at init) but
        kept on the signature so future variable-density variants do not
        need a breaking signature change. Pre-marked as ARG001 to satisfy
        ruff in the meantime.
    lambda_h
        Hourglass control coefficient (default 0.05).
    walls
        Tuple of rigid walls applied at the end of the step.

    Returns
    -------
    ExplicitTaylorState
        The updated state (same instance).
    """
    if dt <= 0.0:
        msg = f"dt must be positive; got {dt}."
        raise ValueError(msg)

    mesh = state.mesh
    coords_ref = mesh.coordinates
    conn = mesh.connectivity

    f_int, f_hg = _assemble_internal_force(coords_ref, conn, state.displacement, lam, mu, lambda_h)

    # Newton's second law with lumped diagonal mass.
    state.acceleration = -(f_int + f_hg) / state.mass

    # Forward-Euler velocity / position update (leapfrog kernel; first
    # step has v at t=0 so this reduces to central-difference for
    # subsequent steps once we treat velocity as half-step internally).
    state.velocity = state.velocity + dt * state.acceleration

    du = dt * state.velocity
    state.displacement = state.displacement + du
    state.coords = coords_ref + state.displacement

    for wall in walls:
        state = apply_rigid_wall_contact(state, wall)

    state.time = float(state.time) + float(dt)

    # Energy accumulation — use absolute work so the diagnostic stays a
    # non-negative dissipation budget (the energy-ratio acceptance test reads
    # it as a bound, not as a signed integral).
    state.internal_energy = float(state.internal_energy) + float(np.abs(np.sum(f_int * du)))
    state.hourglass_energy = float(state.hourglass_energy) + float(
        hourglass_energy_increment(du, f_hg)
    )

    return state


def apply_rigid_wall_contact(
    state: ExplicitTaylorState, wall: RigidWallSpec
) -> ExplicitTaylorState:
    """Clamp penetrating nodes to the wall plane and zero the inward velocity.

    Implements the simplest valid frictionless rigid-half-space contact:

    1. Per node, compute the signed distance to the wall along the wall
       normal: ``s = (x - point) . normal``.
    2. For nodes with ``s < 0`` (penetration), project the position onto
       the wall plane (``x' = x - s * normal``) and update the displacement
       so ``x' = X_ref + u'``.
    3. Zero the inward normal component of the velocity for those nodes
       (or reflect it if ``restitution > 0``). The tangential component
       is preserved (frictionless wall).

    Returns the same ``state`` instance (mutated in place).
    """
    point = wall.point
    normal = wall.normal

    # Signed distances of all nodes to the wall plane.
    rel = state.coords - point
    sd = rel @ normal

    pen_mask = sd < 0.0
    if not np.any(pen_mask):
        return state

    # 1) Position correction: x' = x - s n  (only for penetrating nodes)
    correction = sd[pen_mask, None] * normal[None, :]
    state.coords[pen_mask] -= correction
    state.displacement[pen_mask] -= correction

    # 2) Velocity correction: zero (or reflect) the inward normal component.
    v_pen = state.velocity[pen_mask]
    vn = v_pen @ normal
    inward = vn < 0.0  # nodes still moving into the wall
    if np.any(inward):
        idxs = np.where(pen_mask)[0][inward]
        v_inward = state.velocity[idxs]
        vn_inward = v_inward @ normal
        # Reflect with restitution e: v' = v - (1 + e) (v.n) n
        scale = 1.0 + float(wall.restitution)
        state.velocity[idxs] = v_inward - scale * vn_inward[:, None] * normal[None, :]

    return state


def hourglass_energy_increment(du: NDArray[np.float64], f_hg: NDArray[np.float64]) -> float:
    """Incremental hourglass work ``|f_HG . du|`` for one explicit step.

    The absolute value keeps the diagnostic strictly non-negative across
    sign-flipping oscillations (the AC-1 test uses it as a dissipation
    *budget*, not as a signed work integral).

    Parameters
    ----------
    du
        Nodal displacement increment for the step, shape ``(n_nodes, 3)``.
    f_hg
        Nodal hourglass force at the start of the step, shape
        ``(n_nodes, 3)``.

    Returns
    -------
    float
        Magnitude of the elementwise dot product ``sum f_HG_ai * du_ai``.
    """
    if du.shape != f_hg.shape:
        msg = f"du and f_hg shape mismatch: {du.shape} vs {f_hg.shape}."
        raise ValueError(msg)
    return float(np.abs(np.sum(f_hg * du)))


# ---------------------------------------------------------------------------
# Johnson-Cook explicit runtime
# ---------------------------------------------------------------------------


def _reduced_hex8_jc_internal_force(
    u_elem: NDArray[np.float64],
    X_elem: NDArray[np.float64],
    S: NDArray[np.float64],
) -> NDArray[np.float64]:
    """One-point centroid internal force for a reduced Hex8 with a given PK2.

    Mirrors :func:`_reduced_hex8_svk_internal_force` but takes the PK2 stress
    tensor ``S`` (3, 3) directly — letting the caller plug in any constitutive
    update (e.g. the Johnson-Cook radial return) without re-deriving the kine-
    matics. Centroid quadrature with weight ``w_q = 8``.

    Parameters
    ----------
    u_elem
        Element nodal displacements, shape ``(8, 3)``.
    X_elem
        Element nodal reference coordinates, shape ``(8, 3)``.
    S
        Second Piola-Kirchhoff stress tensor at the centroid, shape ``(3, 3)``.

    Returns
    -------
    f_int : ndarray, shape (8, 3)
        Element internal force in the same sign convention as the rest of
        the codebase (resisting force; add to the residual).
    """
    dN_dxi = shape_gradients(0.0, 0.0, 0.0)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = (
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at element "
            f"centroid. Element inverted in the reference configuration."
        )
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv

    grad_u = u_elem.T @ dN_dX
    F = np.eye(3) + grad_u
    P = F @ S
    f_int: NDArray[np.float64] = 8.0 * detJ0 * (dN_dX @ P.T)
    return f_int


def _centroid_green_lagrange(
    u_elem: NDArray[np.float64],
    X_elem: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Green-Lagrange strain ``E = 0.5 (F^T F - I)`` at the Hex8 centroid.

    Used by the JC explicit step to feed the per-element strain into
    :func:`mechdsl.symbolic.models.johnson_cook.radial_return`.
    """
    dN_dxi = shape_gradients(0.0, 0.0, 0.0)
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        msg = (
            f"Non-positive Jacobian determinant ({detJ0:.6e}) at element "
            f"centroid. Element inverted in the reference configuration."
        )
        raise ValueError(msg)
    J0_inv = np.linalg.inv(J0)
    dN_dX = dN_dxi @ J0_inv
    grad_u = u_elem.T @ dN_dX
    F = np.eye(3) + grad_u
    E: NDArray[np.float64] = 0.5 * (F.T @ F - np.eye(3))
    return E


def _assemble_internal_force_jc(
    coords_ref: NDArray[np.float64],
    conn: NDArray[np.int64],
    u: NDArray[np.float64],
    pk2_stress: NDArray[np.float64],
    mu: float,
    lambda_h: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Assemble the global JC + hourglass nodal internal force.

    The per-element PK2 stress array is supplied by the caller (computed
    upstream by the radial-return update). The hourglass stabilisation uses
    the JC elastic shear modulus ``mu``.

    Parameters
    ----------
    coords_ref
        Reference nodal coordinates, shape ``(n_nodes, 3)``.
    conn
        Element connectivity, shape ``(n_elem, 8)``.
    u
        Cumulative nodal displacement, shape ``(n_nodes, 3)``.
    pk2_stress
        Per-element PK2 stress at the centroid, shape ``(n_elem, 3, 3)``.
    mu
        Shear modulus for the FB hourglass scalar.
    lambda_h
        Hourglass control coefficient.

    Returns
    -------
    f_int : ndarray, shape (n_nodes, 3)
        Nodal internal force from the supplied per-element PK2 stress.
    f_hg : ndarray, shape (n_nodes, 3)
        Nodal hourglass force from FB stabilisation.
    """
    f_int = np.zeros_like(u, dtype=np.float64)
    f_hg = np.zeros_like(u, dtype=np.float64)
    for e, elem_nodes in enumerate(conn):
        nodes = elem_nodes.astype(np.int64)
        X_e = coords_ref[nodes]
        u_e = u[nodes]
        f_int_e = _reduced_hex8_jc_internal_force(u_e, X_e, pk2_stress[e])
        f_hg_e = flanagan_belytschko_force(u_e, X_e, mu=mu, lambda_h=lambda_h)
        for local_idx, n in enumerate(nodes):
            f_int[n] += f_int_e[local_idx]
            f_hg[n] += f_hg_e[local_idx]
    return f_int, f_hg


def init_taylor_runtime_jc(
    mesh: BenchmarkMesh,
    *,
    rho: float,
    jc_material: JohnsonCookMaterial,
    lambda_h: float = 0.05,
    initial_velocity: NDArray[np.float64] | None = None,
) -> ExplicitTaylorState:
    """Allocate the initial state for a Johnson-Cook Taylor explicit run.

    Mirrors :func:`init_taylor_runtime` but pre-allocates the per-element
    Johnson-Cook history arrays on ``state.material_state``:

    - ``"eqplas"`` (n_elem,): equivalent plastic strain, initialised to 0.0.
    - ``"temperature"`` (n_elem,): temperature (K), initialised to
      ``jc_material.T_ref``.
    - ``"pk2_stress"`` (n_elem, 3, 3): PK2 stress, initialised to zero.

    The elastic moduli used by the centroid quadrature and the FB hourglass
    scalar are taken from ``jc_material.lam`` / ``jc_material.mu``.

    Parameters
    ----------
    mesh
        Source mesh. Must have ``element_type == 'hex8'``.
    rho
        Mass density (kg/m^3). Must be positive.
    jc_material
        Johnson-Cook calibration. ``mat.lam`` / ``mat.mu`` provide the elastic
        constants used by the centroid kernel and the hourglass stabilisation.
    lambda_h
        Hourglass control coefficient (default 0.05).
    initial_velocity
        Optional initial nodal velocity field, shape ``(n_nodes, 3)``.

    Returns
    -------
    ExplicitTaylorState
        Freshly allocated state with zero displacement / acceleration, the
        supplied (or zero) initial velocity, and the JC history arrays
        attached to ``state.material_state``.
    """
    if mesh.element_type != "hex8":
        msg = (
            f"Taylor JC explicit runtime currently supports only Hex8 meshes; "
            f"got {mesh.element_type!r}."
        )
        raise ValueError(msg)

    state = init_taylor_runtime(
        mesh,
        rho=rho,
        lam=jc_material.lam,
        mu=jc_material.mu,
        lambda_h=lambda_h,
        initial_velocity=initial_velocity,
    )

    n_elem = mesh.n_elements
    state.material_state = {
        "eqplas": np.zeros(n_elem, dtype=np.float64),
        "temperature": np.full(n_elem, float(jc_material.T_ref), dtype=np.float64),
        "pk2_stress": np.zeros((n_elem, 3, 3), dtype=np.float64),
    }
    return state


def explicit_step_jc(
    state: ExplicitTaylorState,
    *,
    dt: float,
    jc_material: JohnsonCookMaterial,
    rho: float,
    lambda_h: float = 0.05,
    walls: tuple[RigidWallSpec, ...] = (),
) -> ExplicitTaylorState:
    """Advance the JC state by one central-difference explicit step.

    Per-element flow:

    1. Compute centroid Green-Lagrange strain ``E = 0.5 (F^T F - I)``.
    2. Call :func:`mechdsl.symbolic.models.johnson_cook.radial_return` with
       the cached ``eqplas`` and ``temperature`` to obtain the updated PK2
       stress, ``alpha_new``, and ``T_new``.
    3. Write ``stress``, ``alpha_new``, ``T_new`` back to
       ``state.material_state`` (in place).

    The element internal force then uses the freshly returned PK2 stress;
    the hourglass force uses ``jc_material.mu``. Velocity / position /
    energy / time updates follow the same leapfrog pattern as
    :func:`explicit_step` (absolute-work energy bookkeeping preserved).

    Parameters
    ----------
    state
        Input state (mutated in place and returned). Must have JC history
        arrays attached (typically by :func:`init_taylor_runtime_jc`).
    dt
        Time-step size. Must be positive (the JC return mapping itself
        rejects ``dt <= 0``).
    jc_material
        Johnson-Cook calibration.
    rho
        Mass density (kept for signature parity; mass is precomputed at
        init).
    lambda_h
        Hourglass control coefficient (default 0.05).
    walls
        Tuple of rigid walls applied at the end of the step.

    Returns
    -------
    ExplicitTaylorState
        The updated state (same instance).
    """
    del rho  # mass precomputed at init; kept for signature parity

    if dt <= 0.0:
        msg = f"dt must be positive; got {dt}."
        raise ValueError(msg)

    mesh = state.mesh
    coords_ref = mesh.coordinates
    conn = mesh.connectivity

    eqplas = state.material_state["eqplas"]
    temperature = state.material_state["temperature"]
    pk2 = state.material_state["pk2_stress"]

    # --- 1. Per-element JC return mapping at centroid ---
    for e, elem_nodes in enumerate(conn):
        nodes = elem_nodes.astype(np.int64)
        X_e = coords_ref[nodes]
        u_e = state.displacement[nodes]
        E_e = _centroid_green_lagrange(u_e, X_e)
        result = radial_return(
            jc_material,
            E_e,
            alpha_old=float(eqplas[e]),
            T_old=float(temperature[e]),
            dt=dt,
        )
        pk2[e] = result.stress
        eqplas[e] = result.alpha_new
        temperature[e] = result.T_new

    # --- 2. Internal + hourglass force assembly using the updated PK2 ---
    f_int, f_hg = _assemble_internal_force_jc(
        coords_ref, conn, state.displacement, pk2, jc_material.mu, lambda_h
    )

    # --- 3. Newton's second law with lumped diagonal mass ---
    state.acceleration = -(f_int + f_hg) / state.mass

    # --- 4. Leapfrog velocity / position update (matches explicit_step) ---
    state.velocity = state.velocity + dt * state.acceleration
    du = dt * state.velocity
    state.displacement = state.displacement + du
    state.coords = coords_ref + state.displacement

    for wall in walls:
        state = apply_rigid_wall_contact(state, wall)

    state.time = float(state.time) + float(dt)

    # --- 5. Energy bookkeeping (absolute work, matches explicit_step) ---
    state.internal_energy = float(state.internal_energy) + float(np.abs(np.sum(f_int * du)))
    state.hourglass_energy = float(state.hourglass_energy) + float(
        hourglass_energy_increment(du, f_hg)
    )

    return state


# ---------------------------------------------------------------------------
# Postprocessing helpers
# ---------------------------------------------------------------------------


def extract_equivalent_plastic_strain(state: ExplicitTaylorState) -> NDArray[np.float64]:
    """Return a copy of the per-element equivalent plastic strain.

    Returning a copy (not a view) guarantees that downstream consumers can
    mutate the returned array without disturbing the integrator state — a
    contract relied on by the postprocessing tests.

    Parameters
    ----------
    state
        Explicit state with a Johnson-Cook material history attached
        (typically allocated by :func:`init_taylor_runtime_jc`).

    Returns
    -------
    ndarray, shape (n_elem,)
        Equivalent plastic strain per element, dtype ``float64``.
    """
    if "eqplas" not in state.material_state:
        msg = (
            "state.material_state has no 'eqplas' key — was the state allocated "
            "via init_taylor_runtime_jc?"
        )
        raise KeyError(msg)
    return np.array(state.material_state["eqplas"], dtype=np.float64, copy=True)


def final_length(state: ExplicitTaylorState, *, axis: int = 2) -> float:
    """Deformed-bar extent along ``axis`` (deterministic).

    Computed as ``max(coords[:, axis]) - min(coords[:, axis])`` on the
    current deformed coordinates ``state.coords``. Bit-for-bit deterministic
    across calls (no random state, no dict iteration, no float-string
    roundtrip).

    Parameters
    ----------
    state
        Explicit state. ``state.coords`` is read; nothing is mutated.
    axis
        Spatial axis (0, 1, or 2). Defaults to 2 — the conventional Taylor
        impact axis for the bar mesh.

    Returns
    -------
    float
        Axial extent of the deformed bar.
    """
    if axis not in (0, 1, 2):
        msg = f"axis must be 0, 1, or 2; got {axis}."
        raise ValueError(msg)
    col = state.coords[:, axis]
    return float(col.max() - col.min())


def mushroom_radius(
    state: ExplicitTaylorState,
    *,
    axis: int = 2,
    face: str = "min",
    center: tuple[float, float] | None = None,
) -> float:
    """Maximum in-plane radius of the impact face in the deformed configuration.

    The conventional Taylor-impact "mushroom" diagnostic. The center is
    measured in the *reference* configuration so that a uniform translation
    of the bar does not shift the metric — the test reference relies on this
    invariance.

    Parameters
    ----------
    state
        Explicit state. ``state.coords`` (deformed) and ``state.mesh`` (refer-
        ence boundary set + reference coordinates) are read; nothing mutates.
    axis
        Bar axis (0, 1, or 2). Defaults to 2.
    face
        Either ``"min"`` or ``"max"``: which end of the bar along ``axis`` is
        the impact face. The boundary set is keyed
        ``f"{'xyz'[axis]}_{face}"`` on ``state.mesh.boundary_nodes``.
    center
        Optional ``(c0, c1)`` reference-frame centre about which to measure
        the in-plane radius (the two coordinates orthogonal to ``axis``). If
        ``None`` (default), the centre is taken to be the geometric centroid
        of the impact-face nodes in the *reference* configuration.

    Returns
    -------
    float
        Maximum radial distance of the impact-face nodes about ``center`` in
        the deformed configuration.
    """
    if axis not in (0, 1, 2):
        msg = f"axis must be 0, 1, or 2; got {axis}."
        raise ValueError(msg)
    if face not in ("min", "max"):
        msg = f"face must be 'min' or 'max'; got {face!r}."
        raise ValueError(msg)

    key = f"{'xyz'[axis]}_{face}"
    boundary = state.mesh.boundary_nodes
    if key not in boundary:
        msg = (
            f"mushroom_radius: mesh has no boundary set {key!r}. "
            f"Available sets: {sorted(boundary)}."
        )
        raise KeyError(msg)
    face_nodes = boundary[key]

    # The two in-plane axes (deterministic order: ascending).
    in_plane = tuple(a for a in (0, 1, 2) if a != axis)
    a0, a1 = in_plane

    if center is None:
        ref_face = state.mesh.coordinates[face_nodes]
        c0 = 0.5 * (float(ref_face[:, a0].min()) + float(ref_face[:, a0].max()))
        c1 = 0.5 * (float(ref_face[:, a1].min()) + float(ref_face[:, a1].max()))
    else:
        c0, c1 = float(center[0]), float(center[1])

    deformed_face = state.coords[face_nodes]
    dx = deformed_face[:, a0] - c0
    dy = deformed_face[:, a1] - c1
    return float(np.sqrt(dx * dx + dy * dy).max())
