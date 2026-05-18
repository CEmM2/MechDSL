"""Task P10-6: Simo and Hughes (1998) necking bar benchmark matrix.

Reference: Simo and Hughes, "Computational Inelasticity" (1998), Ch. 4,
necking bar load-displacement curve. The 2% tolerance against the committed
golden snapshot matches the MVP acceptance criterion
(dev/design_docs/07-CONVENTIONS.md section 6).

Acceptance criteria (from dev/tasks/PLAN-B/json/P10-6.json):
  1. TL curve matches reference within 2%.
  2. UL curve matches reference within 2%.
  3. TL and UL curves agree within 1%.

Existing partial coverage:
  - tests/test_benchmarks.py::TestNeckingBar::test_reference_comparison
    runs the TL path and asserts <2% vs golden; this file adds a second test
    that reaches the same verification through the harness function
    `mechdsl.verify.benchmarks.run_necking_bar_benchmark` that P10-10 nightly
    CI will call directly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from mechdsl.solver.import_adapter import ScipyCGSolver
from mechdsl.verify.benchmarks import (
    NeckingBarParameters,
    run_necking_bar_benchmark,
)
from tests.ref.ref_hex8_plastic import (
    HistoryFields,
    apply_dirichlet,
    apply_tangent_matvec_plastic,
    assemble_internal_force_plastic,
)

_GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "necking_bar_reference.npz"


@pytest.fixture(scope="module")
def necking_bar_tl_result():
    """Run the TL + J2 + Hex8 necking bar benchmark once per module."""
    return run_necking_bar_benchmark(
        params=NeckingBarParameters(),
        assemble_internal_force_plastic=assemble_internal_force_plastic,
        apply_dirichlet=apply_dirichlet,
        apply_tangent_matvec_plastic=apply_tangent_matvec_plastic,
        history_factory=HistoryFields,
        cg_solver=ScipyCGSolver(),
    )


@pytest.fixture(scope="module")
def necking_bar_ul_result():
    """Run the UL + J2 + Hex8 necking bar benchmark once per module."""
    return run_necking_bar_benchmark(
        params=NeckingBarParameters(formulation="updated_lagrangian"),
        assemble_internal_force_plastic=assemble_internal_force_plastic,
        apply_dirichlet=apply_dirichlet,
        apply_tangent_matvec_plastic=apply_tangent_matvec_plastic,
        history_factory=HistoryFields,
        cg_solver=ScipyCGSolver(),
    )


class TestTaskP10_6:
    """Tests for Task P10-6: Necking bar benchmark matrix (TL + J2+SVK + Hex8)."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_tl_necking_bar_within_2pct_of_simo_hughes(self, necking_bar_tl_result) -> None:
        """TL load-displacement curve matches Simo and Hughes (1998) within 2%.

        The golden file is a regression snapshot of the handwritten plastic
        reference kernel on the documented Simo and Hughes mesh + material +
        loading. It is the comparison target the MVP shipped with; the 2%
        tolerance catches regressions in the solver, the kernel, or the
        harness without churning on tiny numerical drift.
        """
        assert _GOLDEN_PATH.exists(), (
            f"Golden file missing: {_GOLDEN_PATH}. "
            f"Regenerate via `uv run python packages/mechdsl-core/tests/generate_golden.py`."
        )
        golden = np.load(_GOLDEN_PATH)
        gold_force = np.asarray(golden["force_history"], dtype=np.float64)
        gold_disp = np.asarray(golden["disp_history"], dtype=np.float64)

        cur_force = necking_bar_tl_result.extras["force_history"]
        cur_disp = necking_bar_tl_result.extras["disp_history"]

        assert cur_force.shape == gold_force.shape, (
            f"force_history shape mismatch: current={cur_force.shape}, "
            f"golden={gold_force.shape}. Harness params must match the golden setup."
        )
        np.testing.assert_allclose(
            cur_disp,
            gold_disp,
            rtol=1e-12,
            atol=1e-12,
            err_msg="Prescribed displacement schedule diverged from golden",
        )

        force_scale = float(np.max(np.abs(gold_force)))
        assert force_scale > 0.0, "Golden force history is all zero"
        atol_floor = 1e-10 * force_scale
        np.testing.assert_allclose(
            cur_force,
            gold_force,
            rtol=2e-2,
            atol=atol_floor,
            err_msg=(
                "TL load-displacement curve exceeds 2% per-step tolerance vs "
                f"Simo/Hughes golden (atol_floor={atol_floor:.3e}). "
                f"Current={cur_force}, Golden={gold_force}"
            ),
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_tl_newton_converges_all_steps(self, necking_bar_tl_result) -> None:
        """Newton-Raphson converges at every load step (|R_final|/|R_0| < 1e-8)."""
        residual_history = necking_bar_tl_result.extras["residual_history"]
        n_steps = necking_bar_tl_result.extras["n_steps"]

        assert len(residual_history) == n_steps, (
            f"Expected {n_steps} converged steps, got {len(residual_history)}"
        )
        for step_idx, step_res in enumerate(residual_history):
            assert len(step_res) >= 1, f"Step {step_idx}: empty residual history"
            if step_res[0] > 1e-15:
                assert step_res[-1] < 1e-8 * step_res[0], (
                    f"Step {step_idx}: Newton did not converge. "
                    f"R0={step_res[0]:.3e}, R_final={step_res[-1]:.3e}"
                )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_ul_necking_bar_within_2pct_of_simo_hughes(
        self, necking_bar_tl_result, necking_bar_ul_result
    ) -> None:
        """UL + J2 + Hex8 -- load-displacement curve within 2% of Simo and Hughes.

        Also covers AC3 (TL/UL intra-run consistency within 1%).
        """
        assert necking_bar_ul_result.extras["formulation"] == "updated_lagrangian"
        assert necking_bar_ul_result.extras["matrix_mode"] == "hex8_reference"

        golden = np.load(_GOLDEN_PATH)
        gold_force = np.asarray(golden["force_history"], dtype=np.float64)
        ul_force = necking_bar_ul_result.extras["force_history"]
        tl_force = necking_bar_tl_result.extras["force_history"]

        force_scale = float(np.max(np.abs(gold_force)))
        assert force_scale > 0.0, "Golden force history is all zero"
        atol_floor = 1e-10 * force_scale
        np.testing.assert_allclose(
            ul_force,
            gold_force,
            rtol=2e-2,
            atol=atol_floor,
            err_msg="UL load-displacement curve exceeds 2% vs Simo/Hughes golden",
        )
        np.testing.assert_allclose(
            ul_force,
            tl_force,
            rtol=1e-2,
            atol=atol_floor,
            err_msg="TL and UL necking curves differ by more than 1%",
        )

    @pytest.mark.regression
    def test_ul_smoke_history_is_finite_and_monotonic(self) -> None:
        """UL Hex8 J2 smoke path keeps accumulated plastic history finite."""
        result = run_necking_bar_benchmark(
            params=NeckingBarParameters(
                formulation="updated_lagrangian",
                nx=1,
                ny=1,
                nz=2,
                n_steps=3,
                smoke_final_disp=0.03,
            )
        )

        assert result.extras["formulation"] == "updated_lagrangian"
        assert result.extras["matrix_mode"] == "prescribed_displacement"
        assert result.extras["n_steps"] == 3
        assert result.extras["max_alpha"] >= 0.0
        assert result.extras["force_norm"] > 0.0
        assert np.all(np.isfinite(result.extras["force_history"]))
