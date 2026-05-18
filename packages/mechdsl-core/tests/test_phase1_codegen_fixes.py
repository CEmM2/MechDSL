"""Tests for Phase 1: Critical Taichi Codegen Fixes (R3.1.x).

These tests verify the new behaviors introduced by Phase 1 of the
PR #3 review resolution plan (dev/plans/mvp_pr3_round3.md).
"""

from __future__ import annotations

import inspect

import pytest

from mechdsl.codegen.artifact import ArtifactBundle
from mechdsl.codegen.taichi_printer import emit, emit_constitutive_update
from mechdsl.ir.mechanics_ir import (
    BCType,
    BoundaryCondition,
    ElementType,
    Formulation,
    MaterialSpec,
    ProblemIR,
)
from mechdsl.lowering.fe_localise import localise_and_optimize


def _make_svk_bundle() -> ArtifactBundle:
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(model="svk", params={"E": 200e3, "nu": 0.3}),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


def _make_j2_bundle() -> ArtifactBundle:
    problem_ir = ProblemIR(
        dim=3,
        formulation=Formulation.TOTAL_LAGRANGIAN,
        element_type=ElementType.HEX8,
        material=MaterialSpec(
            model="j2_power_law",
            params={"E": 200e3, "nu": 0.3, "sigma_y": 250.0, "n_exp": 10.0},
        ),
        boundaries=(BoundaryCondition(name="fix", bc_type=BCType.DIRICHLET),),
    )
    loc_result, plans = localise_and_optimize(problem_ir)
    return ArtifactBundle.from_pipeline(problem_ir, loc_result, plans)


@pytest.fixture
def svk_source() -> str:
    return emit(_make_svk_bundle())


@pytest.fixture
def j2_source() -> str:
    return emit(_make_j2_bundle())


class TestC4NewtonNonConvergence:
    """R3.1.3: Emitted Newton driver raises RuntimeError on non-convergence."""

    def test_emitted_newton_raises_on_non_convergence(self, svk_source: str) -> None:
        assert "raise RuntimeError" in svk_source
        assert "did not converge" in svk_source
        assert "return max_iter" not in svk_source

    def test_emitted_newton_uses_res_norm_variable(self, svk_source: str) -> None:
        # The RuntimeError f-string must use res_norm (the actual variable at line 662)
        idx = svk_source.find("did not converge")
        context = svk_source[max(0, idx - 200) : idx + 200]
        assert "res_norm" in context


class TestC4bNaNGuard:
    """R3.1.4: NaN/Inf guard in emitted Newton driver."""

    def test_emitted_nan_guard_present(self, svk_source: str) -> None:
        assert "np.isfinite(res_norm)" in svk_source

    def test_emitted_nan_guard_error_message(self, svk_source: str) -> None:
        assert "NaN or Inf detected" in svk_source


class TestH9MaterialValidation:
    """R3.1.6: Material model validation in emit()."""

    def test_emit_invalid_material_raises(self) -> None:
        bundle = _make_svk_bundle()
        # Corrupt the material model to trigger validation
        bundle.problem_ir_dict["material"]["model"] = "unknown_model"
        with pytest.raises(ValueError, match="Unsupported material model"):
            emit(bundle)

    def test_emit_svk_passes_validation(self) -> None:
        source = emit(_make_svk_bundle())
        assert len(source) > 0

    def test_emit_j2_passes_validation(self) -> None:
        source = emit(_make_j2_bundle())
        assert len(source) > 0


class TestH1J2ConvergenceCheck:
    """R3.1.7: Emitted J2 convergence check after Newton loop."""

    def test_emitted_j2_convergence_check_present(self, j2_source: str) -> None:
        assert "f_final" in j2_source
        assert "ti.abs(f_final)" in j2_source

    def test_emitted_j2_nan_flag_on_non_convergence(self, j2_source: str) -> None:
        assert "float('nan')" in j2_source


class TestH2DeltaLambdaClamp:
    """R3.1.8: Emitted J2 negative delta_lambda guard."""

    def test_emitted_j2_dl_clamp_present(self, j2_source: str) -> None:
        assert "dl = ti.max(dl, 0.0)" in j2_source
        # Clamp must appear before factor computation
        pos_clamp = j2_source.find("dl = ti.max(dl, 0.0)")
        pos_factor = j2_source.find("factor = 1.0 - 3.0 * mu * dl / sigma_eq")
        assert pos_clamp < pos_factor


class TestCM3FunctionRename:
    """R3.1.9: emit_constitutive_stub renamed to emit_constitutive_update."""

    def test_emit_constitutive_update_exists(self) -> None:
        assert callable(emit_constitutive_update)

    def test_emit_constitutive_stub_removed(self) -> None:
        import mechdsl.codegen.taichi_printer as tp

        source = inspect.getsource(tp)
        assert "emit_constitutive_stub" not in source
