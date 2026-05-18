"""Boundary condition codegen — compile IR BCs to arrays (P7.2).

Compiles Dirichlet and Neumann boundary conditions from face names
and parameters into dense numpy arrays suitable for the Newton driver.

All arrays use float64.  Masks use bool dtype.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.solver.mesh_io import HexMesh, get_face_nodes

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray


@dataclass(frozen=True)
class DirichletBC:
    """Compiled Dirichlet boundary condition.

    Attributes
    ----------
    mask : NDArray, shape (n_nodes, 3), dtype bool
        True where a DOF is constrained.
    values : NDArray, shape (n_nodes, 3), dtype float64
        Prescribed displacement values (only meaningful where mask is True).
    """

    mask: NDArray  # (n_nodes, 3) bool - True = constrained
    values: NDArray  # (n_nodes, 3) prescribed values

    def __post_init__(self) -> None:
        if self.mask.ndim != 2 or self.mask.shape[1] != 3:
            raise ValueError(f"mask must be (n, 3), got {self.mask.shape}")
        if self.values.ndim != 2 or self.values.shape[1] != 3:
            raise ValueError(f"values must be (n, 3), got {self.values.shape}")
        if self.mask.shape != self.values.shape:
            raise ValueError(f"mask shape {self.mask.shape} != values shape {self.values.shape}")


@dataclass(frozen=True)
class NeumannBC:
    """Compiled Neumann boundary condition.

    Attributes
    ----------
    force : NDArray, shape (n_nodes, 3), dtype float64
        External force contribution at each node.
    """

    force: NDArray  # (n_nodes, 3) external force contribution

    def __post_init__(self) -> None:
        if self.force.ndim != 2 or self.force.shape[1] != 3:
            raise ValueError(f"force must be (n, 3), got {self.force.shape}")


def compile_dirichlet(
    mesh: HexMesh,
    face_name: str,
    components: tuple[int, ...] = (0, 1, 2),
    value: float = 0.0,
) -> DirichletBC:
    """Compile a Dirichlet BC into mask and values arrays.

    Parameters
    ----------
    mesh : HexMesh
        The hex mesh.
    face_name : str
        Boundary face name (e.g., "x0").
    components : tuple[int, ...]
        Which displacement components to constrain (0=x, 1=y, 2=z).
    value : float
        Prescribed displacement value.

    Returns
    -------
    DirichletBC
        Compiled BC with mask and values arrays sized to the mesh.
    """
    face_nodes = get_face_nodes(mesh, face_name)

    mask = np.zeros((mesh.n_nodes, 3), dtype=bool)
    values = np.zeros((mesh.n_nodes, 3), dtype=np.float64)

    for c in components:
        mask[face_nodes, c] = True
        values[face_nodes, c] = value

    return DirichletBC(mask=mask, values=values)


def compile_neumann(
    mesh: HexMesh,
    face_name: str,
    traction: NDArray,  # (3,) traction vector [tx, ty, tz]
) -> NeumannBC:
    """Compile a Neumann BC into nodal force array.

    Distributes traction evenly over boundary face nodes.
    For structured mesh: ``f_node = traction * face_area / n_face_nodes``.

    Note: Uniform distribution is valid only for structured meshes with
    equal-size boundary elements. Surface quadrature is planned for Plan B.

    The face area is computed from the mesh dimensions and the face
    orientation.  For a structured rectangular mesh the face areas are:

    - x-faces (x0, x1): Ly * Lz
    - y-faces (y0, y1): Lx * Lz
    - z-faces (z0, z1): Lx * Ly

    Parameters
    ----------
    mesh : HexMesh
        The hex mesh.
    face_name : str
        Boundary face name (e.g., "x1").
    traction : NDArray, shape (3,)
        Traction vector [tx, ty, tz].

    Returns
    -------
    NeumannBC
        Compiled BC with force array sized to the mesh.
    """
    traction = np.asarray(traction, dtype=np.float64)
    face_nodes = get_face_nodes(mesh, face_name)
    n_face_nodes = len(face_nodes)

    # Compute face area from mesh coordinate extents
    coords = mesh.coords
    Lx = coords[:, 0].max() - coords[:, 0].min()
    Ly = coords[:, 1].max() - coords[:, 1].min()
    Lz = coords[:, 2].max() - coords[:, 2].min()

    axis = face_name[0]
    if axis not in ("x", "y", "z"):
        raise ValueError(
            f"Cannot determine face orientation from name '{face_name}'. "
            "Expected name starting with 'x', 'y', or 'z'."
        )
    if axis == "x":
        face_area = Ly * Lz
    elif axis == "y":
        face_area = Lx * Lz
    else:
        face_area = Lx * Ly

    if face_area < 1e-30:
        raise ValueError(
            f"Face '{face_name}' has near-zero area ({face_area:.3e}). Check mesh dimensions."
        )
    if n_face_nodes == 0:
        raise ValueError(f"No nodes found on face '{face_name}'. Check mesh boundary tags.")

    f_node = traction * face_area / n_face_nodes

    force = np.zeros((mesh.n_nodes, 3), dtype=np.float64)
    force[face_nodes] = f_node

    return NeumannBC(force=force)


def merge_dirichlet(bcs: list[DirichletBC], n_nodes: int) -> DirichletBC:
    """Merge multiple Dirichlet BCs into one.

    Later BCs in the list overwrite earlier ones where masks overlap.

    Parameters
    ----------
    bcs : list[DirichletBC]
        Individual Dirichlet BCs to merge.
    n_nodes : int
        Total number of nodes in the mesh.

    Returns
    -------
    DirichletBC
        Combined Dirichlet BC.
    """
    mask = np.zeros((n_nodes, 3), dtype=bool)
    values = np.zeros((n_nodes, 3), dtype=np.float64)

    for bc in bcs:
        # Where the new BC constrains, overwrite
        mask |= bc.mask
        values[bc.mask] = bc.values[bc.mask]

    return DirichletBC(mask=mask, values=values)


def merge_neumann(bcs: list[NeumannBC], n_nodes: int) -> NeumannBC:
    """Merge multiple Neumann BCs (sum forces).

    Parameters
    ----------
    bcs : list[NeumannBC]
        Individual Neumann BCs to merge.
    n_nodes : int
        Total number of nodes in the mesh.

    Returns
    -------
    NeumannBC
        Combined Neumann BC with summed forces.
    """
    force = np.zeros((n_nodes, 3), dtype=np.float64)

    for bc in bcs:
        force += bc.force

    return NeumannBC(force=force)


def apply_dirichlet_to_vector(v: NDArray, bc: DirichletBC) -> NDArray:
    """Zero constrained DOFs in a vector.

    Parameters
    ----------
    v : NDArray, shape (n_nodes, 3)
        Vector to modify.
    bc : DirichletBC
        Dirichlet BC specifying constrained DOFs.

    Returns
    -------
    NDArray, shape (n_nodes, 3)
        Copy of ``v`` with constrained DOFs set to zero.
    """
    out = v.copy()
    out[bc.mask] = 0.0
    return out


def apply_dirichlet_to_matvec(
    matvec_fn: Callable[[NDArray], NDArray],
    bc: DirichletBC,
) -> Callable[[NDArray], NDArray]:
    """Wrap a matvec to enforce Dirichlet BCs (zero constrained rows/cols).

    The wrapper zeros constrained DOFs in the input before calling the
    underlying matvec, and zeros constrained DOFs in the output.  This
    is equivalent to replacing constrained rows and columns of the system
    matrix with zeros (identity on the diagonal is handled separately
    by the solver).

    Parameters
    ----------
    matvec_fn : Callable[[NDArray], NDArray]
        Original matvec function operating on flat (n_dof,) vectors.
    bc : DirichletBC
        Dirichlet BC specifying constrained DOFs.

    Returns
    -------
    Callable[[NDArray], NDArray]
        Wrapped matvec that enforces Dirichlet BCs.
    """
    flat_mask = bc.mask.ravel()

    def wrapped(v: NDArray) -> NDArray:
        v_free = v.copy()
        v_free[flat_mask] = 0.0
        result = matvec_fn(v_free)
        result[flat_mask] = 0.0
        return result

    return wrapped
