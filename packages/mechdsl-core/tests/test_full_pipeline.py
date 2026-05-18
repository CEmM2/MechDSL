"""Full-pipeline E2E tests covering all 6 compiler layers for P4-1."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit
from mechdsl.frontend import build_context
from mechdsl.ir.mechanics_ir import ProblemIR
from mechdsl.lowering.fe_localise import LocalisationResult, localise, localise_and_optimize
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial
from tests.ref.ref_hex8_elastic import generate_hex8_mesh, solve_elastic
from tests.ref.ref_hex8_plastic import solve_plastic

if TYPE_CHECKING:
    from pathlib import Path

    from numpy.typing import NDArray

pytestmark = [pytest.mark.e2e, pytest.mark.from_problem_ir]

_RTOL_DISP = 1e-10
_ATOL_DISP = 1e-14
_RTOL_RESIDUAL = 1e-5
_ATOL_RESIDUAL = 1e-10


def _make_elastic_context() -> dict[str, Any]:
    """Build the Layer 1 frontend context for the elastic cantilever path."""
    return build_context(
        dim=3,
        cell_type="hex8",
        formulation="total_lagrangian",
        material_type="svk",
        params={"E": 200.0e3, "nu": 0.3},
        boundaries=[
            {"name": "fix", "face": "x0", "type": "dirichlet", "dofs": [0, 1, 2], "value": 0.0},
            {"name": "load", "face": "x1", "type": "neumann", "traction": "t_bar"},
        ],
    )


def _make_plastic_context() -> dict[str, Any]:
    """Build the Layer 1 frontend context for the plastic uniaxial path."""
    return build_context(
        dim=3,
        cell_type="hex8",
        formulation="total_lagrangian",
        material_type="j2_power_law",
        params={"E": 200.0e3, "nu": 0.3, "sigma_y0": 250.0, "K": 1000.0, "n": 1.0},
        boundaries=[
            {"name": "fix", "face": "x0", "type": "dirichlet", "dofs": [0, 1, 2], "value": 0.0},
            {"name": "load", "face": "x1", "type": "dirichlet", "dofs": [0], "value": "u_bar"},
        ],
    )


def _run_pipeline_from_context(
    ctx: dict[str, Any],
) -> tuple[ProblemIR, LocalisationResult, LocalisationResult, ArtifactBundle]:
    """Exercise Layers 1-5 explicitly and return the populated artifact bundle."""
    problem_ir = ProblemIR.from_context(ctx)

    loc_only = localise(problem_ir)
    loc_optimized, plans = localise_and_optimize(problem_ir)

    source = emit(ArtifactBundle.from_pipeline(problem_ir, loc_optimized, plans))
    ast.parse(source)

    bundle = ArtifactBundle.from_pipeline(
        problem_ir=problem_ir,
        localisation=loc_optimized,
        contraction_plans=plans,
        emitted_source=source,
    )
    return problem_ir, loc_only, loc_optimized, bundle


def _assert_pipeline_artifacts(
    *,
    ctx: dict[str, Any],
    problem_ir: ProblemIR,
    loc_only: LocalisationResult,
    loc_optimized: LocalisationResult,
    bundle: ArtifactBundle,
    expected_model: str,
) -> None:
    """Assert the required 6-layer compiler artifacts are populated and coherent."""
    assert ctx["material_type"] == expected_model
    assert problem_ir.material.model == expected_model

    assert loc_only.problem_ir is problem_ir
    assert loc_optimized.problem_ir is problem_ir
    assert loc_only.element_ir.n_nodes == 8
    assert loc_only.element_ir.dim == 3
    assert tuple(spec.name for spec in loc_only.einsum_specs) == (
        "strain_displacement",
        "internal_force",
        "tangent_matvec",
    )
    assert tuple(spec.name for spec in loc_optimized.einsum_specs) == tuple(
        spec.name for spec in loc_only.einsum_specs
    )

    assert bundle.problem_ir_dict
    assert bundle.element_ir_summary
    assert len(bundle.contraction_plans) == 3
    assert bundle.emitted_source

    assert bundle.problem_ir_dict["material"]["model"] == expected_model
    assert bundle.element_ir_summary["element_type"] == "hex8"
    assert bundle.element_ir_summary["n_nodes"] == 8
    assert bundle.element_ir_summary["dim"] == 3
    assert bundle.element_ir_summary["n_quadrature_points"] == 8

    for plan in bundle.contraction_plans:
        assert plan.einsum_string
        assert plan.tier > 0
        assert plan.estimated_flops > 0

    assert "import taichi as ti" in bundle.emitted_source
    assert "def allocate_fields" in bundle.emitted_source
    assert "def newton_solve" in bundle.emitted_source
    assert "def tangent_matvec" in bundle.emitted_source


def _load_golden(golden_dir: Path, name: str) -> dict[str, NDArray]:
    """Load a golden artifact bundle from tests/golden."""
    path = golden_dir / name
    if not path.exists():
        raise FileNotFoundError(
            f"Golden file not found: {path}\n"
            "Regenerate with:\n"
            "  PYTHONPATH=packages/mechdsl-core "
            "uv run python packages/mechdsl-core/tests/generate_golden.py"
        )
    return dict(np.load(path, allow_pickle=False))


def _run_elastic_cantilever() -> tuple[NDArray, list[float], NDArray, NDArray]:
    """Reproduce the elastic golden problem for regression comparison."""
    nx, ny, nz = 4, 2, 1
    lx, ly, lz = 4.0, 2.0, 1.0
    coords, conn = generate_hex8_mesh(nx, ny, nz, lx, ly, lz)
    n_nodes = coords.shape[0]

    e_young = 200.0e3
    nu = 0.3
    lam = e_young * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = e_young / (2.0 * (1.0 + nu))

    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    f_ext = np.zeros((n_nodes, 3), dtype=np.float64)
    right_top = np.where(
        (np.abs(coords[:, 0] - lx) < 1e-12)
        & (np.abs(coords[:, 1] - ly) < 1e-12)
        & (np.abs(coords[:, 2] - lz) < 1e-12)
    )[0]
    assert len(right_top) == 1
    f_ext[right_top[0], 2] = -10.0

    displacement, residual_history = solve_elastic(
        coords,
        conn,
        lam,
        mu,
        bc_mask,
        bc_values,
        f_ext,
        tol=1e-8,
        max_iter=50,
        cg_tol=1e-10,
        cg_max_iter=2000,
    )
    return displacement, residual_history, coords, conn


def _run_plastic_uniaxial() -> tuple[NDArray, NDArray, list[list[float]], NDArray, NDArray]:
    """Reproduce the plastic golden problem for regression comparison."""
    nx, ny, nz = 2, 1, 1
    lx, ly, lz = 2.0, 1.0, 1.0
    coords, conn = generate_hex8_mesh(nx, ny, nz, lx, ly, lz)
    n_nodes = coords.shape[0]

    material = J2PowerLawMaterial(E=200.0e3, nu=0.3, sigma_y0=250.0, K=1000.0, n=1.0)

    bc_mask = np.zeros((n_nodes, 3), dtype=bool)
    bc_values = np.zeros((n_nodes, 3), dtype=np.float64)
    left_nodes = np.where(np.abs(coords[:, 0]) < 1e-12)[0]
    bc_mask[left_nodes, :] = True

    right_nodes = np.where(np.abs(coords[:, 0] - lx) < 1e-12)[0]
    bc_mask[right_nodes, 0] = True
    bc_values[right_nodes, 0] = 0.005 * lx

    displacement, history, residual_history = solve_plastic(
        coords,
        conn,
        material,
        bc_mask,
        bc_values,
        np.zeros((n_nodes, 3), dtype=np.float64),
        n_steps=5,
        tol=1e-8,
        max_iter=50,
        cg_tol=1e-10,
        cg_max_iter=2000,
    )
    return displacement, history.alpha_current, residual_history, coords, conn


@pytest.mark.e2e
class TestFullPipeline:
    """P4-1 crown-jewel tests for the frontend-to-codegen pipeline."""

    def test_elastic_full_pipeline(self, golden_dir: Path) -> None:
        """Exercise all 6 layers for the SVK cantilever path and compare with golden data."""
        ctx = _make_elastic_context()
        problem_ir, loc_only, loc_optimized, bundle = _run_pipeline_from_context(ctx)
        _assert_pipeline_artifacts(
            ctx=ctx,
            problem_ir=problem_ir,
            loc_only=loc_only,
            loc_optimized=loc_optimized,
            bundle=bundle,
            expected_model="svk",
        )
        assert "def constitutive_update" in bundle.emitted_source
        assert "ti.f32" not in bundle.emitted_source

        golden = _load_golden(golden_dir, "elastic_cantilever.npz")
        displacement, residual_history, coords, conn = _run_elastic_cantilever()

        np.testing.assert_allclose(
            displacement,
            golden["displacement"],
            rtol=_RTOL_DISP,
            atol=_ATOL_DISP,
            err_msg="Elastic displacement field does not match golden data",
        )
        np.testing.assert_allclose(
            np.array(residual_history, dtype=np.float64),
            golden["residual_history"],
            rtol=_RTOL_RESIDUAL,
            atol=_ATOL_RESIDUAL,
            err_msg="Elastic residual history does not match golden data",
        )
        np.testing.assert_array_equal(coords, golden["coords"])
        np.testing.assert_array_equal(conn, golden["conn"])
        assert float(golden["lam"]) == pytest.approx(115384.61538461538)
        assert float(golden["mu"]) == pytest.approx(76923.07692307692)

    def test_plastic_full_pipeline(self, golden_dir: Path) -> None:
        """Exercise all 6 layers for the J2 uniaxial path and compare with golden data."""
        ctx = _make_plastic_context()
        problem_ir, loc_only, loc_optimized, bundle = _run_pipeline_from_context(ctx)
        _assert_pipeline_artifacts(
            ctx=ctx,
            problem_ir=problem_ir,
            loc_only=loc_only,
            loc_optimized=loc_optimized,
            bundle=bundle,
            expected_model="j2_power_law",
        )
        assert "constitutive_update_plastic" in bundle.emitted_source
        assert "alpha = ti.field" in bundle.emitted_source
        assert "sigma_y0" in bundle.emitted_source

        golden = _load_golden(golden_dir, "plastic_uniaxial.npz")
        displacement, alpha, residual_history, coords, conn = _run_plastic_uniaxial()
        residual_flat = np.concatenate(
            [np.array(step, dtype=np.float64) for step in residual_history]
        )
        residual_step_lengths = np.array([len(step) for step in residual_history], dtype=np.int64)

        np.testing.assert_allclose(
            displacement,
            golden["displacement"],
            rtol=_RTOL_DISP,
            atol=_ATOL_DISP,
            err_msg="Plastic displacement field does not match golden data",
        )
        np.testing.assert_allclose(
            alpha,
            golden["alpha"],
            rtol=_RTOL_DISP,
            atol=_ATOL_DISP,
            err_msg="Plastic alpha does not match golden data",
        )
        np.testing.assert_array_equal(
            residual_step_lengths,
            golden["residual_step_lengths"],
            err_msg="Plastic Newton iteration counts differ from golden",
        )
        np.testing.assert_allclose(
            residual_flat,
            golden["residual_flat"],
            rtol=_RTOL_RESIDUAL,
            atol=_ATOL_RESIDUAL,
            err_msg="Plastic residual history does not match golden data",
        )
        np.testing.assert_array_equal(coords, golden["coords"])
        np.testing.assert_array_equal(conn, golden["conn"])
        assert float(golden["E"]) == pytest.approx(200.0e3)
        assert float(golden["nu"]) == pytest.approx(0.3)
        assert float(golden["sigma_y0"]) == pytest.approx(250.0)
        assert float(golden["K"]) == pytest.approx(1000.0)
        assert float(golden["n_hard"]) == pytest.approx(1.0)
