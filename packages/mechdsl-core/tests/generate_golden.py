"""Generate golden artifact files from reference solvers.

Run this script to (re)generate the golden .npz files used by
``test_artifacts.py`` for regression testing::

    cd packages/mechdsl-core
    uv run python tests/generate_golden.py

Golden files are written to ``tests/golden/`` and should be committed.
They must only be regenerated intentionally — never auto-updated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Ensure the tests directory is importable when running as a standalone script.
_TESTS_DIR = Path(__file__).resolve().parent
_PKG_DIR = _TESTS_DIR.parent  # packages/mechdsl-core
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from mechdsl.solver import generate_necking_bar_mesh  # noqa: E402
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial  # noqa: E402
from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic  # noqa: E402
from tests.ref.ref_hex8_plastic import (  # noqa: E402
    assemble_internal_force_plastic,
    solve_plastic,
)

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# ---------------------------------------------------------------------------
# Elastic cantilever (4x2x1 mesh)
# ---------------------------------------------------------------------------

# Material: steel-like SVK
_E_YOUNG = 200.0e3  # MPa
_NU = 0.3
_LAM = _E_YOUNG * _NU / ((1 + _NU) * (1 - 2 * _NU))
_MU = _E_YOUNG / (2 * (1 + _NU))


def generate_golden_elastic(golden_dir: Path) -> Path:
    """Run elastic reference solver and save golden file.

    Problem: 4x2x1 cantilever, fixed left face, point load on right face.

    Stores
    ------
    displacement : (n_nodes, 3)
        Final converged displacement field.
    residual_history : (n_iters,)
        Residual norm at each Newton iteration.
    coords : (n_nodes, 3)
        Reference coordinates (for reproducibility checks).
    conn : (n_elem, 8)
        Element connectivity.
    lam : scalar
        First Lame parameter used.
    mu : scalar
        Shear modulus used.
    """
    nx, ny, nz = 4, 2, 1
    Lx, Ly, Lz = 4.0, 2.0, 1.0
    coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
    n_nodes = coords.shape[0]

    # BCs: fix left face (x=0) in all DOFs
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    # External load: downward point force on right-back-top corner (Lx, Ly, Lz)
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
    right_top = np.where(
        (np.abs(coords[:, 0] - Lx) < 1e-12)
        & (np.abs(coords[:, 1] - Ly) < 1e-12)
        & (np.abs(coords[:, 2] - Lz) < 1e-12)
    )[0]
    assert len(right_top) == 1
    f_ext[right_top[0], 2] = -10.0  # downward in z

    u, residual_history = solve_elastic(
        coords,
        conn,
        _LAM,
        _MU,
        bc_mask,
        bc_values,
        f_ext,
        tol=1e-8,
        max_iter=50,
        cg_tol=1e-10,
        cg_max_iter=2000,
    )

    out_path = golden_dir / "elastic_cantilever.npz"
    np.savez_compressed(
        out_path,
        displacement=u,
        residual_history=np.array(residual_history, dtype=np.float64),
        coords=coords,
        conn=conn,
        lam=np.float64(_LAM),
        mu=np.float64(_MU),
    )
    print(f"Wrote {out_path}  ({u.shape[0]} nodes, {len(residual_history)} Newton iters)")
    return out_path


# ---------------------------------------------------------------------------
# Plastic uniaxial (2x1x1 mesh)
# ---------------------------------------------------------------------------


def generate_golden_plastic(golden_dir: Path) -> Path:
    """Run plastic reference solver and save golden file.

    Problem: 2x1x1 block, fixed left face, prescribed displacement on right
    face large enough to induce yielding.

    Stores
    ------
    displacement : (n_nodes, 3)
        Final converged displacement field at full load.
    alpha : (n_elem, 8)
        Equivalent plastic strain at every quadrature point.
    residual_history_per_step : list of arrays
        Residual norm at each Newton iteration for each load step.
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    E : scalar
        Young's modulus.
    nu : scalar
        Poisson's ratio.
    sigma_y0 : scalar
        Initial yield stress.
    K : scalar
        Hardening modulus.
    n_hard : scalar
        Hardening exponent.
    """
    nx, ny, nz = 2, 1, 1
    Lx, Ly, Lz = 2.0, 1.0, 1.0
    coords, conn = generate_hex8_mesh(nx, ny, nz, Lx, Ly, Lz)
    n_nodes = coords.shape[0]

    # Material: J2 power-law
    mat = J2PowerLawMaterial(
        E=_E_YOUNG,
        nu=_NU,
        sigma_y0=250.0,
        K=1000.0,
        n=1.0,
    )

    # BCs: fix left face (x=0) in all DOFs
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    # Prescribed displacement: pull right face in +x enough to yield
    # sigma_y0 = 250 MPa, E = 200e3 MPa  =>  yield strain ~ 250/200e3 = 1.25e-3
    # Prescribe 0.5% strain => well into plastic range on a 2-unit bar
    right_nodes = np.where(np.abs(coords[:, 0] - Lx) < 1e-12)[0]
    bc_mask[right_nodes, 0] = True  # fix x-dof on right face
    prescribed_ux = 0.005 * Lx  # 0.5% engineering strain
    bc_values[right_nodes, 0] = prescribed_ux

    # No external body/traction force
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

    n_steps = 5
    u, history, residual_history = solve_plastic(
        coords,
        conn,
        mat,
        bc_mask,
        bc_values,
        f_ext,
        n_steps=n_steps,
        tol=1e-8,
        max_iter=50,
        cg_tol=1e-10,
        cg_max_iter=2000,
    )

    # Convert residual_history (list[list[float]]) to ragged-safe storage
    # Store as a flat array plus a lengths array so we can reconstruct
    flat_residuals = np.concatenate([np.array(step, dtype=np.float64) for step in residual_history])
    step_lengths = np.array([len(step) for step in residual_history], dtype=np.int64)

    out_path = golden_dir / "plastic_uniaxial.npz"
    np.savez_compressed(
        out_path,
        displacement=u,
        alpha=history.alpha_current,
        residual_flat=flat_residuals,
        residual_step_lengths=step_lengths,
        coords=coords,
        conn=conn,
        E=np.float64(mat.E),
        nu=np.float64(mat.nu),
        sigma_y0=np.float64(mat.sigma_y0),
        K=np.float64(mat.K),
        n_hard=np.float64(mat.n),
    )
    print(
        f"Wrote {out_path}  ({u.shape[0]} nodes, {n_steps} steps, "
        f"max alpha = {history.alpha_current.max():.6e})"
    )
    return out_path


# ---------------------------------------------------------------------------
# Necking bar reference (2x2x8 quarter-model mesh)
# ---------------------------------------------------------------------------
#
# Mesh density: 2x2x8 (32 elements, 135 nodes).
# This is a REGRESSION snapshot of the handwritten reference solver on the
# smallest mesh that still exhibits necking localization near z=L/2. The
# fine-mesh self-convergence study is deferred to offline analysis — generating
# a 4x4x16 golden takes ~90 min per run, which is infeasible on every ref-solver
# modification. P3-4 compares the generated Taichi output to this regression
# snapshot; literature-value comparison (Simo & Hughes 1998) is performed
# separately at the benchmark level with 2% tolerance.
#
# Material: steel-like J2 with power-law hardening (from plan sprint3.md §140)
_NB_E = 206.9e3  # MPa
_NB_NU = 0.29
_NB_SIGMA_Y0 = 450.0  # MPa
_NB_K = 129.24  # MPa
_NB_N = 0.1  # power-law exponent
# Geometry
_NB_L = 20.0  # full bar length (mm)
_NB_W = 2.0  # full cross-section width (mm)
_NB_IMPERFECTION = 0.005  # fractional cross-section reduction
# Loading
_NB_N_STEPS = 10  # moderate stepping — enough to capture plastic evolution
_NB_FINAL_DISP = 1.0  # prescribed u_z at z1 face at full load (mm)


def generate_golden_necking_bar(golden_dir: Path) -> Path:
    """Run necking bar reference solver and save regression snapshot.

    Problem: quarter-model of a necking bar (2x2x8 Hex8 mesh — regression
    snapshot, not a convergence study; see the module-level comment block
    above for the mesh-density rationale). Symmetry BCs on x0/y0/z0 faces;
    displacement-controlled on z1 face.

    Stores
    ------
    displacement : (n_nodes, 3)
        Final converged displacement field at full load.
    force_history : (n_steps,)
        Reaction force (z-component) at z0 face at each load step.
    disp_history : (n_steps,)
        Prescribed displacement at z1 face at each load step.
    coords : (n_nodes, 3)
        Reference coordinates.
    conn : (n_elem, 8)
        Element connectivity.
    E, nu, sigma_y0, K, n_hard : scalars
        Material parameters.
    nx, ny, nz : scalars
        Mesh density parameters.
    residual_history_flat : (total_iters,)
        All Newton residual norms concatenated.
    residual_step_lengths : (n_steps,)
        Number of Newton iterations per load step.
    """
    nx, ny, nz = 2, 2, 8

    mesh = generate_necking_bar_mesh(nx, ny, nz, L=_NB_L, W=_NB_W, imperfection=_NB_IMPERFECTION)
    coords = mesh.coords
    conn = mesh.connectivity
    n_nodes = coords.shape[0]

    # Material
    mat = J2PowerLawMaterial(
        E=_NB_E,
        nu=_NB_NU,
        sigma_y0=_NB_SIGMA_Y0,
        K=_NB_K,
        n=_NB_N,
    )

    # Identify face node sets from boundary tags
    x0_nodes = mesh.boundary_tags["x0"]
    y0_nodes = mesh.boundary_tags["y0"]
    z0_nodes = mesh.boundary_tags["z0"]
    z1_nodes = mesh.boundary_tags["z1"]

    # BCs:
    #   x0 face: u_x = 0  (symmetry)
    #   y0 face: u_y = 0  (symmetry)
    #   z0 face: u_z = 0  (symmetry — midplane of full bar)
    #   z1 face: u_z = prescribed (displacement control)
    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)

    bc_mask[x0_nodes, 0] = True  # u_x = 0 on x0
    bc_mask[y0_nodes, 1] = True  # u_y = 0 on y0
    bc_mask[z0_nodes, 2] = True  # u_z = 0 on z0 (symmetry)
    bc_mask[z1_nodes, 2] = True  # u_z prescribed on z1 (displacement control)
    bc_values[z1_nodes, 2] = _NB_FINAL_DISP  # full load level

    # No external body/traction force (displacement-controlled)
    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)

    print(
        f"  Necking bar mesh: {nx}x{ny}x{nz}  |  "
        f"nodes={n_nodes}, elems={conn.shape[0]}  |  "
        f"z1 nodes={len(z1_nodes)}, z0 nodes={len(z0_nodes)}"
    )

    # We need per-step reaction forces for the load-displacement curve, which
    # solve_plastic does not expose. Run a custom step-by-step Newton loop that
    # records f_int at the converged state of each step.
    from mechdsl.solver.import_adapter import ScipyCGSolver
    from tests.ref.ref_hex8_plastic import (
        HistoryFields,
        apply_dirichlet,
        apply_tangent_matvec_plastic,
    )

    n_elem = conn.shape[0]
    ndof = n_nodes * 3
    u2 = np.zeros((n_nodes, 3), dtype=np.float64)
    history2 = HistoryFields(n_elem)
    cg_solver = ScipyCGSolver()

    force_history = np.zeros(_NB_N_STEPS, dtype=np.float64)
    disp_history = np.zeros(_NB_N_STEPS, dtype=np.float64)
    residual_history2: list[list[float]] = []

    print(f"  Running {_NB_N_STEPS} load steps...")
    for step in range(1, _NB_N_STEPS + 1):
        load_fraction = step / _NB_N_STEPS
        f_ext_step = load_fraction * f_ext  # = zero, kept for clarity
        bc_values_step = load_fraction * bc_values
        prescribed_uz = load_fraction * _NB_FINAL_DISP

        u2 = apply_dirichlet(u2, bc_mask, bc_values_step)

        step_residuals: list[float] = []
        R0_norm: float | None = None

        for newton_iter in range(50):
            f_int = assemble_internal_force_plastic(u2, coords, conn, mat, history2)
            R = f_ext_step - f_int
            R[bc_mask] = 0.0

            R_norm = float(np.linalg.norm(R))
            step_residuals.append(R_norm)

            if newton_iter == 0:
                R0_norm = R_norm
                if R0_norm < 1e-15:
                    break

            assert R0_norm is not None
            if R_norm < 1e-8 * R0_norm:
                break

            def matvec(v_flat: np.ndarray, _u: np.ndarray = u2) -> np.ndarray:
                v = v_flat.reshape((n_nodes, 3))
                Kv = apply_tangent_matvec_plastic(_u, v, coords, conn, mat, history2, bc_mask)
                return Kv.ravel()

            R_flat = R.ravel()
            du_flat, _cg_iters, _cg_res = cg_solver.solve(
                matvec, R_flat, np.zeros(ndof, dtype=np.float64), 1e-10, 5000
            )
            du = du_flat.reshape((n_nodes, 3))
            du[bc_mask] = 0.0
            u2 = u2 + du
        else:
            history2.rollback()
            raise RuntimeError(
                f"Newton did not converge at step {step}/{_NB_N_STEPS}. "
                f"Final |R| = {step_residuals[-1]:.3e}, |R0| = {step_residuals[0]:.3e}"
            )

        # Recompute f_int at the converged u2 (the last Newton f_int is stale by one du).
        # Do this BEFORE commit so the trial state (alpha_old from the previous load step)
        # is still in place — the radial return will reproduce alpha_current exactly.
        f_int_conv = assemble_internal_force_plastic(u2, coords, conn, mat, history2)
        reaction_z = float(np.sum(f_int_conv[z0_nodes, 2]))

        # Converged: commit history and record
        history2.commit()
        residual_history2.append(step_residuals)

        force_history[step - 1] = reaction_z
        disp_history[step - 1] = prescribed_uz

        iters = len(step_residuals)
        print(
            f"    Step {step:2d}/{_NB_N_STEPS}: "
            f"disp={prescribed_uz:.4f} mm, "
            f"F_z0={reaction_z:.4f} N, "
            f"iters={iters}, "
            f"|R_final|={step_residuals[-1]:.2e}"
        )

    # Ragged residual storage (same pattern as plastic_uniaxial.npz)
    flat_residuals = np.concatenate(
        [np.array(step, dtype=np.float64) for step in residual_history2]
    )
    step_lengths = np.array([len(step) for step in residual_history2], dtype=np.int64)

    out_path = golden_dir / "necking_bar_reference.npz"
    np.savez_compressed(
        out_path,
        displacement=u2,
        force_history=force_history,
        disp_history=disp_history,
        coords=coords,
        conn=conn,
        E=np.float64(_NB_E),
        nu=np.float64(_NB_NU),
        sigma_y0=np.float64(_NB_SIGMA_Y0),
        K=np.float64(_NB_K),
        n_hard=np.float64(_NB_N),
        nx=np.int64(nx),
        ny=np.int64(ny),
        nz=np.int64(nz),
        residual_history_flat=flat_residuals,
        residual_step_lengths=step_lengths,
    )
    print(
        f"Wrote {out_path}  ({n_nodes} nodes, {_NB_N_STEPS} steps, "
        f"max alpha = {history2.alpha_current.max():.6e})"
    )
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _make_bundle(model: str, params: dict[str, float]) -> str:
    """Emit Taichi source for the given material model."""
    from mechdsl.codegen.artifact import ArtifactBundle
    from mechdsl.codegen.taichi_printer import emit
    from mechdsl.ir.mechanics_ir import (
        BCType,
        BoundaryCondition,
        ElementType,
        Formulation,
        MaterialSpec,
        ProblemIR,
    )
    from mechdsl.lowering.fe_localise import localise_and_optimize

    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model=model, params=params),
        boundaries=(
            BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),
            BoundaryCondition(name="load", bc_type=BCType.NEUMANN, traction="t_bar"),
        ),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    bundle = ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)
    return emit(bundle)


def generate_golden_sources(golden_dir: Path) -> None:
    """Generate .py.golden source snapshots from the Taichi emitter.

    These are the emitted Taichi solver source files used by
    ``test_codegen.py::TestGoldenSnapshot`` for regression testing.
    """
    # Params MUST match test_codegen.py::_make_elastic_bundle / _make_plastic_bundle
    elastic_source = _make_bundle("svk", {"E": 200e3, "nu": 0.3})
    elastic_path = golden_dir / "generated_elastic.py.golden"
    elastic_path.write_text(elastic_source, encoding="utf-8")
    print(f"Wrote {elastic_path}  ({len(elastic_source.splitlines())} lines)")

    plastic_source = _make_bundle(
        "j2_power_law",
        {"E": 200e3, "nu": 0.3, "sigma_y0": 250.0, "K": 500.0, "n": 1.0},
    )
    plastic_path = golden_dir / "generated_plastic.py.golden"
    plastic_path.write_text(plastic_source, encoding="utf-8")
    print(f"Wrote {plastic_path}  ({len(plastic_source.splitlines())} lines)")


def generate_all(golden_dir: Path | None = None) -> None:
    """Generate all golden files (.npz data + .py.golden source snapshots)."""
    if golden_dir is None:
        golden_dir = GOLDEN_DIR
    golden_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Generating golden artifact files")
    print("=" * 60)

    generate_golden_elastic(golden_dir)
    generate_golden_plastic(golden_dir)
    generate_golden_necking_bar(golden_dir)
    generate_golden_sources(golden_dir)

    print("=" * 60)
    print("Done.")


if __name__ == "__main__":
    generate_all()
