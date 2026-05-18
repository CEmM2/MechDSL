"""Example: Run the elastic reference solver on a cantilever beam.

This script demonstrates how to use the handwritten reference solver
(ref_hex8_elastic) to solve a 3D elastic cantilever beam with SVK
material and Hex8 elements.  The reference solver is the ground truth
for verifying generated code.

Usage:
    uv run python dev/examples/run_elastic_reference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# The reference solver lives in the test suite; add its parent to sys.path
# so that ``from tests.ref.ref_hex8_elastic import ...`` resolves correctly.
_TESTS_PARENT = str(Path(__file__).resolve().parents[2] / "packages" / "mechdsl-core")
if _TESTS_PARENT not in sys.path:
    sys.path.insert(0, _TESTS_PARENT)

from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic  # noqa: E402

from mechdsl.symbolic.models.svk import SVKMaterial  # noqa: E402


def main() -> None:
    # ---- Material parameters (steel-like) ----
    E = 200e3  # Young's modulus [MPa]
    nu = 0.3  # Poisson's ratio
    mat = SVKMaterial.from_E_nu(E, nu)
    lam, mu = mat.lam, mat.mu

    # ---- Mesh: 4x2x2 cantilever beam ----
    nx, ny, nz = 4, 2, 2
    Lx, Ly, Lz = 10.0, 2.0, 2.0
    coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
    n_nodes = coords.shape[0]

    print(f"Mesh: {nx}x{ny}x{nz} = {conn.shape[0]} elements, {n_nodes} nodes")

    # ---- Boundary conditions ----
    # Fix left face (x = 0): all components
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)

    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    # External force: downward traction on right face (x = Lx)
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
    right_nodes = np.where(np.abs(coords[:, 0] - Lx) < 1e-12)[0]
    traction_per_node = -1000.0 / len(right_nodes)  # total force / number of face nodes
    f_ext[right_nodes, 2] = traction_per_node  # z-direction

    # ---- Solve ----
    print(f"Material: SVK (E={E}, nu={nu}, lam={lam:.1f}, mu={mu:.1f})")
    print("Solving...")
    u, residual_history = solve_elastic(
        coords,
        conn,
        lam,
        mu,
        bc_mask,
        bc_values,
        f_ext,
        tol=1e-8,
        max_iter=50,
    )

    # ---- Report ----
    print(f"Newton converged in {len(residual_history)} iterations")
    for i, r in enumerate(residual_history):
        print(f"  iter {i}: ||R|| = {r:.6e}")

    tip_disp = u[right_nodes, 2]
    print(f"\nTip displacement (z): min={tip_disp.min():.6e}, max={tip_disp.max():.6e}")
    print(f"Max displacement magnitude: {np.linalg.norm(u, axis=1).max():.6e}")

    # Verify fixed face
    fixed_disp = np.linalg.norm(u[left_nodes], axis=1).max()
    print(f"Fixed face max displacement: {fixed_disp:.2e} (should be 0)")

    return None


if __name__ == "__main__":
    main()
    sys.exit(0)
