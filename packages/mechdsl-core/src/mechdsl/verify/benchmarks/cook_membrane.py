"""de Souza Neto et al. (2008) Cook's membrane benchmark harness (P10-3).

This module wraps the existing Hex8 Cook's membrane regression in a reusable
benchmark function and widens the original-scope matrix to
`{TL, UL} x {Hex8, Tet10}`. Hex8 cells can use the injected handwritten
reference solve; Tet10 cells use the benchmark-local Phase 10 J2 assembly layer
with a prescribed load-face displacement smoke path.

Reference
---------
The mesh, load case, and material parameters follow the existing Cook's
membrane regression in `tests/test_benchmarks.py` and the helper script
`tests/_gen_cooks_ref.py`. The benchmark target is the committed self-consistent
`2x2x1` Hex8 tip displacement reference `4.6999070649`, compared with a 2%
tolerance in the task test.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.solver.mesh_io import generate_cook_membrane_mesh
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
from mechdsl.verify.benchmarks._core import BenchmarkResult
from mechdsl.verify.benchmarks._j2_solver import (
    J2BenchmarkHistory,
    assemble_internal_force_j2,
    assert_monotonic_plastic_history,
)
from mechdsl.verify.benchmarks._meshes import cook_membrane_mesh

if TYPE_CHECKING:
    from numpy.typing import NDArray


_SolvePlasticFn = Callable[..., tuple["NDArray", object, list[list[float]]]]
CookFormulation = Literal["total_lagrangian", "updated_lagrangian"]
CookElementType = Literal["hex8", "tet10"]


@dataclass(frozen=True)
class CookMembraneParameters:
    """Cook's membrane setup with backward-compatible Hex8 defaults."""

    formulation: CookFormulation = "total_lagrangian"
    element_type: CookElementType = "hex8"

    # Mesh
    nx: int = 2
    ny: int = 2
    nz: int = 1

    # Material (de Souza Neto et al. benchmark parameters)
    E: float = 240.565
    nu: float = 0.3
    sigma_y0: float = 243.0
    K: float = 300.0
    n: float = 0.4

    # Loading
    total_shear: float = 100.0
    n_steps: int = 10

    # Solver tolerances
    newton_tol: float = 1e-6
    newton_max_iter: int = 100
    cg_tol: float = 1e-10
    cg_max_iter: int = 2000

    # Regression target from tests/_gen_cooks_ref.py and test_benchmarks.py
    reference_tip_uy: float = 4.6999070649

    # Smoke displacement used for non-reference matrix cells.
    matrix_tip_uy: float = 0.02


def run_cook_membrane_benchmark(
    *,
    params: CookMembraneParameters | None = None,
    solve_plastic: _SolvePlasticFn | None = None,
) -> BenchmarkResult:
    """Run a Cook's membrane matrix cell and return benchmark-style data.

    For Hex8 cells, callers may inject the handwritten plastic reference solver
    so the production module stays free of `tests.*` imports. Tet10 cells use a
    prescribed-displacement smoke path through the benchmark-local J2 assembly
    helper, which keeps the original matrix active without changing shared
    benchmark result schemas.
    """
    if params is None:
        params = CookMembraneParameters()
    _validate_params(params)

    if params.element_type == "hex8" and solve_plastic is not None:
        return _run_hex8_reference(params, solve_plastic)

    return _run_prescribed_matrix_cell(params)


