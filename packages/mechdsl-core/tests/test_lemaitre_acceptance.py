"""Lemaitre damage model acceptance tests -- Phase 6 exit criterion.

Task P6-3: D=0 regression + notched bar verification (integration tier).

Two sub-deliverables:

1. ``test_lemaitre_at_zero_matches_j2_power_law_benchmark``: drive a small
   non-isotropic benchmark (tension + shear on a 2-element Hex8 bar) through
   BOTH the J2 power-law generated solver and the Lemaitre generated solver,
   with Lemaitre parameters chosen so damage can never activate (huge
   ``eps_D`` threshold), and assert the converged displacement fields match
   within 1e-8.  The non-isotropic stress state is deliberate: the Phase 2
   ``physics_error`` precedent showed that isotropic (pure uniaxial) tests
   mask formula errors in tangent/stress coupling.

2. ``test_notched_bar_damage_localises_at_notch_root``: build a small Hex8
   notched-bar mesh programmatically (rectangular bar with a semi-circular
   notch cut into one side), run damage evolution under displacement-controlled
   tension, and assert that ``argmax(D)`` sits within one element-hop of a
   notch-root element.  Mesh-dependence of the localisation is expected and
   is documented as the B9 nonlocal-regularisation follow-up.

Acceptance criteria (from ``dev/tasks/PLAN-B/json/P6-3.json``):
- Lemaitre at D=0 matches J2 power-law within 1e-8 on the shared benchmark.
- Notched bar: D localises at the notch root (max within 1 element of the
  geometric notch).

Notes
-----
- Both tests are marked ``slow`` because they drive full Taichi JIT compiles
  + Newton loops.  They run under ``uv run pytest ... -v`` explicitly (the
  fast suite excludes ``-m "not slow"``).
- Per the P6-2 Gate B forward-warnings, the tangent used by ``tangent_matvec``
  is the **undamaged J2** algorithmic tangent (Option A), so Newton drops
  from super-linear to sub-linear convergence when damage is actively
  evolving.  The notched-bar test therefore uses small strain increments
  (<=0.5 % per step) and a generous Newton iteration budget (>=30).
- All damage parameters (``S_d``, ``s_d``, ``eps_D``, ``D_crit``) are set
  EXPLICITLY on every ProblemIR — the emitter's silent fallback defaults
  would otherwise hide parameter-threading regressions.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mechdsl.codegen import compile as mechdsl_compile
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.solver.import_adapter import CGSolver

# ---------------------------------------------------------------------------
# Material parameters shared by both tests (steel-like, MPa/mm)
# ---------------------------------------------------------------------------

_E = 200.0e3  # MPa
_NU = 0.3
_SIGMA_Y0 = 200.0  # MPa
_K_HARD = 100.0
_N_HARD = 0.3

_LAM = _E * _NU / ((1.0 + _NU) * (1.0 - 2.0 * _NU))
_MU = _E / (2.0 * (1.0 + _NU))


# ---------------------------------------------------------------------------
# Problem-IR factories
# ---------------------------------------------------------------------------


def _make_j2_ir() -> ProblemIR:
    """Build a J2 power-law ProblemIR with the shared material set."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={
                "E": _E,
                "nu": _NU,
                "sigma_y0": _SIGMA_Y0,
                "K": _K_HARD,
                "n": _N_HARD,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


