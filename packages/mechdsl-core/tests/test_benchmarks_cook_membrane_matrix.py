"""Task P10-3: Cook's membrane benchmark matrix.

Reference: de Souza Neto, Peric & Owen, "Computational Methods for
Plasticity: Theory and Applications" (2008), Cook's membrane benchmark.

Existing partial coverage:
  - `tests/test_benchmarks.py::TestCooksMembrane::test_reference_comparison`
    runs the legacy regression directly through `tests.ref.ref_hex8_plastic`.
  - This file reaches the same benchmark through the public harness
    `mechdsl.verify.benchmarks.run_cook_membrane_benchmark`.
"""

from __future__ import annotations

import pytest

from mechdsl.verify.benchmarks import CookMembraneParameters, run_cook_membrane_benchmark
from tests.ref.ref_hex8_plastic import solve_plastic


@pytest.fixture(scope="module")
def cook_membrane_tl_result():
    """Run the TL + J2 + Hex8 benchmark once per module."""
    return run_cook_membrane_benchmark(
        params=CookMembraneParameters(),
        solve_plastic=solve_plastic,
    )


class TestTaskP10_3:
    """Tests for Task P10-3: Cook's membrane benchmark matrix."""

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_tl_j2_hex8_within_2pct_of_reference(self, cook_membrane_tl_result) -> None:
        """Tip displacement matches the committed Hex8 reference within 2%."""
        tip_uy = cook_membrane_tl_result.extras["tip_uy"]
        ref = cook_membrane_tl_result.extras["reference_tip_uy"]
        rel_error = cook_membrane_tl_result.extras["relative_error"]

        assert tip_uy > 0.0, f"Tip should displace in +y under shear, got uy = {tip_uy:.6e}"
        assert rel_error < 0.02, (
            f"Tip uy = {tip_uy:.6e} differs from reference ({ref:.6e}) by {rel_error:.2%} (> 2%)"
        )

    @pytest.mark.nightly
    @pytest.mark.regression
    @pytest.mark.slow
    def test_tl_newton_converges_all_steps(self, cook_membrane_tl_result) -> None:
        """Newton-Raphson converges at every load step."""
        residual_history = cook_membrane_tl_result.extras["residual_history"]
        n_steps = cook_membrane_tl_result.extras["n_steps"]
        newton_tol = cook_membrane_tl_result.extras["newton_tol"]

        assert len(residual_history) == n_steps, (
            f"Expected {n_steps} converged steps, got {len(residual_history)}"
        )
        for step_idx, step_res in enumerate(residual_history):
            assert len(step_res) >= 1, f"Step {step_idx}: empty residual history"
            if step_res[0] > 1e-15:
                assert step_res[-1] < newton_tol * step_res[0], (
                    f"Step {step_idx}: Newton did not converge. "
                    f"R0={step_res[0]:.3e}, R_final={step_res[-1]:.3e}"
                )

    @pytest.mark.parametrize(
        ("formulation", "element_type"),
        [
            ("total_lagrangian", "hex8"),
            ("updated_lagrangian", "hex8"),
            ("total_lagrangian", "tet10"),
            ("updated_lagrangian", "tet10"),
        ],
    )
    @pytest.mark.regression
    def test_original_cook_matrix_cells_are_active(
        self, formulation: str, element_type: str
    ) -> None:
        """TL/UL x Hex8/Tet10 Cook cells run and produce finite J2 state."""
        result = run_cook_membrane_benchmark(
            params=CookMembraneParameters(
                formulation=formulation,
                element_type=element_type,
                nx=1,
                ny=1,
                nz=1,
                n_steps=2,
                matrix_tip_uy=0.01,
            ),
        )

        assert result.extras["formulation"] == formulation
        assert result.extras["element_type"] == element_type
        assert result.extras["matrix_mode"] == "prescribed_displacement"
        assert result.extras["n_steps"] == 2
        assert result.extras["mesh_n_elem"] > 0
        assert result.extras["max_alpha"] >= 0.0
        assert result.displacements.shape[1] == 3
        assert result.extras["tip_uy"] > 0.0
        assert result.extras["force_norm"] > 0.0
