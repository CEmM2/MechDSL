"""Lower Neumann ``BoundaryCondition`` to per-node force contributions.

Bridges the IR layer (``mechdsl.ir.mechanics_ir.BoundaryCondition``) to the
codegen-layer primitives in ``mechdsl.codegen.boundary_codegen``. Introduced
in post_recovery_plan Phase 1 (P1-3) so that directive-driven Neumann BCs
flow through the pipeline ``LaTeX → IR → lowering → codegen`` without a
manual numeric injection.

Typical usage::

    from mechdsl.lowering.boundary import lower_neumann, per_node_contributions

    bc = problem_ir.boundaries[0]  # Neumann BC with vector traction
    nbc = lower_neumann(bc, mesh)  # NeumannBC with (n_nodes, 3) force array
    contribs = per_node_contributions(bc, mesh)  # sparse (node_id, force) list

The single-face surface tag form is exhaustively tested. Multi-face tags
(a single ``surface_tag`` whose boundary_tags entry covers nodes from
several physical faces) work as long as the tag name still starts with
``x|y|z`` because the underlying ``compile_neumann`` derives face area
from that axis prefix; see ``boundary_codegen.compile_neumann`` for the
full structured-mesh contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from mechdsl.codegen.boundary_codegen import NeumannBC, compile_neumann
from mechdsl.ir.mechanics_ir import BCType, BoundaryCondition

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy.typing import NDArray

    from mechdsl.solver.mesh_io import HexMesh


@dataclass(frozen=True)
class NodalForceContribution:
    """A single node's external-force contribution from a Neumann BC.

    The lowering pass returns a sparse list of these so the codegen layer
    can decide whether to materialize them into a dense ``f_ext`` field
    or iterate them directly in an emitted kernel.
    """

    node_id: int
    force: tuple[float, float, float]


def resolve_traction_vector(
    bc: BoundaryCondition,
    traction_registry: Mapping[str, NDArray | tuple[float, float, float] | list[float]]
    | None = None,
) -> NDArray:
    """Resolve a BC's traction spec to a length-3 numeric numpy array.

    The IR allows ``traction`` to be either a numeric tuple (post P1-1
    directive-driven form) or a symbolic string (legacy form like
    ``"t_bar"``). Numeric forms pass through; symbolic forms are looked up
    in ``traction_registry`` if supplied, otherwise an explicit error
    points at the missing registry mapping.
    """
    if bc.traction is None:
        # Should already be caught by IR-layer validation, but guard here too
        # so callers that bypass the dataclass (e.g. dicts) still see a
        # consistent error message.
        raise ValueError(
            f"BoundaryCondition(name={bc.name!r}) has no traction; "
            "post_recovery_plan Phase 1 (P1-3) requires Neumann BCs to "
            "carry a traction vector or registered symbol."
        )
    if isinstance(bc.traction, tuple):
        return np.asarray(bc.traction, dtype=np.float64)
    # Symbolic-string form: look up in the registry.
    if traction_registry is None or bc.traction not in traction_registry:
        raise ValueError(
            f"BoundaryCondition(name={bc.name!r}) traction symbol "
            f"{bc.traction!r} not found in traction_registry. "
            "Pass an explicit numeric traction (e.g. from a "
            "'--traction \"x y z\"' directive) or supply a registry "
            "mapping symbols to vectors."
        )
    return np.asarray(traction_registry[bc.traction], dtype=np.float64)


def lower_neumann(
    bc: BoundaryCondition,
    mesh: HexMesh,
    traction_registry: Mapping[str, NDArray | tuple[float, float, float] | list[float]]
    | None = None,
) -> NeumannBC:
    """Lower a Neumann ``BoundaryCondition`` to a ``NeumannBC`` force array.

    Resolves the surface tag (falling back to ``bc.name`` when
    ``surface_tag`` is unset, per ``BoundaryCondition.effective_surface_tag``)
    to a mesh face, resolves the traction to a numeric 3-vector, and
    delegates to ``compile_neumann`` for the per-node distribution.
    """
    if bc.bc_type != BCType.NEUMANN:
        raise ValueError(
            f"lower_neumann() received bc_type={bc.bc_type!r} for "
            f"BoundaryCondition(name={bc.name!r}); only NEUMANN BCs lower "
            "to nodal forces."
        )
    traction_vec = resolve_traction_vector(bc, traction_registry)
    surface_tag = bc.effective_surface_tag
    return compile_neumann(mesh, surface_tag, traction_vec)


def per_node_contributions(
    bc: BoundaryCondition,
    mesh: HexMesh,
    traction_registry: Mapping[str, NDArray | tuple[float, float, float] | list[float]]
    | None = None,
    *,
    zero_tol: float = 0.0,
) -> list[NodalForceContribution]:
    """Sparse list of ``(node_id, force)`` entries for a Neumann BC.

    Iterates the dense ``NeumannBC.force`` array and emits one entry per
    node whose force vector exceeds ``zero_tol`` in absolute value. With
    the default ``zero_tol=0.0`` only exactly-zero rows are dropped, so
    nodes outside the tagged surface contribute nothing — matching the
    P1-3 acceptance "non-tagged surface elements receive zero
    contribution".
    """
    nbc = lower_neumann(bc, mesh, traction_registry)
    contribs: list[NodalForceContribution] = []
    for node_id in range(nbc.force.shape[0]):
        f = nbc.force[node_id]
        if np.any(np.abs(f) > zero_tol):
            contribs.append(
                NodalForceContribution(
                    node_id=int(node_id),
                    force=(float(f[0]), float(f[1]), float(f[2])),
                )
            )
    return contribs


__all__ = [
    "NodalForceContribution",
    "lower_neumann",
    "per_node_contributions",
    "resolve_traction_vector",
]
