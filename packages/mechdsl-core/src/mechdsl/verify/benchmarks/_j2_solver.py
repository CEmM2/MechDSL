"""Benchmark-local J2 helpers for Phase 10 prerequisite work.

The helpers in this module provide a small, numpy-based J2 assembly surface for
benchmark enablement. They intentionally do not modify the symbolic material
model, codegen, or public benchmark APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.lib.tensor_ops import deformation_gradient, green_lagrange
from mechdsl.symbolic.models.j2_power_law import J2PowerLawMaterial, radial_return

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from mechdsl.ir.element_ir import ElementIR
    from mechdsl.verify.benchmarks._meshes import BenchmarkMesh

Formulation = Literal["total_lagrangian", "updated_lagrangian"]


@dataclass
class J2BenchmarkHistory:
    """Equivalent plastic strain history for benchmark-local J2 solves."""

    alpha_current: NDArray[np.float64]
    alpha_old: NDArray[np.float64]

    @classmethod
    def zeros_for_mesh(
        cls, mesh: BenchmarkMesh, element: ElementIR | None = None
    ) -> J2BenchmarkHistory:
        elem = element or ElementFactory.create(mesh.element_type)
        shape = (mesh.n_elements, elem.quadrature.n_points)
        alpha_current = np.zeros(shape, dtype=np.float64)
        alpha_old = np.zeros(shape, dtype=np.float64)
        return cls(alpha_current=alpha_current, alpha_old=alpha_old)

    def __post_init__(self) -> None:
        self.alpha_current = np.asarray(self.alpha_current, dtype=np.float64)
        self.alpha_old = np.asarray(self.alpha_old, dtype=np.float64)
        if self.alpha_current.shape != self.alpha_old.shape:
            raise ValueError(
                "alpha_current and alpha_old must have the same shape, "
                f"got {self.alpha_current.shape} and {self.alpha_old.shape}"
            )
        if self.alpha_current.ndim != 2:
            raise ValueError(f"history alpha arrays must be 2D, got {self.alpha_current.shape}")

    def commit(self) -> None:
        """Accept the current state as the old state for the next load step."""

        self.alpha_old[:] = self.alpha_current

    def rollback(self) -> None:
        """Restore current state from the previously committed state."""

        self.alpha_current[:] = self.alpha_old

    @property
    def alpha_increment(self) -> NDArray[np.float64]:
        return self.alpha_current - self.alpha_old


def element_internal_force_j2(
    u_elem: NDArray[np.float64],
    X_elem: NDArray[np.float64],
    mat: J2PowerLawMaterial,
    alpha_old: NDArray[np.float64],
    *,
    element: ElementIR,
    formulation: Formulation = "total_lagrangian",
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Compute benchmark-local J2 internal force for one element."""

    _validate_formulation(formulation)
    if alpha_old.shape != (element.quadrature.n_points,):
        raise ValueError(
            f"alpha_old must have shape ({element.quadrature.n_points},), got {alpha_old.shape}"
        )

    f_int = np.zeros_like(u_elem, dtype=np.float64)
    alpha_new = np.empty(element.quadrature.n_points, dtype=np.float64)

    for q, point in enumerate(element.quadrature.points):
        dN_dX, detJ0 = _shape_grad_reference(element, X_elem, point)
        grad_u = u_elem.T @ dN_dX
        F = deformation_gradient(grad_u)
        E = green_lagrange(F)
        result = radial_return(mat, E, float(alpha_old[q]))
        P = F @ result.stress

        f_int += float(element.quadrature.weights[q]) * detJ0 * (dN_dX @ P.T)
        alpha_new[q] = result.alpha_new

    return f_int, alpha_new


def assemble_internal_force_j2(
    mesh: BenchmarkMesh,
    displacement: NDArray[np.float64],
    mat: J2PowerLawMaterial,
    history: J2BenchmarkHistory,
    *,
    formulation: Formulation = "total_lagrangian",
) -> NDArray[np.float64]:
    """Assemble benchmark-local J2 internal force and update current history."""

    _validate_formulation(formulation)
    element = ElementFactory.create(
        mesh.element_type,
        formulation=formulation,
        configuration="current" if formulation == "updated_lagrangian" else "reference",
    )
    _validate_displacement(mesh, displacement)
    _validate_history(mesh, element, history)

    f_int = np.zeros_like(displacement, dtype=np.float64)
    for e, conn in enumerate(mesh.connectivity):
        nodes = conn.astype(np.int64)
        f_e, alpha_new = element_internal_force_j2(
            displacement[nodes],
            mesh.coordinates[nodes],
            mat,
            history.alpha_old[e],
            element=element,
            formulation=formulation,
        )
        history.alpha_current[e] = alpha_new
        for local_idx, node in enumerate(nodes):
            f_int[node] += f_e[local_idx]

    return f_int


def assert_monotonic_plastic_history(history: J2BenchmarkHistory, *, tol: float = 1e-12) -> None:
    """Raise if equivalent plastic strain decreased across the current update."""

    min_increment = float(np.min(history.alpha_increment))
    if min_increment < -tol:
        raise ValueError(f"Equivalent plastic strain decreased by {min_increment:.6e}")


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


def _validate_displacement(mesh: BenchmarkMesh, displacement: NDArray[np.float64]) -> None:
    if displacement.shape != mesh.coordinates.shape:
        raise ValueError(
            f"displacement must have shape {mesh.coordinates.shape}, got {displacement.shape}"
        )


def _validate_history(
    mesh: BenchmarkMesh,
    element: ElementIR,
    history: J2BenchmarkHistory,
) -> None:
    expected = (mesh.n_elements, element.quadrature.n_points)
    if history.alpha_old.shape != expected:
        raise ValueError(f"history shape must be {expected}, got {history.alpha_old.shape}")


def _validate_formulation(formulation: str) -> None:
    if formulation not in ("total_lagrangian", "updated_lagrangian"):
        raise ValueError(
            f"formulation must be 'total_lagrangian' or 'updated_lagrangian', got {formulation!r}"
        )
