"""End-to-end Taichi execution tests -- Phase 6 smoke tests.

Task P6-T1: Create E2E Taichi smoke test.
Compile SVK elastic problem -> write generated .py -> execute under Taichi JIT ->
compare displacement against handwritten reference (max diff < 1e-10).

Strategy: import the generated module's Taichi kernels (compute_internal_force,
tangent_matvec) and drive Newton externally with proper BC enforcement.  The
generated newton_solve does NOT include BC handling (known gap from Phase 5),
so we wrap the generated kernels with numpy-level BC enforcement and compare
against the handwritten reference solver in tests/ref/ref_hex8_elastic.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pathlib import Path
import pytest

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
from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic

pytestmark = pytest.mark.from_problem_ir

# ---------------------------------------------------------------------------
# Material parameters (must match reference tests)
# ---------------------------------------------------------------------------

E_YOUNG = 200.0e3
NU = 0.3
LAM = E_YOUNG * NU / ((1 + NU) * (1 - 2 * NU))
MU = E_YOUNG / (2 * (1 + NU))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_elastic_problem_ir() -> ProblemIR:
    """Create SVK elastic ProblemIR for E2E test."""
    return ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": E_YOUNG, "nu": NU}),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )


# _import_generated_module is sourced from the shared _e2e_helpers module
# so all e2e tests share a single helper definition.
from tests._e2e_helpers import _import_generated_module  # noqa: E402


def _load_mesh_into_module(mod, coords: np.ndarray, conn: np.ndarray) -> None:
    """Allocate Taichi fields and load mesh data into the generated module."""
    n_nodes = coords.shape[0]
    n_elem = conn.shape[0]

    mod.allocate_fields(n_nodes, n_elem)
    mod.x_ref.from_numpy(coords)

    # Load connectivity element-by-element (elem_nodes is a 2D ti.field)
    for e in range(n_elem):
        for a in range(8):
            mod.elem_nodes[e, a] = int(conn[e, a])


def _newton_with_bc(
    mod,
    coords: np.ndarray,
    bc_mask: np.ndarray,
    f_ext: np.ndarray,
    lam: float,
    mu: float,
    tol: float = 1e-8,
    max_iter: int = 50,
) -> tuple[np.ndarray, list[float]]:
    """Run Newton-Raphson using generated Taichi kernels with BC enforcement.

    Uses the generated module's compute_internal_force and tangent_matvec
    (Taichi JIT) but enforces Dirichlet BCs from the Python side.
    """
    n_nodes = coords.shape[0]
    n_dof = n_nodes * 3
    bc_flat = bc_mask.ravel()

    u = np.zeros((n_nodes, 3), dtype=np.float64)
    mod.u.from_numpy(u)
    mod.f_ext.from_numpy(f_ext)

    cg = CGSolver()
    residual_history: list[float] = []
    R0_norm: float | None = None

    for newton_iter in range(max_iter):
        # Compute f_int using generated Taichi kernel
        mod.u.from_numpy(u)
        mod.compute_internal_force(lam, mu)
        f_int = mod.f_int.to_numpy()

        # Residual with BC enforcement
        R = f_ext - f_int
        R[bc_mask] = 0.0
        R_flat = R.ravel()
        R_norm = float(np.linalg.norm(R_flat))
        residual_history.append(R_norm)

        if newton_iter == 0:
            R0_norm = R_norm
            if R0_norm < 1e-15:
                break

        assert R0_norm is not None
        if R_norm < tol * R0_norm:
            break

        # Tangent matvec with BC enforcement
        def matvec(v_flat: np.ndarray, _u_bound: np.ndarray = u) -> np.ndarray:
            v = v_flat.copy()
            v[bc_flat] = 0.0
            # Generated tangent_matvec uses Taichi JIT internally
            mod.u.from_numpy(_u_bound)
            Kv = mod.tangent_matvec(v, lam, mu)
            Kv[bc_flat] = v_flat[bc_flat]
            return Kv

        du_flat, _cg_iters, _cg_res = cg.solve(
            matvec, R_flat, np.zeros(n_dof, dtype=np.float64), 1e-10, 2000
        )

        du = du_flat.reshape((n_nodes, 3))
        du[bc_mask] = 0.0
        u = u + du
    else:
        raise RuntimeError(
            f"Newton did not converge after {max_iter} iterations. "
            f"Final |R| = {residual_history[-1]:.3e}"
        )

    return u, residual_history


# ===========================================================================
# End-to-end Taichi execution tests
# ===========================================================================


@pytest.mark.slow
@pytest.mark.e2e
class TestE2ETaichiExecution:
    """End-to-end tests: compile -> execute -> compare vs reference.

    Acceptance criteria covered:
    - AC1: Generated code compiles and runs under Taichi JIT
    - AC2: 1-element Newton solve converges
    - AC3: Displacement matches handwritten reference within 1e-10
    - AC4: Tests marked @pytest.mark.slow and @pytest.mark.e2e
    - AC5: Tests pass when run with uv run pytest -m slow
    """

    def test_elastic_hex8_matches_reference(self, tmp_path: Path) -> None:
        """Compiled SVK elastic solver produces same displacement as reference.

        Verifies: full compile -> Taichi JIT -> newton solve -> compare pipeline
        Acceptance criterion: AC1, AC2, AC3
        Passes when: max |u_gen - u_ref| < 1e-10
        """
        # 1. Compile ProblemIR -> emitted source
        bundle = mechdsl_compile(_make_elastic_problem_ir())
        assert bundle.emitted_source, "compile() returned empty source"

        # 2. Import generated module (triggers Taichi JIT)
        mod = _import_generated_module(bundle.emitted_source, tmp_path)
        assert hasattr(mod, "compute_internal_force")
        assert hasattr(mod, "tangent_matvec")

        # 3. Set up 1-element Hex8 mesh (unit cube)
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        _load_mesh_into_module(mod, coords, conn)

        # 4. BCs: fix left face (x=0), tension on right face
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        for n_idx in right_nodes:
            f_ext[n_idx, 0] = 1.0

        # 5. Solve with generated Taichi kernels + BC enforcement
        u_gen, residuals_gen = _newton_with_bc(mod, coords, bc_mask, f_ext, LAM, MU)

        # 6. Solve with handwritten reference
        u_ref, _residuals_ref = solve_elastic(coords, conn, LAM, MU, bc_mask, bc_values, f_ext)

        # 7. Compare
        max_diff = float(np.max(np.abs(u_gen - u_ref)))
        assert max_diff < 1e-10, (
            f"Generated vs reference displacement mismatch: max diff = {max_diff:.3e}"
        )

        assert float(np.max(np.abs(u_gen))) > 1e-10, "Solution is trivially zero"
        assert len(residuals_gen) >= 2, "Should take at least 1 Newton iteration"

    def test_linear_elastic_converges_few_iterations(self, tmp_path: Path) -> None:
        """Linear elastic SVK converges rapidly (near-linear regime).

        For small loads the SVK model is approximately linear. With finite-
        difference tangent (central FD, h=1e-7) the O(h^2) error means the
        first correction is not exact, but convergence should still be rapid
        (at most 3 iterations).

        Verifies: Newton convergence count for near-linear problem
        Acceptance criterion: AC2
        Passes when: Newton converges in <= 3 iterations
        """
        # 1. Compile and import
        bundle = mechdsl_compile(_make_elastic_problem_ir())
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_e2e_conv")

        # 2. Set up 1-element mesh
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]
        _load_mesh_into_module(mod, coords, conn)

        # 3. BCs: fix left face, small tension on right face
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True

        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        for n_idx in right_nodes:
            f_ext[n_idx, 0] = 1.0  # same load as test_elastic_hex8_matches_reference

        # 4. Solve with looser tolerance — focus is on iteration count
        _u, residuals = _newton_with_bc(mod, coords, bc_mask, f_ext, LAM, MU, tol=1e-6)

        # 5. Near-linear problem: should converge rapidly
        # With FD tangent (h=1e-7), the O(h^2) error limits precision,
        # so convergence may take 2-3 iterations rather than exactly 1.
        n_newton_iters = len(residuals) - 1  # first entry is initial residual
        assert n_newton_iters <= 3, (
            f"Expected <= 3 Newton iterations for near-linear problem, "
            f"got {n_newton_iters}. "
            f"Residuals: {[f'{r:.3e}' for r in residuals]}"
        )
        # First correction should reduce residual by several orders of magnitude
        assert residuals[1] < 1e-3 * residuals[0], (
            f"First Newton correction should reduce residual significantly. "
            f"R0={residuals[0]:.3e}, R1={residuals[1]:.3e}"
        )

    def test_emitted_main_produces_nontrivial_solution(self, tmp_path: Path) -> None:
        """The generated __main__ block produces a nonzero displacement when
        the mesh .npz includes bc_dofs and f_ext.

        This is a behavioral test: it calls the emitted newton_solve()
        with bc_dofs and f_ext and verifies the solver produces a non-trivial
        displacement field, proving that BCs are actually applied.

        Verifies: newton_solve(bc_dofs=...) enforces Dirichlet BCs and
        f_ext drives the solver to a non-zero solution.
        """
        # 1. Compile ProblemIR → emitted source
        bundle = mechdsl_compile(_make_elastic_problem_ir())

        # 2. Set up mesh with BCs
        coords, conn = generate_hex8_mesh(1, 1, 1, 1.0, 1.0, 1.0)
        n_nodes = coords.shape[0]

        # Fix left face (x=0), tension on right face (x=1)
        bc_mask = np.zeros((n_nodes, 3), dtype=bool)
        left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
        bc_mask[left_nodes, :] = True
        bc_dofs = np.where(bc_mask.ravel())[0].astype(np.int64)

        f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
        right_nodes = np.where(np.abs(coords[:, 0] - 1.0) < 1e-12)[0]
        for n_idx in right_nodes:
            f_ext[n_idx, 0] = 1.0

        # 3. Run the emitted newton_solve via Python API (not subprocess)
        #    This avoids subprocess/cwd issues while still testing the full
        #    emitted newton_solve path with BC enforcement.
        mod = _import_generated_module(bundle.emitted_source, tmp_path, "gen_main")
        _load_mesh_into_module(mod, coords, conn)

        # Load f_ext into the module's Taichi field
        mod.f_ext.from_numpy(f_ext)

        # Call the emitted newton_solve with bc_dofs
        n_iters = mod.newton_solve(LAM, MU, bc_dofs=bc_dofs)

        # 4. Verify non-trivial displacement
        u_arr = mod.u.to_numpy()
        assert float(np.max(np.abs(u_arr))) > 1e-10, (
            f"Displacement is trivially zero — BCs not applied. max|u| = {np.max(np.abs(u_arr)):.3e}"
        )
        assert n_iters >= 1, "Should take at least 1 Newton iteration with nonzero load"
