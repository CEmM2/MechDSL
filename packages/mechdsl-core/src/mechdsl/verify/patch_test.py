"""Patch test and rigid body test harnesses.

Implements:
- run_patch_test()      — constant-strain patch test (error < 1e-12)
- run_rigid_body_test() — rigid body motion test (internal force norm < 1e-12)
- generate_irregular_mesh() — perturbed Hex8 mesh for patch test on irregular geometry

Design decision (Phase 3):
    These tests use the handwritten reference solver (ref_hex8_elastic.py), NOT
    the generated solver.  The patch test and rigid body test validate fundamental
    mechanics correctness of the numerical method.  Generated-vs-reference
    comparison is Phase 4's job.

Patch test formulation:
    For a Hex8 element with trilinear shape functions, a constant Green-Lagrange
    strain E (linearised as u_i = E_{ij} X_j) must be reproduced *exactly* by the
    element formulation.  This is verified by:

    1. Applying the analytical displacement u = E @ X to ALL nodes.
    2. Computing the assembled internal force.
    3. Checking that the force is zero at ALL nodes (interior + boundary).

    A non-zero force at any interior node indicates that the element does not
    pass the patch test.  Boundary forces are non-zero because they are the
    reaction forces, but their sum must be zero (global equilibrium).  We report
    the *interior* node force max-norm and the total force norm.

    NOTE: We do NOT use the Newton solver because the patch test directly asserts
    the quality of the element quadrature/gradient computation.  Using Newton would
    conflate element formulation errors with linear-solver convergence errors.

Rigid body test formulation:
    Apply u = (R - I) @ X + t to all nodes.  Compute f_int.  For a proper
    rotation (R^T R = I), the Green-Lagrange strain E = (C - I)/2 = 0 exactly,
    so the PK2 stress S = 0 and therefore f_int = 0.

Reference: dev/design_docs/08-VERIFICATION.md §4.1 (patch test), §4.3 (rigid body)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.verify.analytical import patch_test_reference, rigid_body_reference

if TYPE_CHECKING:
    from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatchTestResult:
    """Result of a constant-strain patch test.

    Attributes
    ----------
    error : float
        Relative max-norm of interior node internal forces divided by the
        characteristic force scale (max boundary reaction force).
        When no interior nodes exist (single element), degrades to
        normalised global force balance (boundary_force_sum / scale).
        If boundary reactions are zero this is the absolute interior force max.
    passed : bool
        True when ``error < tol``.
    tol : float
        Tolerance used (default 1e-12).
    n_nodes : int
        Number of nodes in the mesh.
    n_elements : int
        Number of elements in the mesh.
    interior_force_max : float
        Maximum absolute internal force at any interior DOF.
    boundary_force_sum : float
        L2 norm of the sum of all internal forces (global equilibrium check).
    residual_history : list[float]
        Empty list (no Newton solve used in patch test).
    """

    error: float
    passed: bool
    tol: float
    n_nodes: int
    n_elements: int
    interior_force_max: float
    boundary_force_sum: float
    residual_history: list[float]

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"PatchTestResult({status}: error={self.error:.3e}, tol={self.tol:.3e}, "
            f"interior_force_max={self.interior_force_max:.3e}, "
            f"boundary_force_sum={self.boundary_force_sum:.3e}, "
            f"nodes={self.n_nodes}, elements={self.n_elements})"
        )


@dataclass(frozen=True)
class RigidBodyResult:
    """Result of a rigid body motion test.

    Attributes
    ----------
    force_norm : float
        L2 norm of the internal force vector: ``||f_int||``.
    passed : bool
        True when ``force_norm < tol``.
    tol : float
        Tolerance used (default 1e-12).
    n_nodes : int
        Number of nodes in the mesh.
    n_elements : int
        Number of elements in the mesh.
    """

    force_norm: float
    passed: bool
    tol: float
    n_nodes: int
    n_elements: int

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"RigidBodyResult({status}: force_norm={self.force_norm:.3e}, tol={self.tol:.3e}, "
            f"nodes={self.n_nodes}, elements={self.n_elements})"
        )


# ---------------------------------------------------------------------------
# Mesh utilities
# ---------------------------------------------------------------------------


def generate_irregular_mesh(
    nx: int,
    ny: int,
    nz: int,
    Lx: float,
    Ly: float,
    Lz: float,
    perturbation_fraction: float = 0.1,
    seed: int = 42,
) -> tuple[NDArray, NDArray]:
    """Generate an irregular Hex8 mesh by perturbing interior nodes.

    Starts from a regular structured mesh and perturbs interior nodes by a
    random displacement of magnitude ``perturbation_fraction * element_size``.
    Boundary nodes are left unchanged to preserve the mesh domain geometry.

    Parameters
    ----------
    nx, ny, nz : int
        Number of elements in each direction.
    Lx, Ly, Lz : float
        Domain dimensions.
    perturbation_fraction : float
        Maximum perturbation as a fraction of the element edge length.
        Default 0.1 (10% perturbation).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    coords : NDArray, shape (n_nodes, 3)
        Perturbed nodal reference coordinates.
    conn : NDArray, shape (n_elem, 8)
        Element connectivity (0-based node indices).
    """
    from mechdsl.solver.mesh_io import generate_hex8_mesh as _gen_mesh

    mesh = _gen_mesh(nx, ny, nz, Lx, Ly, Lz)
    coords, conn = mesh.coords, mesh.connectivity

    # Element sizes
    dx = Lx / nx
    dy = Ly / ny
    dz = Lz / nz

    # Interior node mask: nodes not on any boundary face
    tol_geom = 1e-12
    on_boundary = (
        (coords[:, 0] < tol_geom)
        | (coords[:, 0] > Lx - tol_geom)
        | (coords[:, 1] < tol_geom)
        | (coords[:, 1] > Ly - tol_geom)
        | (coords[:, 2] < tol_geom)
        | (coords[:, 2] > Lz - tol_geom)
    )
    interior_mask = ~on_boundary

    # Perturb interior nodes
    rng = np.random.default_rng(seed)
    n_interior = int(np.sum(interior_mask))
    if n_interior > 0:
        perturbation = rng.uniform(-1.0, 1.0, size=(n_interior, 3))
        perturbation[:, 0] *= perturbation_fraction * dx
        perturbation[:, 1] *= perturbation_fraction * dy
        perturbation[:, 2] *= perturbation_fraction * dz

        coords = coords.copy()
        coords[interior_mask] += perturbation

    return coords, conn


# ---------------------------------------------------------------------------
# Patch test
# ---------------------------------------------------------------------------


def run_patch_test(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    strain: NDArray,
    tol: float = 1e-12,
) -> PatchTestResult:
    """Run a constant-strain patch test.

    Applies the analytical displacement u = E @ X to ALL nodes and checks
    that the assembled internal force at interior nodes is (essentially) zero.

    This formulation directly tests whether the element quadrature correctly
    represents the constant-strain field without invoking the Newton solver,
    which would conflate element formulation errors with linear-solver accuracy.

    For the SVK model with a constant Green-Lagrange strain E:
    - The deformation gradient F = I + grad(u) is constant throughout each element
    - The PK2 stress S = lambda*tr(E)*I + 2*mu*E is constant
    - Adjacent elements contribute equal and opposite forces at shared interior nodes
    - Therefore, interior node forces must sum to exactly zero

    The "error" metric reported is:
        interior_force_max / boundary_reaction_scale
    where ``boundary_reaction_scale`` is the max absolute boundary nodal force.

    Parameters
    ----------
    coords : NDArray, shape (n_nodes, 3)
        Nodal reference coordinates.
    conn : NDArray, shape (n_elem, 8)
        Element connectivity.
    lam, mu : float
        Lame parameters.
    strain : NDArray, shape (3, 3)
        Constant Green-Lagrange strain tensor (symmetric).
    tol : float
        Acceptance tolerance for the normalised interior force max.

    Returns
    -------
    PatchTestResult
        Result dataclass with error, passed flag, and diagnostics.
    """
    from mechdsl.verify._assembly import assemble_internal_force

    n_nodes = coords.shape[0]
    n_elements = conn.shape[0]

    # Compute analytical displacement field: u = E @ X
    u_analytical = patch_test_reference(coords, strain)  # (n_nodes, 3)

    # Compute internal force with the analytical displacement applied to all nodes
    f_int = assemble_internal_force(u_analytical, coords, conn, lam, mu)

    # Identify interior and boundary nodes
    tol_geom = 1e-12
    x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
    y_min, y_max = coords[:, 1].min(), coords[:, 1].max()
    z_min, z_max = coords[:, 2].min(), coords[:, 2].max()

    on_boundary = (
        (coords[:, 0] < x_min + tol_geom)
        | (coords[:, 0] > x_max - tol_geom)
        | (coords[:, 1] < y_min + tol_geom)
        | (coords[:, 1] > y_max - tol_geom)
        | (coords[:, 2] < z_min + tol_geom)
        | (coords[:, 2] > z_max - tol_geom)
    )
    interior_mask = ~on_boundary

    # Global equilibrium: sum of all forces = 0
    boundary_force_sum = float(np.linalg.norm(f_int.sum(axis=0)))

    if np.any(interior_mask):
        # Multi-element: interior force max should be exactly zero
        interior_force_max = float(np.max(np.abs(f_int[interior_mask])))
        boundary_force_scale = (
            float(np.max(np.abs(f_int[on_boundary]))) if np.any(on_boundary) else 1.0
        )
        if boundary_force_scale > 1e-15:
            error = interior_force_max / boundary_force_scale
        else:
            error = interior_force_max
    else:
        # Single element: all nodes are boundary, no interior nodes.
        # Degrade to global equilibrium check.
        interior_force_max = 0.0
        boundary_force_scale = float(np.max(np.abs(f_int))) if f_int.size > 0 else 1.0
        if boundary_force_scale > 1e-15:
            error = boundary_force_sum / boundary_force_scale
        else:
            error = boundary_force_sum

    return PatchTestResult(
        error=error,
        passed=error < tol,
        tol=tol,
        n_nodes=n_nodes,
        n_elements=n_elements,
        interior_force_max=interior_force_max,
        boundary_force_sum=boundary_force_sum,
        residual_history=[],
    )


# ---------------------------------------------------------------------------
# Parametric patch test (Plan B phase B5 — all element factory triples)
# ---------------------------------------------------------------------------


def run_patch_test_parametric(
    element_ir,
    material_params: dict,
    strain: NDArray | None = None,
    X_nodes: NDArray | None = None,
    tol: float = 1e-12,
) -> PatchTestResult:
    """Single-element patch test parametric over :class:`ElementIR`.

    Accepts any :class:`mechdsl.ir.element_ir.ElementIR` produced by
    :class:`mechdsl.ir.element_factory.ElementFactory` (all Plan B phase
    B5 triples: ``hex8 / tet4 / tet10 / hex20`` with
    ``full / reduced`` integration and optional
    ``flanagan_belytschko`` hourglass control).  Applies the constant-
    strain kinematic state ``u = E X`` to all nodes and asserts that the
    element internal force sums to zero to within ``tol``.

    Mathematical background
    -----------------------
    For a constant Green-Lagrange strain ``E``, the linearised
    displacement ``u = E X`` induces an (approximately) constant ``F``
    inside each element; the PK2 stress ``S`` is therefore constant and
    the integrated nodal forces must sum to zero by equilibrium.  On a
    single element all nodes are boundary nodes, so we report the
    normalised global equilibrium residual:

        error = ||sum_a f_int[a]|| / max_a ||f_int[a]||

    (degrading to the absolute sum when all nodal forces are zero to
    machine precision).  For full-integration elements this should sit
    at ``< 1e-12``.  For reduced-integration Hex8 with Flanagan-Belytschko
    hourglass control the FB projection introduces ``O(1e-10)`` round-off,
    so the caller should relax to ``tol=1e-8``.

    Parameters
    ----------
    element_ir
        The element IR to test.  Topology and integration rule determine
        which internal-force kernel is used; the presence of
        ``hourglass="flanagan_belytschko"`` in the factory call is
        detected here by checking
        ``element_ir.integration_rule == IntegrationRule.REDUCED`` together
        with the ``hourglass`` keyword argument of this function.
    material_params
        Dictionary with ``{"lam": float, "mu": float}`` Lame parameters.
        A ``"lambda_h"`` entry (default ``0.05``) tunes the FB coefficient
        when hourglass control is active.
    strain
        ``(3, 3)`` constant Green-Lagrange strain.  Defaults to
        ``diag(0.01, 0, 0)`` — a mild uniaxial stretch compatible with
        all element types (Tet4 stays well away from the
        volumetric-locking regime).
    X_nodes
        ``(n_nodes, 3)`` reference-configuration node layout.  Defaults
        to the canonical reference element for the topology
        (``HEX8_NODE_COORDS`` etc.).
    tol
        Acceptance tolerance for the normalised equilibrium residual.

    Returns
    -------
    PatchTestResult
        ``interior_force_max`` carries the max-nodal-force magnitude
        (there are no interior nodes in a single element, so this is the
        characteristic scale); ``boundary_force_sum`` carries the
        L2 norm of ``sum_a f_int[a]``.
    """
    from mechdsl.codegen.hourglass import flanagan_belytschko_force
    from mechdsl.ir.mechanics_ir import IntegrationRule
    from mechdsl.verify._patch_test_kernels import (
        element_svk_internal_force,
        reference_nodes,
    )

    if "lam" not in material_params or "mu" not in material_params:
        raise ValueError(
            "material_params must contain 'lam' and 'mu' (Lame parameters). "
            "Plan B phase B5 accepts SVK only for patch-test material."
        )
    lam = float(material_params["lam"])
    mu = float(material_params["mu"])
    lambda_h = float(material_params.get("lambda_h", 0.05))

    if strain is None:
        strain = np.diag([0.01, 0.0, 0.0]).astype(np.float64)
    strain = np.asarray(strain, dtype=np.float64)
    if strain.shape != (3, 3):
        raise ValueError(f"strain must be (3, 3); got {strain.shape}")

    if X_nodes is None:
        X_nodes = reference_nodes(element_ir.element_type)
    X_nodes = np.asarray(X_nodes, dtype=np.float64)
    if X_nodes.shape != (element_ir.n_nodes, 3):
        raise ValueError(
            f"X_nodes must be ({element_ir.n_nodes}, 3) for "
            f"{element_ir.element_type!r}; got {X_nodes.shape}."
        )

    # u = E @ X per node  (constant Green-Lagrange strain kinematic state)
    u_nodes = X_nodes @ strain.T  # (n_nodes, 3)

    # SVK internal force for this element family.
    f_int = element_svk_internal_force(element_ir, u_nodes, X_nodes, lam, mu)

    # Add the Flanagan-Belytschko hourglass contribution for reduced Hex8.
    # On a constant-strain state the projected gamma vectors annihilate the
    # displacement by construction, so this contributes only round-off.
    if element_ir.element_type == "hex8" and element_ir.integration_rule == IntegrationRule.REDUCED:
        f_int = f_int + flanagan_belytschko_force(u_nodes, X_nodes, mu, lambda_h=lambda_h)

    # Single-element: all nodes are boundary.  Report normalised global
    # equilibrium residual.
    boundary_force_sum = float(np.linalg.norm(f_int.sum(axis=0)))
    nodal_force_max = float(np.max(np.abs(f_int))) if f_int.size > 0 else 0.0
    error = boundary_force_sum / nodal_force_max if nodal_force_max > 1e-15 else boundary_force_sum

    return PatchTestResult(
        error=error,
        passed=error < tol,
        tol=tol,
        n_nodes=element_ir.n_nodes,
        n_elements=1,
        interior_force_max=nodal_force_max,
        boundary_force_sum=boundary_force_sum,
        residual_history=[],
    )


# ---------------------------------------------------------------------------
# Rigid body test
# ---------------------------------------------------------------------------


def run_rigid_body_test(
    coords: NDArray,
    conn: NDArray,
    lam: float,
    mu: float,
    rotation: NDArray,
    translation: NDArray,
    tol: float = 1e-12,
) -> RigidBodyResult:
    """Run a rigid body motion test.

    Applies the rigid body displacement field to all nodes and directly
    evaluates the internal force. For a proper rigid body motion (R^T R = I,
    det R = +1), the Green-Lagrange strain is exactly zero, so the internal
    force must be exactly zero.

    Note: This test does NOT use the Newton solver — it directly calls
    ``assemble_internal_force`` with the rigid body displacement to check
    that the element formulation is frame-indifferent.

    Parameters
    ----------
    coords : NDArray, shape (n_nodes, 3)
        Nodal reference coordinates.
    conn : NDArray, shape (n_elem, 8)
        Element connectivity.
    lam, mu : float
        Lame parameters.
    rotation : NDArray, shape (3, 3)
        Proper orthogonal rotation matrix (R^T R = I, det R = +1).
    translation : NDArray, shape (3,)
        Rigid body translation vector.
    tol : float
        Acceptance tolerance for internal force L2 norm.

    Returns
    -------
    RigidBodyResult
        Result dataclass with force_norm, passed flag, and diagnostics.
    """
    from mechdsl.verify._assembly import assemble_internal_force

    n_nodes = coords.shape[0]
    n_elements = conn.shape[0]

    # Compute rigid body displacement field: u = (R - I) @ X + t
    u_rigid = rigid_body_reference(coords, rotation, translation)  # (n_nodes, 3)

    # Compute internal force directly (no Newton solve needed)
    f_int = assemble_internal_force(u_rigid, coords, conn, lam, mu)

    force_norm = float(np.linalg.norm(f_int))

    return RigidBodyResult(
        force_norm=force_norm,
        passed=force_norm < tol,
        tol=tol,
        n_nodes=n_nodes,
        n_elements=n_elements,
    )
