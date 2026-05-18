"""Matrix-capable MMS convergence helpers for Phase 10.

This module intentionally does not modify ``run_mms_convergence(lam, mu, ...)``.
It adds a separate result surface for the broader element/material MMS matrix.

Policy for nonlinear and dissipative material entries
-----------------------------------------------------
The manufactured field and source terms currently available in
``mechdsl.verify.convergence`` are elastic-regime MMS data. Matrix entries for
Neo-Hookean, J2 power-law, Perzyna, and Lemaitre are therefore documented as
elastic-regime checks: the displacement amplitude is small, plastic flow and
damage are inactive, and the test validates the element interpolation/error
machinery and structured diagnostics rather than a true dissipative source
term. True manufactured plastic/damage source terms can replace these entries
later without changing the result dataclasses below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from mechdsl.ir.element_factory import ElementFactory
from mechdsl.verify.benchmarks._meshes import (
    BenchmarkMesh,
    structured_block_mesh,
    validate_positive_jacobians,
)
from mechdsl.verify.convergence import (
    ConvergenceResult,
    check_convergence_rate,
    mms_exact_displacement,
    mms_exact_displacement_gradient,
    run_mms_convergence,
)

if TYPE_CHECKING:

    from mechdsl.ir.element_ir import ElementIR

MMSElementType = Literal["hex8", "tet10", "hex20"]
MMSMaterial = Literal["svk", "neo_hookean", "j2_power_law", "perzyna", "lemaitre_d0"]
MMSPolicy = Literal["svk_full_solve", "elastic_regime_interpolation"]

_DEFAULT_MESH_LEVELS = (4, 8, 16)
_DEFAULT_MATRIX: tuple[MMSMatrixCase, ...]


@dataclass(frozen=True)
class MMSMatrixCase:
    """One element/material entry in the Phase 10 MMS matrix."""

    element_type: MMSElementType
    material: MMSMaterial
    expected_l2_rate: float
    expected_h1_rate: float
    policy: MMSPolicy = "elastic_regime_interpolation"

    @property
    def id(self) -> str:
        return f"{self.element_type}:{self.material}:{self.policy}"


@dataclass(frozen=True)
class MMSConvergenceEntry:
    """Structured convergence result for one MMS matrix case."""

    case: MMSMatrixCase
    mesh_sizes: tuple[float, ...]
    l2_errors: tuple[float, ...]
    h1_errors: tuple[float, ...]
    l2_check: ConvergenceResult
    h1_check: ConvergenceResult
    diagnostics: dict[str, object]

    @property
    def passed(self) -> bool:
        return self.l2_check.passed and self.h1_check.passed


@dataclass(frozen=True)
class MMSMatrixResult:
    """Result bundle for a full MMS matrix run."""

    entries: tuple[MMSConvergenceEntry, ...]

    @property
    def passed(self) -> bool:
        return all(entry.passed for entry in self.entries)

    def by_id(self) -> dict[str, MMSConvergenceEntry]:
        return {entry.case.id: entry for entry in self.entries}


def default_mms_matrix_cases() -> tuple[MMSMatrixCase, ...]:
    """Return the planned Phase 10 MMS matrix entries."""

    return _DEFAULT_MATRIX


def run_mms_convergence_matrix(
    cases: tuple[MMSMatrixCase, ...] | list[MMSMatrixCase] | None = None,
    *,
    mesh_levels: tuple[int, ...] | list[int] = _DEFAULT_MESH_LEVELS,
    L: float = 1.0,
    A: float = 1.0e-3,
    tol: float = 0.1,
) -> MMSMatrixResult:
    """Run the additive Phase 10 MMS matrix API.

    The existing Hex8 SVK full-solve path remains available through the legacy
    API and is used for cases with ``policy='svk_full_solve'``. The default
    matrix uses the cheaper elastic-regime interpolation policy so local
    regression tests stay fast.
    """

    matrix = tuple(cases) if cases is not None else default_mms_matrix_cases()
    _validate_mesh_levels(mesh_levels)
    interpolation_cache: dict[MMSElementType, tuple[list[float], list[float], list[float], tuple[int, ...]]] = {}
    entries = tuple(
        _run_case(
            case,
            tuple(mesh_levels),
            L=L,
            A=A,
            tol=tol,
            interpolation_cache=interpolation_cache,
        )
        for case in matrix
    )
    return MMSMatrixResult(entries=entries)


def _run_case(
    case: MMSMatrixCase,
    mesh_levels: tuple[int, ...],
    *,
    L: float,
    A: float,
    tol: float,
    interpolation_cache: dict[MMSElementType, tuple[list[float], list[float], list[float], tuple[int, ...]]],
) -> MMSConvergenceEntry:
    _validate_case(case)
    if case.policy == "svk_full_solve":
        if case.element_type != "hex8" or case.material != "svk":
            raise ValueError("svk_full_solve policy is only available for hex8/svk")
        l2_errors, h1_errors, mesh_sizes = run_mms_convergence(
            lam=1.0,
            mu=1.0,
            mesh_levels=list(mesh_levels),
            L=L,
            A=A,
        )
        mesh_node_counts = tuple((n + 1) ** 3 for n in mesh_levels)
    else:
        if case.element_type not in interpolation_cache:
            interpolation_cache[case.element_type] = _run_interpolation_mms(
                case.element_type,
                mesh_levels,
                L=L,
                A=A,
            )
        l2_errors, h1_errors, mesh_sizes, mesh_node_counts = interpolation_cache[case.element_type]

    l2_check = check_convergence_rate(
        l2_errors,
        mesh_sizes,
        expected_rate=case.expected_l2_rate,
        tol=tol,
    )
    h1_check = check_convergence_rate(
        h1_errors,
        mesh_sizes,
        expected_rate=case.expected_h1_rate,
        tol=tol,
    )
    diagnostics = {
        "case_id": case.id,
        "element_type": case.element_type,
        "material": case.material,
        "policy": case.policy,
        "policy_note": _policy_note(case),
        "mesh_levels": tuple(mesh_levels),
        "mesh_node_counts": mesh_node_counts,
        "l2_measured_rate": l2_check.measured_rate,
        "h1_measured_rate": h1_check.measured_rate,
        "l2_threshold": case.expected_l2_rate - tol,
        "h1_threshold": case.expected_h1_rate - tol,
    }
    return MMSConvergenceEntry(
        case=case,
        mesh_sizes=tuple(float(v) for v in mesh_sizes),
        l2_errors=tuple(float(v) for v in l2_errors),
        h1_errors=tuple(float(v) for v in h1_errors),
        l2_check=l2_check,
        h1_check=h1_check,
        diagnostics=diagnostics,
    )


def _run_interpolation_mms(
    element_type: MMSElementType,
    mesh_levels: tuple[int, ...],
    *,
    L: float,
    A: float,
) -> tuple[list[float], list[float], list[float], tuple[int, ...]]:
    l2_errors: list[float] = []
    h1_errors: list[float] = []
    mesh_sizes: list[float] = []
    node_counts: list[int] = []
    element = ElementFactory.create(element_type)

    for n in mesh_levels:
        mesh = structured_block_mesh(
            element_type,
            length=L,
            width=L,
            height=L,
            nx=n,
            ny=n,
            nz=n,
        )
        validate_positive_jacobians(mesh, element)
        l2_err, h1_err = _compute_interpolation_errors(mesh, element, L=L, A=A)
        l2_errors.append(l2_err)
        h1_errors.append(h1_err)
        mesh_sizes.append(L / n)
        node_counts.append(mesh.n_nodes)

    return l2_errors, h1_errors, mesh_sizes, tuple(node_counts)


def _compute_interpolation_errors(
    mesh: BenchmarkMesh,
    element: ElementIR,
    *,
    L: float,
    A: float,
) -> tuple[float, float]:
    l2_sq = 0.0
    h1_sq = 0.0

    for conn in mesh.connectivity:
        nodes = conn.astype(np.int64)
        X_elem = mesh.coordinates[nodes]
        u_elem = np.array(
            [mms_exact_displacement(*coords, L=L, A=A) for coords in X_elem],
            dtype=np.float64,
        )

        for q, point in enumerate(element.quadrature.points):
            xi, eta, zeta = (float(point[0]), float(point[1]), float(point[2]))
            weight = float(element.quadrature.weights[q])
            N = element.basis.evaluate(xi, eta, zeta)
            dN_dxi = element.basis.gradient(xi, eta, zeta)
            J0 = X_elem.T @ dN_dxi
            detJ0 = float(np.linalg.det(J0))
            if detJ0 <= 0.0:
                raise ValueError(f"Non-positive MMS Jacobian determinant {detJ0:.6e}")
            dN_dX = dN_dxi @ np.linalg.inv(J0)
            X_qp = N @ X_elem

            u_interp = N @ u_elem
            grad_interp = u_elem.T @ dN_dX
            u_exact = mms_exact_displacement(*X_qp, L=L, A=A)
            grad_exact = mms_exact_displacement_gradient(*X_qp, L=L, A=A)

            diff_u = u_interp - u_exact
            diff_grad = grad_interp - grad_exact
            l2_sq += weight * detJ0 * float(np.dot(diff_u, diff_u))
            h1_sq += weight * detJ0 * float(np.sum(diff_grad**2))

    return float(np.sqrt(l2_sq)), float(np.sqrt(h1_sq))


def _validate_case(case: MMSMatrixCase) -> None:
    if case.element_type not in ("hex8", "tet10", "hex20"):
        raise ValueError(f"Unsupported MMS element_type {case.element_type!r}")
    if case.material not in ("svk", "neo_hookean", "j2_power_law", "perzyna", "lemaitre_d0"):
        raise ValueError(f"Unsupported MMS material {case.material!r}")
    if case.expected_l2_rate <= 0.0 or case.expected_h1_rate <= 0.0:
        raise ValueError("expected MMS convergence rates must be positive")
    if case.policy not in ("svk_full_solve", "elastic_regime_interpolation"):
        raise ValueError(f"Unsupported MMS policy {case.policy!r}")


def _validate_mesh_levels(mesh_levels: tuple[int, ...] | list[int]) -> None:
    if len(mesh_levels) < 3:
        raise ValueError("At least 3 mesh levels are required for MMS convergence")
    if any(level <= 0 for level in mesh_levels):
        raise ValueError("MMS mesh levels must be positive")


def _policy_note(case: MMSMatrixCase) -> str:
    if case.policy == "svk_full_solve":
        return "Uses the existing Hex8 SVK MMS solve path without changing its public contract."
    if case.material == "svk":
        return "Elastic interpolation MMS over the SVK manufactured displacement field."
    return (
        f"{case.material} uses the documented elastic-regime MMS policy: "
        "small displacement, inactive dissipative evolution, and element error diagnostics."
    )


_DEFAULT_MATRIX = (
    MMSMatrixCase("hex8", "svk", expected_l2_rate=2.0, expected_h1_rate=1.0),
    MMSMatrixCase("tet10", "svk", expected_l2_rate=3.0, expected_h1_rate=2.0),
    MMSMatrixCase("hex20", "svk", expected_l2_rate=3.0, expected_h1_rate=2.0),
    MMSMatrixCase("hex8", "neo_hookean", expected_l2_rate=2.0, expected_h1_rate=1.0),
    MMSMatrixCase("hex8", "j2_power_law", expected_l2_rate=2.0, expected_h1_rate=1.0),
    MMSMatrixCase("hex8", "perzyna", expected_l2_rate=2.0, expected_h1_rate=1.0),
    MMSMatrixCase("hex8", "lemaitre_d0", expected_l2_rate=2.0, expected_h1_rate=1.0),
)
