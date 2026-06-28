"""Benchmark-local elastic helpers for Phase 10 cantilever prerequisites.

This module is intentionally internal to `mechdsl.verify.benchmarks`. It
provides cheap prescribed-displacement elastic assembly checks for the
cantilever benchmark matrix without exposing the public cantilever runner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange
from mechdsl.symbolic.models.neo_hookean import (
    NeoHookeanMaterial,
)
from mechdsl.symbolic.models.neo_hookean import (
    pk2_stress as neo_hookean_pk2_stress,
)
from mechdsl.symbolic.models.svk import SVKMaterial
from mechdsl.symbolic.models.svk import pk2_stress as svk_pk2_stress
from mechdsl.verify.benchmarks._meshes import BenchmarkMesh, cantilever_mesh

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.ir.element_ir import ElementIR
    from mechdsl.verify.benchmarks._j2_solver import Formulation

ElasticElementType = Literal["hex8", "tet10", "hex20"]
ElasticMaterialKind = Literal["svk", "neo_hookean"]
ElasticMaterial = SVKMaterial | NeoHookeanMaterial


@dataclass(frozen=True)
class ElasticSolverParameters:
    """Internal elastic cantilever smoke parameters."""

    formulation: Formulation = "total_lagrangian"
    element_type: ElasticElementType = "hex8"
    material: ElasticMaterialKind = "svk"

    length: float = 10.0
    width: float = 1.0
    height: float = 1.0
    nx: int = 1
    ny: int = 1
    nz: int = 1

    E: float = 1_000.0
    nu: float = 0.3
    tip_displacement: float = 1.0e-3


@dataclass(frozen=True)
class ElasticSolveResult:
    """Result bundle returned by the internal elastic smoke solve."""

    displacements: NDArray[np.float64]
    internal_force: NDArray[np.float64]
    reaction_force: float
    force_norm: float
    strain_energy_proxy: float
    wallclock_s: float
    parameters: ElasticSolverParameters
    mesh_n_nodes: int
    mesh_n_elements: int


def make_elastic_material(kind: ElasticMaterialKind, *, E: float, nu: float) -> ElasticMaterial:
    """Create an elastic material object for benchmark-local smoke solves."""

    if kind == "svk":
        return SVKMaterial.from_E_nu(E=E, nu=nu)
    if kind == "neo_hookean":
        return NeoHookeanMaterial.from_E_nu(E=E, nu=nu)
    raise ValueError(f"Unsupported elastic material {kind!r}")


def assemble_internal_force_elastic(
    mesh: BenchmarkMesh,
    displacement: NDArray[np.float64],
    material: ElasticMaterial,
    *,
    formulation: Formulation = "total_lagrangian",
) -> NDArray[np.float64]:
    """Assemble benchmark-local elastic internal force for a mesh."""

    _validate_formulation(formulation)
    if displacement.shape != mesh.coordinates.shape:
        raise ValueError(
            f"displacement must have shape {mesh.coordinates.shape}, got {displacement.shape}"
        )

    element = ElementFactory.create(
        mesh.element_type,
        formulation=formulation,
        configuration="current" if formulation == "updated_lagrangian" else "reference",
    )
    f_int = np.zeros_like(displacement, dtype=np.float64)
    for conn in mesh.connectivity:
        nodes = conn.astype(np.int64)
        f_e = element_internal_force_elastic(
            displacement[nodes],
            mesh.coordinates[nodes],
            material,
            element=element,
            formulation=formulation,
        )
        for local_idx, node in enumerate(nodes):
            f_int[node] += f_e[local_idx]
    return f_int


def element_internal_force_elastic(
    u_elem: NDArray[np.float64],
    X_elem: NDArray[np.float64],
    material: ElasticMaterial,
    *,
    element: ElementIR,
    formulation: Formulation = "total_lagrangian",
) -> NDArray[np.float64]:
    """Compute benchmark-local elastic internal force for one element."""

    _validate_formulation(formulation)
    f_int = np.zeros_like(u_elem, dtype=np.float64)
    for q, point in enumerate(element.quadrature.points):
        dN_dX, detJ0 = _shape_grad_reference(element, X_elem, point)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E_strain = green_lagrange(F)
        S = _pk2_stress(material, E_strain)
        P = F @ S
        f_int += float(element.quadrature.weights[q]) * detJ0 * (dN_dX @ P.T)
    return f_int


def run_elastic_cantilever_smoke(
    params: ElasticSolverParameters | None = None,
) -> ElasticSolveResult:
    """Run an internal prescribed-displacement elastic cantilever smoke cell."""

    params = params or ElasticSolverParameters()
    _validate_params(params)
    mesh = cantilever_mesh(
        params.element_type,
        length=params.length,
        width=params.width,
        height=params.height,
        nx=params.nx,
        ny=params.ny,
        nz=params.nz,
    )
    material = make_elastic_material(params.material, E=params.E, nu=params.nu)
    u = np.zeros_like(mesh.coordinates)
    load_nodes = mesh.boundary_nodes["load"]
    fixed_nodes = mesh.boundary_nodes["fixed"]
    u[load_nodes, 1] = params.tip_displacement

    t0 = time.perf_counter()
    f_int = assemble_internal_force_elastic(
        mesh,
        u,
        material,
        formulation=params.formulation,
    )
    wallclock_s = time.perf_counter() - t0

    force_norm = float(np.linalg.norm(f_int))
    reaction_force = float(np.sum(f_int[fixed_nodes, 1]))
    strain_energy_proxy = 0.5 * float(np.sum(u * f_int))

    return ElasticSolveResult(
        displacements=u,
        internal_force=f_int,
        reaction_force=reaction_force,
        force_norm=force_norm,
        strain_energy_proxy=strain_energy_proxy,
        wallclock_s=wallclock_s,
        parameters=params,
        mesh_n_nodes=mesh.n_nodes,
        mesh_n_elements=mesh.n_elements,
    )


def _shape_grad_reference(
    element: ElementIR,
    X_elem: NDArray[np.float64],
    point: NDArray[np.float64],
) -> tuple[NDArray[np.float64], float]:
    dN_dxi = element.basis.gradient(float(point[0]), float(point[1]), float(point[2]))
    J0 = X_elem.T @ dN_dxi
    detJ0 = float(np.linalg.det(J0))
    if detJ0 <= 0.0:
        raise ValueError(f"Non-positive Jacobian determinant ({detJ0:.6e})")
    dN_dX = dN_dxi @ np.linalg.inv(J0)
    return dN_dX, detJ0


def _pk2_stress(material: ElasticMaterial, E_strain: NDArray[np.float64]) -> NDArray[np.float64]:
    if isinstance(material, SVKMaterial):
        return svk_pk2_stress(material, E_strain)
    if isinstance(material, NeoHookeanMaterial):
        return neo_hookean_pk2_stress(material, E_strain)
    raise TypeError(f"Unsupported elastic material object {type(material).__name__}")


def _validate_params(params: ElasticSolverParameters) -> None:
    _validate_formulation(params.formulation)
    if params.element_type not in ("hex8", "tet10", "hex20"):
        raise ValueError(f"Unsupported elastic element_type {params.element_type!r}")
    if params.material not in ("svk", "neo_hookean"):
        raise ValueError(f"Unsupported elastic material {params.material!r}")
    if params.tip_displacement <= 0.0:
        raise ValueError("tip_displacement must be positive")


def _validate_formulation(formulation: str) -> None:
    if formulation not in ("total_lagrangian", "updated_lagrangian"):
        raise ValueError(
            f"formulation must be 'total_lagrangian' or 'updated_lagrangian', got {formulation!r}"
        )
