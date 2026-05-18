"""Simo and Hughes (1998) necking bar benchmark harness (P10-6).

This module wraps the existing TL + J2 + Hex8 necking bar benchmark from
`tests/test_benchmarks.py::TestNeckingBar` into a reusable harness function
that returns a `BenchmarkResult` consistent with the P10-4 pathfinder
(`mechdsl.verify.benchmarks._core.BenchmarkResult`).
The default TL Hex8 path remains the committed golden regression. The UL Hex8
cell is enabled through the same injected reference solve and tagged as an
updated-Lagrangian matrix cell, while lightweight prescribed-displacement smoke
support exercises the Phase 10 J2 assembly helper for finite history checks.

Reference
---------
The load-displacement curve is compared against a committed golden file
(`tests/golden/necking_bar_reference.npz`) generated from the same handwritten
plastic reference kernel. The 2% tolerance is the MVP acceptance criterion
from Simo and Hughes (1998), Chapter 4, and from
dev/design_docs/07-CONVENTIONS.md section 6.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.solver.mesh_io import generate_necking_bar_mesh
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
from mechdsl.verify.benchmarks._core import BenchmarkResult
from mechdsl.verify.benchmarks._j2_solver import (
    J2BenchmarkHistory,
    assemble_internal_force_j2,
    assert_monotonic_plastic_history,
)
from mechdsl.verify.benchmarks._meshes import BenchmarkMesh

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.solver.import_adapter import LinearSolverInterface

# Callable type matching tests.ref.ref_hex8_plastic public API. Injected by the
# caller so this module stays free of any tests.* import.
_AssembleFn = Callable[..., "NDArray"]
_ApplyDirichletFn = Callable[..., "NDArray"]
_ApplyTangentFn = Callable[..., "NDArray"]
NeckingFormulation = Literal["total_lagrangian", "updated_lagrangian"]


@dataclass(frozen=True)
class NeckingBarParameters:
    """Problem parameters matching the Simo and Hughes (1998) golden setup.

    The default values correspond exactly to the
    `tests/golden/necking_bar_reference.npz` snapshot and must not be changed
    without regenerating the golden file.
    """

    formulation: NeckingFormulation = "total_lagrangian"

    # Mesh
    nx: int = 2
    ny: int = 2
    nz: int = 8
    L: float = 20.0
    W: float = 2.0
    imperfection: float = 0.005

    # Material (steel-like, Simo and Hughes Ch. 4)
    E: float = 206.9e3  # MPa
    nu: float = 0.29
    sigma_y0: float = 450.0  # MPa
    K: float = 129.24  # MPa, power-law prefactor
    n: float = 0.1  # power-law exponent

    # Loading
    final_disp: float = 1.0  # mm
    n_steps: int = 10
    smoke_final_disp: float = 0.02  # mm, used by benchmark-local history smoke checks

    # Solver tolerances
    newton_tol: float = 1e-8
    newton_max_iter: int = 50
    cg_tol: float = 1e-10
    cg_max_iter: int = 5000


def run_necking_bar_benchmark(
    *,
    params: NeckingBarParameters | None = None,
    assemble_internal_force_plastic: _AssembleFn | None = None,
    apply_dirichlet: _ApplyDirichletFn | None = None,
    apply_tangent_matvec_plastic: _ApplyTangentFn | None = None,
    history_factory: Callable[[int], object] | None = None,
    cg_solver: LinearSolverInterface | None = None,
) -> BenchmarkResult:
    """Run a TL/UL + J2 + Hex8 necking-bar benchmark cell.

    The handwritten reference kernel is injected (not imported) so this
    production module has no dependency on the tests package. If those injected
    pieces are omitted, the function falls back to a lightweight
    prescribed-displacement smoke path that exercises the benchmark-local J2
    assembly layer.

    Parameters
    ----------
    params
        Problem parameters. Defaults match the committed golden snapshot.
    assemble_internal_force_plastic, apply_dirichlet,
    apply_tangent_matvec_plastic, history_factory
        Injected from tests.ref.ref_hex8_plastic.
    cg_solver
        Object exposing ``solve(matvec, b, x0, tol, max_iter)``.

    Returns
    -------
    BenchmarkResult
        ``extras`` contains:
          - ``force_history``: reaction force at z0 face per step (n_steps,)
          - ``disp_history``: prescribed displacement per step (n_steps,)
          - ``residual_history``: Newton residuals per step (list of lists)
          - ``z0_nodes``, ``z1_nodes``: boundary node index arrays
    """
    if params is None:
        params = NeckingBarParameters()
    _validate_params(params)

    if _has_reference_solver(
        assemble_internal_force_plastic=assemble_internal_force_plastic,
        apply_dirichlet=apply_dirichlet,
        apply_tangent_matvec_plastic=apply_tangent_matvec_plastic,
        history_factory=history_factory,
        cg_solver=cg_solver,
    ):
        assert assemble_internal_force_plastic is not None
        assert apply_dirichlet is not None
        assert apply_tangent_matvec_plastic is not None
        assert history_factory is not None
        assert cg_solver is not None
        return _run_reference_necking(
            params=params,
            assemble_internal_force_plastic=assemble_internal_force_plastic,
            apply_dirichlet=apply_dirichlet,
            apply_tangent_matvec_plastic=apply_tangent_matvec_plastic,
            history_factory=history_factory,
            cg_solver=cg_solver,
        )

    return _run_prescribed_necking_smoke(params)


def _run_reference_necking(
    *,
    params: NeckingBarParameters,
    assemble_internal_force_plastic: _AssembleFn,
    apply_dirichlet: _ApplyDirichletFn,
    apply_tangent_matvec_plastic: _ApplyTangentFn,
    history_factory: Callable[[int], object],
    cg_solver: LinearSolverInterface,
) -> BenchmarkResult:
    """Run the injected Hex8 reference solve for a TL/UL matrix cell."""

    mesh = generate_necking_bar_mesh(
        params.nx,
        params.ny,
        params.nz,
        L=params.L,
        W=params.W,
        imperfection=params.imperfection,
    )
    coords = mesh.coords
    conn = mesh.connectivity
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]

    mat = J2PowerLawMaterial(
        E=params.E,
        nu=params.nu,
        sigma_y0=params.sigma_y0,
        K=params.K,
        n=params.n,
    )

    x0_nodes = mesh.boundary_tags["x0"]
    y0_nodes = mesh.boundary_tags["y0"]
    z0_nodes = mesh.boundary_tags["z0"]
    z1_nodes = mesh.boundary_tags["z1"]

    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    bc_mask[x0_nodes, 0] = True
    bc_mask[y0_nodes, 1] = True
    bc_mask[z0_nodes, 2] = True
    bc_mask[z1_nodes, 2] = True
    bc_values[z1_nodes, 2] = params.final_disp

    u = np.zeros((n_nodes, 3), dtype=np.float64)
    history = history_factory(n_elem)
    ndof = n_nodes * 3

    n_steps = params.n_steps
    force_history = np.zeros(n_steps, dtype=np.float64)
    disp_history = np.zeros(n_steps, dtype=np.float64)
    residual_history: list[list[float]] = []

    t0 = time.perf_counter()
    total_newton_iters = 0

    for step in range(1, n_steps + 1):
        load_fraction = step / n_steps
        prescribed_uz = load_fraction * params.final_disp
        bc_values_step = load_fraction * bc_values

        u = apply_dirichlet(u, bc_mask, bc_values_step)

        step_residuals: list[float] = []
        R0_norm: float | None = None

        for newton_iter in range(params.newton_max_iter):
            f_int = assemble_internal_force_plastic(u, coords, conn, mat, history)
            R = -f_int
            R[bc_mask] = 0.0
            R_norm = float(np.linalg.norm(R))
            step_residuals.append(R_norm)

            if newton_iter == 0:
                R0_norm = R_norm
                if R0_norm < 1e-15:
                    break
            assert R0_norm is not None
            if R_norm < params.newton_tol * R0_norm:
                break

            def matvec(v_flat: NDArray, _u: NDArray = u) -> NDArray:
                v = v_flat.reshape((n_nodes, 3))
                Kv = apply_tangent_matvec_plastic(_u, v, coords, conn, mat, history, bc_mask)
                return Kv.ravel()

            du_flat, _, _ = cg_solver.solve(
                matvec,
                R.ravel(),
                np.zeros(ndof, dtype=np.float64),
                params.cg_tol,
                params.cg_max_iter,
            )
            du = du_flat.reshape((n_nodes, 3))
            du[bc_mask] = 0.0
            u = u + du
            total_newton_iters += 1
        else:
            history.rollback()  # type: ignore[attr-defined]
            msg = (
                f"Newton did not converge at step {step}/{n_steps}. "
                f"|R0|={step_residuals[0]:.3e}, |R_final|={step_residuals[-1]:.3e}"
            )
            raise RuntimeError(msg)

        f_int_conv = assemble_internal_force_plastic(u, coords, conn, mat, history)
        reaction_z = float(np.sum(f_int_conv[z0_nodes, 2]))

        history.commit()  # type: ignore[attr-defined]
        residual_history.append(step_residuals)
        force_history[step - 1] = reaction_z
        disp_history[step - 1] = prescribed_uz

    wallclock_s = time.perf_counter() - t0

    extras: dict = {
        "force_history": force_history,
        "disp_history": disp_history,
        "residual_history": residual_history,
        "formulation": params.formulation,
        "element_type": "hex8",
        "matrix_mode": "hex8_reference",
        "z0_nodes": z0_nodes,
        "z1_nodes": z1_nodes,
        "n_steps": n_steps,
        "n_nodes": n_nodes,
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=total_newton_iters,
        wallclock_s=wallclock_s,
        extras=extras,
    )


def _run_prescribed_necking_smoke(params: NeckingBarParameters) -> BenchmarkResult:
    """Run a cheap necking-bar history update through Phase 10 J2 helpers."""

    raw_mesh = generate_necking_bar_mesh(
        params.nx,
        params.ny,
        params.nz,
        L=params.L,
        W=params.W,
        imperfection=params.imperfection,
    )
    mesh = BenchmarkMesh(
        element_type="hex8",
        coordinates=raw_mesh.coords,
        connectivity=raw_mesh.connectivity,
        boundary_nodes=dict(raw_mesh.boundary_tags),
    )
    n_nodes = mesh.n_nodes

    mat = J2PowerLawMaterial(
        E=params.E,
        nu=params.nu,
        sigma_y0=params.sigma_y0,
        K=params.K,
        n=params.n,
    )
    history = J2BenchmarkHistory.zeros_for_mesh(mesh)
    u = np.zeros((n_nodes, 3), dtype=np.float64)
    z0_nodes = mesh.boundary_nodes["z0"]
    z1_nodes = mesh.boundary_nodes["z1"]

    force_history = np.zeros(params.n_steps, dtype=np.float64)
    disp_history = np.zeros(params.n_steps, dtype=np.float64)
    residual_history: list[list[float]] = []

    t0 = time.perf_counter()
    f_int = np.zeros_like(u)
    for step in range(1, params.n_steps + 1):
        load_fraction = step / params.n_steps
        prescribed_uz = load_fraction * params.smoke_final_disp
        u_step = np.zeros_like(u)
        u_step[z1_nodes, 2] = prescribed_uz

        f_int = assemble_internal_force_j2(
            mesh,
            u_step,
            mat,
            history,
            formulation=params.formulation,
        )
        assert_monotonic_plastic_history(history)
        history.commit()

        u = u_step
        force_history[step - 1] = float(np.sum(f_int[z0_nodes, 2]))
        disp_history[step - 1] = prescribed_uz
        residual_history.append([float(np.linalg.norm(f_int))])

    wallclock_s = time.perf_counter() - t0
    max_alpha = float(np.max(history.alpha_old)) if history.alpha_old.size else 0.0
    extras: dict = {
        "force_history": force_history,
        "disp_history": disp_history,
        "residual_history": residual_history,
        "formulation": params.formulation,
        "element_type": "hex8",
        "matrix_mode": "prescribed_displacement",
        "z0_nodes": z0_nodes,
        "z1_nodes": z1_nodes,
        "n_steps": params.n_steps,
        "n_nodes": n_nodes,
        "max_alpha": max_alpha,
        "history_shape": history.alpha_old.shape,
        "force_norm": float(np.linalg.norm(f_int)),
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=0,
        wallclock_s=wallclock_s,
        extras=extras,
    )


def _has_reference_solver(
    *,
    assemble_internal_force_plastic: _AssembleFn | None,
    apply_dirichlet: _ApplyDirichletFn | None,
    apply_tangent_matvec_plastic: _ApplyTangentFn | None,
    history_factory: Callable[[int], object] | None,
    cg_solver: LinearSolverInterface | None,
) -> bool:
    pieces = (
        assemble_internal_force_plastic,
        apply_dirichlet,
        apply_tangent_matvec_plastic,
        history_factory,
        cg_solver,
    )
    return all(piece is not None for piece in pieces)


def _validate_params(params: NeckingBarParameters) -> None:
    if params.formulation not in ("total_lagrangian", "updated_lagrangian"):
        raise ValueError(f"Unsupported necking formulation {params.formulation!r}")
    if params.n_steps <= 0:
        raise ValueError("n_steps must be positive")
    if params.final_disp <= 0.0:
        raise ValueError("final_disp must be positive")
    if params.smoke_final_disp <= 0.0:
        raise ValueError("smoke_final_disp must be positive")
