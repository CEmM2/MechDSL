"""Generate self-converged reference values for Cook's membrane benchmark.

Run with: uv run pytest packages/mechdsl-core/tests/_gen_cooks_ref.py -s
"""

from __future__ import annotations

import time

import numpy as np

from mechdsl.solver.mesh_io import generate_cook_membrane_mesh
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
from tests.ref.ref_hex8_plastic import solve_plastic


def _run_cooks(
    nx: int,
    ny: int,
    nz: int = 1,
    n_steps: int = 10,
    cg_max_iter: int = 2000,
    tol: float = 1e-6,
    max_iter: int = 100,
    total_shear: float = 100.0,
) -> tuple[float, float]:
    """Run Cook's membrane with given mesh and return (mean tip uy, max alpha)."""
    mesh = generate_cook_membrane_mesh(nx, ny, nz)
    print(f"\n--- Mesh {nx}x{ny}x{nz}: {mesh.n_nodes} nodes, {mesh.n_elem} elems ---")
    print(f"  Total shear = {total_shear}, n_steps = {n_steps}")

    mat = J2PowerLawMaterial(E=240.565, nu=0.3, sigma_y0=243.0, K=300.0, n=0.4)

    bc_mask = np.zeros((mesh.n_nodes, 3), dtype=bool)
    bc_values = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    bc_mask[mesh.boundary_tags["x0"], :] = True

    f_ext = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    right_nodes = mesh.boundary_tags["x1"]
    force_per_node = total_shear / len(right_nodes)
    f_ext[right_nodes, 1] = force_per_node

    t0 = time.perf_counter()
    u, history, residual_history = solve_plastic(
        mesh.coords,
        mesh.connectivity,
        mat,
        bc_mask,
        bc_values,
        f_ext,
        n_steps=n_steps,
        tol=tol,
        max_iter=max_iter,
        cg_max_iter=cg_max_iter,
    )
    elapsed = time.perf_counter() - t0

    tip_uy = float(u[right_nodes, 1].mean())
    max_alpha = float(history.alpha_old.max())
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Steps converged: {len(residual_history)}/{n_steps}")
    for i, res in enumerate(residual_history):
        print(f"  Step {i}: R0={res[0]:.3e}, R_final={res[-1]:.3e}, iters={len(res)}")
    print(f"  Tip uy (mean) = {tip_uy:.10e}")
    print(f"  Max alpha = {max_alpha:.6e}")
    return tip_uy, max_alpha


def test_cooks_4x4() -> None:
    """4x4 mesh (50 nodes) reference."""
    tip, alpha = _run_cooks(4, 4, n_steps=10, tol=1e-6, total_shear=100.0, cg_max_iter=5000)
    print(f"\n4x4 F=100: tip_uy={tip:.10e}, alpha={alpha:.6e}")