def _make_lemaitre_ir(
    *,
    S_d: float,
    s_d: float,
    eps_D: float,
    D_crit: float,
) -> ProblemIR:
    """Build a Lemaitre ProblemIR. All damage params MUST be set explicitly."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="lemaitre",
            params={
                "E": _E,
                "nu": _NU,
                "sigma_y0": _SIGMA_Y0,
                "K": _K_HARD,
                "n": _N_HARD,
                "S_d": S_d,
                "s_d": s_d,
                "eps_D": eps_D,
                "D_crit": D_crit,
            },
        ),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


# ---------------------------------------------------------------------------
# Generated-module loader
# ---------------------------------------------------------------------------


def _import_generated_module(source: str, tmp_path: Path, name: str):
    """Write generated source to ``tmp_path/{name}.py`` and import it."""
    mod_path = tmp_path / f"{name}.py"
    mod_path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, mod_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_mesh_into_module(mod, coords: np.ndarray, conn: np.ndarray) -> None:
    """Allocate Taichi fields and push mesh data into the generated module."""
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]
    mod.allocate_fields(n_nodes, n_elem)
    mod.x_ref.from_numpy(coords)
    for e in range(n_elem):
        for a in range(8):
            mod.elem_nodes[e, a] = int(conn[e, a])


# ---------------------------------------------------------------------------
# Mesh generation
# ---------------------------------------------------------------------------


def _build_hex8_block(
    nx: int,
    ny: int,
    nz: int,
    Lx: float,
    Ly: float,
    Lz: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Simple structured Hex8 mesh on [0,Lx]x[0,Ly]x[0,Lz].

    Mirrors the convention used by ``ref_hex8_elastic.generate_hex8_mesh``:
    k (z) varies slowest, j (y) next, i (x) fastest. Element node order
    follows the Hex8 CCW-bottom / CCW-top convention used everywhere else.
    """
    n_nodes = (nx + 1) * (ny + 1) * (nz + 1)
    coords = np.empty((n_nodes, 3), dtype=np.float64)
    idx = 0
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                coords[idx, 0] = i * Lx / nx
                coords[idx, 1] = j * Ly / ny
                coords[idx, 2] = k * Lz / nz
                idx += 1

    def node_id(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    n_elem = nx * ny * nz
    conn = np.empty((n_elem, 8), dtype=np.int64)
    e = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                conn[e] = [
                    node_id(i, j, k),
                    node_id(i + 1, j, k),
                    node_id(i + 1, j + 1, k),
                    node_id(i, j + 1, k),
                    node_id(i, j, k + 1),
                    node_id(i + 1, j, k + 1),
                    node_id(i + 1, j + 1, k + 1),
                    node_id(i, j + 1, k + 1),
                ]
                e += 1
    return coords, conn


def _build_notched_bar_mesh(
    n_len: int = 8,
    n_height: int = 4,
    n_thick: int = 1,
    L: float = 8.0,
    H: float = 4.0,
    T: float = 1.0,
    notch_depth: float = 1.0,
    notch_halfwidth: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a rectangular Hex8 bar with a semi-circular notch on the +y face.

    The undeformed bar spans ``[0, L] x [0, H] x [0, T]``.  A semi-circular
    notch is cut into the top face (y = H) centred at ``(L/2, H, T/2)`` with
    radius ``notch_depth`` (in y) and half-width ``notch_halfwidth`` (in x).

    The mesh is generated as a structured block and then deformed: every node
    whose original x-coordinate lies within the notch footprint has its
    y-coordinate pushed down by a smooth cosine profile that vanishes outside
    the notch and reaches ``notch_depth`` at the notch centre.  The y-push
    is scaled by ``(y / H)`` so only nodes near the top face are affected —
    nodes on the bottom face (y = 0) stay put.

    Returns
    -------
    coords : (n_nodes, 3)
        Deformed reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    notch_root_xyz : (3,)
        Coordinates of the notch-root point (geometric lowest point of the
        notch, on the mid-plane).
    """
    coords, conn = _build_hex8_block(n_len, n_height, n_thick, L, H, T)

    x_centre = L / 2.0
    # Cosine bell that is 1 at x=x_centre and 0 at |x-x_centre|>=notch_halfwidth.
    dx = coords[:, 0] - x_centre
    within = np.abs(dx) < notch_halfwidth
    bell = np.zeros(coords.shape[0], dtype=np.float64)
    bell[within] = 0.5 * (1.0 + np.cos(np.pi * dx[within] / notch_halfwidth))
    # Push is proportional to y/H so the bottom stays put, the top is pushed
    # down by ``notch_depth``.
    push = notch_depth * bell * (coords[:, 1] / H)
    coords[:, 1] -= push

    notch_root_xyz = np.array([x_centre, H - notch_depth, T / 2.0], dtype=np.float64)
    return coords, conn, notch_root_xyz


# ---------------------------------------------------------------------------
# Newton drivers (mirroring test_e2e_plastic.py)
# ---------------------------------------------------------------------------


def _newton_step_j2(
    mod,
    u: np.ndarray,
    bc_mask: np.ndarray,
    *,
    lam: float,
    mu: float,
    sigma_y0: float,
    K_hard: float,
    n_hard: float,
    tol: float = 1e-8,
    max_iter: int = 50,
) -> np.ndarray:
    """Run Newton to convergence for ONE J2 step.

    The generated J2 ``compute_internal_force`` mutates ``alpha`` in place;
    we snapshot alpha at entry and restore it before every residual
    evaluation (same pattern as ``test_e2e_plastic._newton_with_bc_plastic``).
    """
    n_nodes = u.shape[0]
    n_dof = n_nodes * 3
    bc_flat = bc_mask.ravel()

    alpha_snapshot = mod.alpha.to_numpy().copy()
    cg = CGSolver()
    R0_norm: float | None = None

    for newton_iter in range(max_iter):
        mod.alpha.from_numpy(alpha_snapshot)
        mod.u.from_numpy(u)
        mod.compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)
        f_int = mod.f_int.to_numpy()
        R = -f_int
        R[bc_mask] = 0.0
        R_flat = R.ravel()
        R_norm = float(np.linalg.norm(R_flat))
        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                break
        assert R0_norm is not None
        if R_norm < tol * max(R0_norm, 1.0):
            break

        def matvec(v_flat: np.ndarray, _u: np.ndarray = u) -> np.ndarray:
            v = v_flat.copy()
            v[bc_flat] = 0.0
            mod.u.from_numpy(_u)
            Kv = mod.tangent_matvec(v, lam, mu, sigma_y0, K_hard, n_hard)
            Kv[bc_flat] = v_flat[bc_flat]
            return Kv

        du_flat, _, _ = cg.solve(matvec, R_flat, np.zeros(n_dof, dtype=np.float64), 1e-10, 2000)
        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:
        mod.alpha.from_numpy(alpha_snapshot)
        raise RuntimeError(
            f"Newton did not converge after {max_iter} iters (J2). Final |R|={R_norm:.3e}"
        )

    mod.alpha.from_numpy(alpha_snapshot)
    mod.u.from_numpy(u)
    mod.compute_internal_force(lam, mu, sigma_y0, K_hard, n_hard)
    mod.u.from_numpy(u)
    return u


def _newton_step_lemaitre(
    mod,
    u: np.ndarray,
    bc_mask: np.ndarray,
    *,
    lam: float,
    mu: float,
    sigma_y0: float,
    K_hard: float,
    n_hard: float,
    S_d: float,
    s_d: float,
    eps_D: float,
    E_mod: float,
    nu_val: float,
    D_crit: float,
    tol: float = 1e-8,
    max_iter: int = 50,
) -> np.ndarray:
    """Run Newton to convergence for ONE Lemaitre step.

    Mirrors ``_newton_step_j2`` but threads the damage parameters into
    ``compute_internal_force`` and snapshots BOTH ``alpha`` and ``damage_D``
    (they are both mutated in-place by the generated kernel).
    ``tangent_matvec`` uses the undamaged J2 tangent (Option A, P6-1/P6-2).
    """
    n_nodes = u.shape[0]
    n_dof = n_nodes * 3
    bc_flat = bc_mask.ravel()

    alpha_snapshot = mod.alpha.to_numpy().copy()
    damage_snapshot = mod.damage_D.to_numpy().copy()
    cg = CGSolver()
    R0_norm: float | None = None
    R_norm = float("inf")

    for newton_iter in range(max_iter):
        mod.alpha.from_numpy(alpha_snapshot)
        mod.damage_D.from_numpy(damage_snapshot)
        mod.u.from_numpy(u)
        mod.compute_internal_force(
            lam,
            mu,
            sigma_y0,
            K_hard,
            n_hard,
            S_d,
            s_d,
            eps_D,
            E_mod,
            nu_val,
            D_crit,
        )
        f_int = mod.f_int.to_numpy()
        R = -f_int
        R[bc_mask] = 0.0
        R_flat = R.ravel()
        R_norm = float(np.linalg.norm(R_flat))
        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                break
        assert R0_norm is not None
        if R_norm < tol * max(R0_norm, 1.0):
            break

        def matvec(v_flat: np.ndarray, _u: np.ndarray = u) -> np.ndarray:
            v = v_flat.copy()
            v[bc_flat] = 0.0
            mod.u.from_numpy(_u)
            Kv = mod.tangent_matvec(v, lam, mu, sigma_y0, K_hard, n_hard)
            Kv[bc_flat] = v_flat[bc_flat]
            return Kv

        du_flat, _, _ = cg.solve(matvec, R_flat, np.zeros(n_dof, dtype=np.float64), 1e-10, 2000)
        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:
        mod.alpha.from_numpy(alpha_snapshot)
        mod.damage_D.from_numpy(damage_snapshot)
        raise RuntimeError(
            f"Newton did not converge after {max_iter} iters (Lemaitre). Final |R|={R_norm:.3e}"
        )

    mod.alpha.from_numpy(alpha_snapshot)
    mod.damage_D.from_numpy(damage_snapshot)
    mod.u.from_numpy(u)
    mod.compute_internal_force(
        lam,
        mu,
        sigma_y0,
        K_hard,
        n_hard,
        S_d,
        s_d,
        eps_D,
        E_mod,
        nu_val,
        D_crit,
    )
    mod.u.from_numpy(u)
    return u


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------


class TestTaskP6_3:
    """Phase 6 acceptance tests for Lemaitre damage model (P6-3)."""

    @pytest.mark.slow
    @pytest.mark.integration
    def test_lemaitre_at_zero_matches_j2_power_law_benchmark(self, tmp_path: Path) -> None:
        """Lemaitre with D-suppressing parameters reproduces J2 power-law.

        Strategy
        --------
        Drive a **non-isotropic** BVP (uniaxial x-tension + prescribed shear
        on the top face) on a 2x1x1 Hex8 bar through BOTH generated solvers.
        The Lemaitre model is configured with ``eps_D = 1e9`` (damage
        threshold unreachable) AND ``S_d = 1e9`` (damage-rate denominator
        astronomical).  Either knob alone suffices to keep ``D = 0``; using
        both is belt-and-braces.  Assert that the converged displacement
        fields agree within ``1e-8``.

        This is a *numerical* regression guard -- the structural one (J2
        inner kernel emitted byte-identically inside the Lemaitre source) is
        already covered by ``test_lemaitre_codegen.test_d_zero_matches_j2_emission``.
        """
        # --- Mesh: 2 x 1 x 1 Hex8 bar on [0,2] x [0,1] x [0,1] ---
        coords, conn = _build_hex8_block(nx=2, ny=1, nz=1, Lx=2.0, Ly=1.0, Lz=1.0)
        n_nodes = coords.shape[0]

        x_left = np.where(np.abs(coords[:, 0] - 0.0) < 1e-12)[0]
        x_right = np.where(np.abs(coords[:, 0] - 2.0) < 1e-12)[0]
        y_top = np.where(np.abs(coords[:, 1] - 1.0) < 1e-12)[0]

        # BC mask: left face fully fixed, right face x-disp prescribed,
        # top face z-disp prescribed (shear in the xz plane).
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_mask[x_left, :] = True
        bc_mask[x_right, 0] = True
        bc_mask[y_top, 2] = True

        total_ux = 0.006  # ~3x yield strain over length 2
        total_uz = 0.002  # shear component on top face
        n_steps = 4

        # --- Compile + run J2 ---
        j2_bundle = mechdsl_compile(_make_j2_ir())
        j2_mod = _import_generated_module(j2_bundle.emitted_source, tmp_path, "gen_j2_p6_3")
        _load_mesh_into_module(j2_mod, coords, conn)

        u_j2 = np.zeros((n_nodes, 3), dtype=np.float64)
        j2_mod.u.from_numpy(u_j2)
        for step in range(1, n_steps + 1):
            frac = step / n_steps
            u_j2[x_left, :] = 0.0
            u_j2[x_right, 0] = frac * total_ux
            u_j2[y_top, 2] = frac * total_uz
            j2_mod.u.from_numpy(u_j2)
            u_j2 = _newton_step_j2(
                j2_mod,
                u_j2,
                bc_mask,
                lam=_LAM,
                mu=_MU,
                sigma_y0=_SIGMA_Y0,
                K_hard=_K_HARD,
                n_hard=_N_HARD,
            )

        # --- Compile + run Lemaitre with damage suppressed ---
        # Huge eps_D means alpha never crosses the damage-nucleation
        # threshold; huge S_d makes (Y/S_d)^s_d vanish even if it did.
        lem_ir = _make_lemaitre_ir(S_d=1.0e9, s_d=1.0, eps_D=1.0e9, D_crit=0.95)
        lem_bundle = mechdsl_compile(lem_ir)
        lem_mod = _import_generated_module(lem_bundle.emitted_source, tmp_path, "gen_lem_p6_3_d0")
        _load_mesh_into_module(lem_mod, coords, conn)

        u_lem = np.zeros((n_nodes, 3), dtype=np.float64)
        lem_mod.u.from_numpy(u_lem)
        for step in range(1, n_steps + 1):
            frac = step / n_steps
            u_lem[x_left, :] = 0.0
            u_lem[x_right, 0] = frac * total_ux
            u_lem[y_top, 2] = frac * total_uz
            lem_mod.u.from_numpy(u_lem)
            u_lem = _newton_step_lemaitre(
                lem_mod,
                u_lem,
                bc_mask,
                lam=_LAM,
                mu=_MU,
                sigma_y0=_SIGMA_Y0,
                K_hard=_K_HARD,
                n_hard=_N_HARD,
                S_d=1.0e9,
                s_d=1.0,
                eps_D=1.0e9,
                E_mod=_E,
                nu_val=_NU,
                D_crit=0.95,
            )

        # Verify D actually stayed at 0 (otherwise the test is a tautology)
        D_max = float(np.max(lem_mod.damage_D.to_numpy()))
        assert D_max == 0.0, (
            f"Lemaitre damage must remain exactly zero for the regression, got max D={D_max:.3e}"
        )
        # And no elements were flagged as deleted
        assert int(np.max(lem_mod.is_deleted.to_numpy())) == 0

        # --- Compare displacements ---
        max_diff = float(np.max(np.abs(u_lem - u_j2)))
        assert max_diff < 1e-8, (
            f"Lemaitre (D=0) vs J2 displacement mismatch: max |u_lem - u_j2| = "
            f"{max_diff:.3e}, tolerance = 1e-8"
        )

    @pytest.mark.slow
    @pytest.mark.integration
    def test_notched_bar_damage_localises_at_notch_root(self, tmp_path: Path) -> None:
        """Notched tension bar: damage concentrates at the notch root.

        Strategy
        --------
        Build a small rectangular Hex8 bar with a semi-circular notch cut
        into the top face.  Load it in x-tension (displacement-controlled)
        past yield in small increments (<= 0.5% strain/step) so the
        undamaged-J2 tangent still delivers acceptable Newton convergence
        (P6-2 Gate B forward-warning #2).  After loading, reduce
        ``damage_D`` over the quadrature axis (max per element) and assert
        that the ``argmax`` element is within one face-neighbour hop of a
        notch-root element (i.e. the element directly under the notch on
        the mid-plane).
        """
        # --- Build mesh (coarse, on purpose -- fewer Newton cycles) ---
        n_len = 6
        n_height = 3
        n_thick = 1
        L, H, T = 6.0, 3.0, 1.0
        notch_depth = 0.75
        notch_halfwidth = 1.0

        coords, conn, notch_root_xyz = _build_notched_bar_mesh(
            n_len=n_len,
            n_height=n_height,
            n_thick=n_thick,
            L=L,
            H=H,
            T=T,
            notch_depth=notch_depth,
            notch_halfwidth=notch_halfwidth,
        )
        n_nodes = coords.shape[0]
        n_elem = conn.shape[0]

        # Element centroids for geometric queries
        centroids = coords[conn].mean(axis=1)  # (n_elem, 3)

        # --- BCs: left face (x=0) clamped, right face (x=L) prescribed x-disp ---
        x_left = np.where(np.abs(coords[:, 0] - 0.0) < 1e-12)[0]
        x_right = np.where(np.abs(coords[:, 0] - L) < 1e-12)[0]
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_mask[x_left, :] = True
        bc_mask[x_right, 0] = True

        # --- Loading: small strain increments (<=0.5%/step) so the undamaged
        #     J2 tangent (Option A, Gate B forward-warning #2) can still
        #     drive Newton to convergence under active damage. ---
        target_eng_strain = 0.02  # 2 % engineering strain
        total_disp = target_eng_strain * L
        n_steps = 8  # 0.25 % strain / step

        # --- Compile Lemaitre with active damage. ---
        # Use n_hard = 1.0 (LINEAR hardening). The J2 power-law
        # consistent algorithmic tangent hits a d(alpha^n)/d(alpha)
        # = n*alpha^(n-1) term that is singular as alpha -> 0 when
        # n < 1 (the class-level _N_HARD=0.3 exhibits this); under
        # sub-linear Newton driven by the undamaged-J2 tangent under
        # active damage, intermediate iterates can transiently produce
        # small but nonzero alpha and the tangent blows up.  n = 1.0
        # keeps every Jacobian entry well-defined.
        n_hard_notch = 1.0
        S_d = 2.0  # damage denominator (MPa) -- modest value
        s_d = 1.0  # linear damage evolution
        eps_D = 0.0  # damage active as soon as alpha > 0
        D_crit = 0.95

        lem_ir = ProblemIR(
            dim=3,
            formulation=Formulation.TOTAL_LAGRANGIAN,
            element_type=ElementType.HEX8,
            material=MaterialSpec(
                model="lemaitre",
                params={
                    "E": _E,
                    "nu": _NU,
                    "sigma_y0": _SIGMA_Y0,
                    "K": _K_HARD,
                    "n": n_hard_notch,
                    "S_d": S_d,
                    "s_d": s_d,
                    "eps_D": eps_D,
                    "D_crit": D_crit,
                },
            ),
            boundaries=(
                BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
                BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
            ),
        )
        bundle = mechdsl_compile(lem_ir)
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_lem_p6_3_notch")
        _load_mesh_into_module(mod, coords, conn)

        # --- Load stepping ---
        u = np.zeros((n_nodes, 3), dtype=np.float64)
        mod.u.from_numpy(u)
        for step in range(1, n_steps + 1):
            frac = step / n_steps
            u[x_left, :] = 0.0
            u[x_right, 0] = frac * total_disp
            mod.u.from_numpy(u)
            u = _newton_step_lemaitre(
                mod,
                u,
                bc_mask,
                lam=_LAM,
                mu=_MU,
                sigma_y0=_SIGMA_Y0,
                K_hard=_K_HARD,
                n_hard=n_hard_notch,
                S_d=S_d,
                s_d=s_d,
                eps_D=eps_D,
                E_mod=_E,
                nu_val=_NU,
                D_crit=D_crit,
                tol=1e-7,
                max_iter=40,  # >= 30 per Gate B guidance
            )

        # --- Extract per-element damage (max over QPs) ---
        damage_qp = mod.damage_D.to_numpy()  # (n_elem, n_qp)
        assert damage_qp.shape == (n_elem, 8)
        damage_elem = damage_qp.max(axis=1)

        # Sanity: damage actually grew somewhere (otherwise the test is vacuous)
        D_max = float(damage_elem.max())
        assert D_max > 0.0, f"No damage accumulated; test is vacuous (D_max={D_max:.3e})"

        # --- Identify notch-root elements (those touching the notch arc) ---
        # A "notch-root element" is the element whose centroid is closest to
        # ``notch_root_xyz`` (the geometric bottom of the notch).
        d_to_root = np.linalg.norm(centroids - notch_root_xyz, axis=1)
        notch_root_elem = int(np.argmin(d_to_root))

        # The "within 1 element" set is {notch_root_elem} plus every element
        # whose centroid is within ~1 element spacing (h) of the notch root.
        # We use the element edge-length along x (h = L/n_len) as the scale.
        h = max(L / n_len, H / n_height, T / n_thick)
        near_root = np.where(d_to_root <= 1.5 * h)[0]

        argmax_elem = int(np.argmax(damage_elem))

        # --- Assert: damage peak is within 1 element of the notch root ---
        assert argmax_elem in set(near_root.tolist()), (
            f"Damage did not localise at the notch root.\n"
            f"  argmax element = {argmax_elem} at centroid {centroids[argmax_elem]}"
            f" (D = {damage_elem[argmax_elem]:.3e})\n"
            f"  notch-root element = {notch_root_elem} at centroid "
            f"{centroids[notch_root_elem]} (D = {damage_elem[notch_root_elem]:.3e})\n"
            f"  notch-root geometric point = {notch_root_xyz}\n"
            f"  near-root elements = {near_root.tolist()}\n"
            f"  distance(argmax -> notch root) = "
            f"{d_to_root[argmax_elem]:.3f}  (threshold 1.5*h = {1.5 * h:.3f})\n"
            f"  per-element D = {damage_elem.tolist()}"
        )

        # --- Bonus assertion: D at argmax strictly greater than D at the
        #     farthest element from the notch -- damage drops off with distance. ---
        far_elem = int(np.argmax(d_to_root))
        assert damage_elem[argmax_elem] > damage_elem[far_elem], (
            f"Damage does not drop off with distance from the notch:\n"
            f"  D(argmax e={argmax_elem}) = {damage_elem[argmax_elem]:.3e}\n"
            f"  D(far    e={far_elem}) = {damage_elem[far_elem]:.3e}"
        )