def _run_hex8_reference(params: CookMembraneParameters, solve_plastic: _SolvePlasticFn) -> BenchmarkResult:
    """Run the legacy Hex8 reference solve for a Cook matrix cell."""

    mesh = generate_cook_membrane_mesh(params.nx, params.ny, params.nz)
    mat = J2PowerLawMaterial(
        E=params.E,
        nu=params.nu,
        sigma_y0=params.sigma_y0,
        K=params.K,
        n=params.n,
    )

    bc_mask = np.zeros((mesh.n_nodes, 3), dtype=bool)
    bc_values = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    bc_mask[mesh.boundary_tags["x0"], :] = True

    f_ext = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    right_nodes = mesh.boundary_tags["x1"]
    force_per_node = params.total_shear / len(right_nodes)
    f_ext[right_nodes, 1] = force_per_node

    t0 = time.perf_counter()
    u, history, residual_history = solve_plastic(
        mesh.coords,
        mesh.connectivity,
        mat,
        bc_mask,
        bc_values,
        f_ext,
        n_steps=params.n_steps,
        tol=params.newton_tol,
        max_iter=params.newton_max_iter,
        cg_tol=params.cg_tol,
        cg_max_iter=params.cg_max_iter,
    )
    wallclock_s = time.perf_counter() - t0

    tip_uy = float(u[right_nodes, 1].mean())
    rel_error = abs(tip_uy - params.reference_tip_uy) / abs(params.reference_tip_uy)
    total_newton_iters = sum(max(len(step_res) - 1, 0) for step_res in residual_history)

    max_alpha = None
    alpha_old = getattr(history, "alpha_old", None)
    if alpha_old is not None:
        max_alpha = float(np.max(alpha_old))

    extras = {
        "tip_uy": tip_uy,
        "reference_tip_uy": params.reference_tip_uy,
        "relative_error": rel_error,
        "formulation": params.formulation,
        "element_type": params.element_type,
        "matrix_mode": "hex8_reference",
        "residual_history": residual_history,
        "right_nodes": right_nodes,
        "n_steps": params.n_steps,
        "newton_tol": params.newton_tol,
        "mesh_shape": (params.nx, params.ny, params.nz),
        "mesh_n_nodes": mesh.n_nodes,
        "mesh_n_elem": mesh.n_elem,
        "max_alpha": max_alpha,
    }

    return BenchmarkResult(
        displacements=u,
        newton_iters=total_newton_iters,
        wallclock_s=wallclock_s,
        extras=extras,
    )


def _run_prescribed_matrix_cell(params: CookMembraneParameters) -> BenchmarkResult:
    """Exercise a Cook matrix cell through Phase 10 mesh/J2 helper contracts."""

    mesh = cook_membrane_mesh(
        params.element_type,
        nx=params.nx,
        ny=params.ny,
        nz=params.nz,
    )
    mat = J2PowerLawMaterial(
        E=params.E,
        nu=params.nu,
        sigma_y0=params.sigma_y0,
        K=params.K,
        n=params.n,
    )
    history = J2BenchmarkHistory.zeros_for_mesh(mesh)
    u = np.zeros_like(mesh.coordinates)

    load_nodes = mesh.boundary_nodes["load"]
    fixed_nodes = mesh.boundary_nodes["fixed"]
    reaction_history = np.zeros(params.n_steps, dtype=np.float64)
    tip_history = np.zeros(params.n_steps, dtype=np.float64)
    residual_history: list[list[float]] = []

    t0 = time.perf_counter()
    f_int = np.zeros_like(u)
    for step in range(1, params.n_steps + 1):
        load_fraction = step / params.n_steps
        u_step = np.zeros_like(u)
        u_step[load_nodes, 1] = load_fraction * params.matrix_tip_uy

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
        reaction_history[step - 1] = float(np.sum(f_int[fixed_nodes, 1]))
        tip_history[step - 1] = float(np.mean(u_step[load_nodes, 1]))
        residual_history.append([float(np.linalg.norm(f_int))])

    wallclock_s = time.perf_counter() - t0
    max_alpha = float(np.max(history.alpha_old)) if history.alpha_old.size else 0.0
    tip_uy = float(np.mean(u[load_nodes, 1]))

    extras = {
        "tip_uy": tip_uy,
        "reference_tip_uy": params.reference_tip_uy,
        "relative_error": np.nan,
        "formulation": params.formulation,
        "element_type": params.element_type,
        "matrix_mode": "prescribed_displacement",
        "residual_history": residual_history,
        "reaction_history": reaction_history,
        "tip_history": tip_history,
        "right_nodes": load_nodes,
        "n_steps": params.n_steps,
        "newton_tol": params.newton_tol,
        "mesh_shape": (params.nx, params.ny, params.nz),
        "mesh_n_nodes": mesh.n_nodes,
        "mesh_n_elem": mesh.n_elements,
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


def _validate_params(params: CookMembraneParameters) -> None:
    if params.formulation not in ("total_lagrangian", "updated_lagrangian"):
        raise ValueError(f"Unsupported Cook formulation {params.formulation!r}")
    if params.element_type not in ("hex8", "tet10"):
        raise ValueError(f"Unsupported Cook element_type {params.element_type!r}")
    if params.n_steps <= 0:
        raise ValueError("n_steps must be positive")
    if params.matrix_tip_uy <= 0.0:
        raise ValueError("matrix_tip_uy must be positive")
