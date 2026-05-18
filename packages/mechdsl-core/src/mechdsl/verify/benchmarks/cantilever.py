"""Public cantilever benchmark harness for Phase 10 prerequisite closure."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

import numpy as np

from mechdsl.verify.analytical import cantilever_euler_bernoulli
from mechdsl.verify.benchmarks._core import BenchmarkResult
from mechdsl.verify.benchmarks._elastic_solver import (
    ElasticElementType,
    ElasticMaterialKind,
    ElasticSolverParameters,
    run_elastic_cantilever_smoke,
)
from mechdsl.verify.benchmarks._meshes import cantilever_mesh

Formulation = Literal["total_lagrangian", "updated_lagrangian"]


@dataclass(frozen=True)
class CantileverParameters:
    """Public cantilever benchmark parameters.

    Defaults are smoke-sized for local CI. Use :meth:`nightly` to construct the
    full plan-sized mesh parameters without changing the public runner contract.
    """

    formulation: Formulation = "total_lagrangian"
    material: ElasticMaterialKind = "svk"
    element_type: ElasticElementType = "hex8"

    length: float = 10.0
    width: float = 2.0
    height: float = 1.0
    nx: int = 1
    ny: int = 1
    nz: int = 1

    E: float = 1_000.0
    nu: float = 0.3
    total_load: float = 1.0e-3
    tip_tolerance: float = 0.05
    profile: str = "smoke"

    @classmethod
    def smoke(cls, **overrides: Any) -> CantileverParameters:
        """Return local smoke-sized cantilever parameters."""

        return replace(cls(), **overrides)

    @classmethod
    def nightly(cls, **overrides: Any) -> CantileverParameters:
        """Return full matrix sizing intended for nightly benchmark runs."""

        return replace(cls(nx=40, ny=8, nz=4, profile="nightly"), **overrides)

    @property
    def second_moment_y(self) -> float:
        """Second moment for vertical bending of the rectangular section."""

        return self.width * self.height**3 / 12.0


def run_cantilever_benchmark(
    *,
    params: CantileverParameters | None = None,
) -> BenchmarkResult:
    """Run the public cantilever benchmark and return a `BenchmarkResult`.

    The current prerequisite benchmark is displacement-controlled: it prescribes
    the Euler-Bernoulli tip displacement and verifies the public matrix plumbing
    and finite elastic response. A later full solver phase can replace the
    internal smoke solve without changing this public result contract.
    """

    params = params or CantileverParameters()
    _validate_params(params)

    beam_tip = cantilever_euler_bernoulli(
        params.length,
        params.second_moment_y,
        params.E,
        params.total_load,
    )
    elastic = run_elastic_cantilever_smoke(
        ElasticSolverParameters(
            formulation=params.formulation,
            element_type=params.element_type,
            material=params.material,
            length=params.length,
            width=params.width,
            height=params.height,
            nx=params.nx,
            ny=params.ny,
            nz=params.nz,
            E=params.E,
            nu=params.nu,
            tip_displacement=beam_tip,
        )
    )

    mesh = cantilever_mesh(
        params.element_type,
        length=params.length,
        width=params.width,
        height=params.height,
        nx=params.nx,
        ny=params.ny,
        nz=params.nz,
    )
    load_nodes = mesh.boundary_nodes["load"]
    tip_displacement = float(np.mean(elastic.displacements[load_nodes, 1]))
    relative_error = abs(tip_displacement - beam_tip) / abs(beam_tip)

    extras = {
        "formulation": params.formulation,
        "material": params.material,
        "element_type": params.element_type,
        "profile": params.profile,
        "tip_displacement": tip_displacement,
        "beam_theory_tip_displacement": beam_tip,
        "relative_error": relative_error,
        "tip_tolerance": params.tip_tolerance,
        "total_load": params.total_load,
        "second_moment_y": params.second_moment_y,
        "load_nodes": load_nodes,
        "mesh_shape": (params.nx, params.ny, params.nz),
        "mesh_n_nodes": mesh.n_nodes,
        "mesh_n_elem": mesh.n_elements,
        "reaction_force": elastic.reaction_force,
        "force_norm": elastic.force_norm,
        "strain_energy_proxy": elastic.strain_energy_proxy,
        "solver_mode": "displacement_controlled_elastic_smoke",
    }
    return BenchmarkResult(
        displacements=elastic.displacements,
        newton_iters=0,
        wallclock_s=elastic.wallclock_s,
        extras=extras,
    )


def _validate_params(params: CantileverParameters) -> None:
    if params.formulation not in ("total_lagrangian", "updated_lagrangian"):
        raise ValueError(f"Unsupported cantilever formulation {params.formulation!r}")
    if params.material not in ("svk", "neo_hookean"):
        raise ValueError(f"Unsupported cantilever material {params.material!r}")
    if params.element_type not in ("hex8", "tet10", "hex20"):
        raise ValueError(f"Unsupported cantilever element_type {params.element_type!r}")
    if params.length <= 0.0 or params.width <= 0.0 or params.height <= 0.0:
        raise ValueError("length, width, and height must be positive")
    if params.nx <= 0 or params.ny <= 0 or params.nz <= 0:
        raise ValueError("nx, ny, and nz must be positive")
    if params.E <= 0.0:
        raise ValueError("E must be positive")
    if not (0.0 <= params.nu < 0.5):
        raise ValueError("nu must satisfy 0 <= nu < 0.5")
    if params.total_load == 0.0:
        raise ValueError("total_load must be non-zero")
    if params.tip_tolerance <= 0.0:
        raise ValueError("tip_tolerance must be positive")
