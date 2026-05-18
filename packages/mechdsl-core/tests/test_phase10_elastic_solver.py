"""Tests for Phase 10 prerequisite phase 4 elastic benchmark solver layer."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from mechdsl.verify.benchmarks._elastic_solver import (
    ElasticSolverParameters,
    assemble_internal_force_elastic,
    make_elastic_material,
    run_elastic_cantilever_smoke,
)
from mechdsl.verify.benchmarks._meshes import cantilever_mesh


class TestTaskP4_1:
    """Tests for Task P4-1: elastic benchmark solver contracts."""

    @pytest.mark.integration
    def test_tl_and_ul_svk_hex8_small_displacement_agree(self) -> None:
        """TL and UL Hex8 SVK smoke solves agree in the small-displacement limit."""
        base = {
            "element_type": "hex8",
            "material": "svk",
            "nx": 1,
            "ny": 1,
            "nz": 1,
            "tip_displacement": 1.0e-5,
        }
        tl = run_elastic_cantilever_smoke(
            ElasticSolverParameters(formulation="total_lagrangian", **base)
        )
        ul = run_elastic_cantilever_smoke(
            ElasticSolverParameters(formulation="updated_lagrangian", **base)
        )

        np.testing.assert_allclose(ul.internal_force, tl.internal_force, rtol=1e-10, atol=1e-12)
        np.testing.assert_allclose(ul.displacements, tl.displacements, rtol=0.0, atol=0.0)
        assert tl.force_norm > 0.0
        assert ul.force_norm > 0.0

    @pytest.mark.integration
    def test_internal_assembly_contract_rejects_bad_displacement_shape(self) -> None:
        """Assembly rejects displacements that do not match mesh coordinates."""
        mesh = cantilever_mesh("hex8", nx=1, ny=1, nz=1)
        material = make_elastic_material("svk", E=1_000.0, nu=0.3)
        with pytest.raises(ValueError, match="displacement must have shape"):
            assemble_internal_force_elastic(
                mesh,
                np.zeros((mesh.n_nodes + 1, 3), dtype=np.float64),
                material,
            )


class TestTaskP4_2:
    """Tests for Task P4-2: material/element smoke matrix and runtime budget."""

    @pytest.mark.integration
    @pytest.mark.parametrize(
        ("material", "element_type"),
        list(itertools.product(("svk", "neo_hookean"), ("hex8", "tet10", "hex20"))),
    )
    def test_elastic_material_element_smoke_matrix_runs(
        self, material: str, element_type: str
    ) -> None:
        """SVK and Neo-Hookean run on Hex8, Tet10, and Hex20 smoke meshes."""
        result = run_elastic_cantilever_smoke(
            ElasticSolverParameters(
                formulation="total_lagrangian",
                material=material,
                element_type=element_type,
                nx=1,
                ny=1,
                nz=1,
                tip_displacement=1.0e-4,
            )
        )

        assert result.parameters.material == material
        assert result.parameters.element_type == element_type
        assert result.mesh_n_nodes > 0
        assert result.mesh_n_elements > 0
        assert result.force_norm > 0.0
        assert np.isfinite(result.reaction_force)
        assert np.isfinite(result.strain_energy_proxy)
        assert result.wallclock_s >= 0.0

    @pytest.mark.integration
    def test_representative_runtime_budget_is_recorded(self) -> None:
        """Representative smoke cells return runtime data for phase 5 sizing."""
        cases = [
            ElasticSolverParameters(material="svk", element_type="hex8"),
            ElasticSolverParameters(material="neo_hookean", element_type="tet10"),
            ElasticSolverParameters(material="svk", element_type="hex20"),
        ]
        results = [run_elastic_cantilever_smoke(case) for case in cases]

        assert all(result.wallclock_s >= 0.0 for result in results)
        assert all(result.force_norm > 0.0 for result in results)
        assert max(result.wallclock_s for result in results) < 5.0
