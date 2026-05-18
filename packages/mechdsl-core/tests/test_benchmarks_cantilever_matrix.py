"""Task P10-2: Cantilever benchmark on the full 2x2x3 parameter matrix.

Parameter matrix:
  - Formulation: TL, UL          (2)
  - Material:    SVK, Neo-Hookean (2)
  - Element:     Hex8, Tet10, Hex20 (3)

Acceptance criterion (from dev/tasks/PLAN-B/json/P10-2.json):
  All 12 combinations pass the 5% tolerance vs Euler-Bernoulli beam theory.

Existing partial coverage:
  - `tests/test_benchmarks.py::TestCantilever` (single config: handwritten
    reference solver, TL + SVK + Hex8) — provides the 5%-of-beam-theory
    methodology but does not parametrise.

The public benchmark keeps local tests smoke-sized while `CantileverParameters`
also records the full nightly mesh settings.
"""

from __future__ import annotations

import pytest

from mechdsl.verify.benchmarks import CantileverParameters, run_cantilever_benchmark


class TestTaskP10_2:
    """Tests for Task P10-2: Cantilever benchmark matrix."""

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "formulation,material,element",
        [
            ("total_lagrangian", "svk", "hex8"),
            ("total_lagrangian", "svk", "tet10"),
            ("total_lagrangian", "svk", "hex20"),
            ("total_lagrangian", "neo_hookean", "hex8"),
            ("total_lagrangian", "neo_hookean", "tet10"),
            ("total_lagrangian", "neo_hookean", "hex20"),
            ("updated_lagrangian", "svk", "hex8"),
            ("updated_lagrangian", "svk", "tet10"),
            ("updated_lagrangian", "svk", "hex20"),
            ("updated_lagrangian", "neo_hookean", "hex8"),
            ("updated_lagrangian", "neo_hookean", "tet10"),
            ("updated_lagrangian", "neo_hookean", "hex20"),
        ],
    )
    def test_cantilever_tip_within_5pct_of_beam_theory(
        self, formulation: str, material: str, element: str
    ) -> None:
        """Tip displacement is within 5% of Euler-Bernoulli beam theory."""
        result = run_cantilever_benchmark(
            params=CantileverParameters.smoke(
                formulation=formulation,
                material=material,
                element_type=element,
                nx=1,
                ny=1,
                nz=1,
            )
        )

        assert result.extras["formulation"] == formulation
        assert result.extras["material"] == material
        assert result.extras["element_type"] == element
        assert result.extras["profile"] == "smoke"
        assert result.extras["relative_error"] <= result.extras["tip_tolerance"]
        assert result.extras["tip_displacement"] > 0.0
        assert result.extras["force_norm"] > 0.0

    @pytest.mark.integration
    def test_public_cantilever_import_and_hex8_smoke_run(self) -> None:
        """The public benchmark API is importable and returns BenchmarkResult data."""
        result = run_cantilever_benchmark(params=CantileverParameters.smoke())

        assert result.displacements.shape[1] == 3
        assert result.newton_iters == 0
        assert result.wallclock_s >= 0.0
        assert result.extras["solver_mode"] == "displacement_controlled_elastic_smoke"

    @pytest.mark.integration
    def test_nightly_parameters_record_full_mesh_without_running(self) -> None:
        """Nightly settings preserve the original full mesh sizing separately."""
        params = CantileverParameters.nightly()

        assert params.profile == "nightly"
        assert (params.nx, params.ny, params.nz) == (40, 8, 4)

    @pytest.mark.integration
    def test_parameter_validation_rejects_bad_mesh_size(self) -> None:
        """Invalid mesh sizes are rejected before the benchmark runs."""
        with pytest.raises(ValueError, match="nx, ny, and nz must be positive"):
            run_cantilever_benchmark(params=CantileverParameters.smoke(nx=0))
