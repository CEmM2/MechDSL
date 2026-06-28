"""Extract einsum strings from Element IR for the optimiser.

This is the canonical location for einsum extraction, per ``.claude/rules/ir.md``.
The function is deterministic and runs once per localisation pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mechdsl.codegen.artifact import ContractionPlan
    from mechdsl.ir.element_ir import ElementIR

from mechdsl.lowering.fe_localise import EinsumSpec


def extract_einsum_specs(element_ir: ElementIR) -> dict[str, EinsumSpec]:
    """Extract einsum specifications from an ElementIR.

    Reads element geometry (n_nodes, dim, n_quadrature_points) from the
    ElementIR and returns a dict of einsum specs keyed by operation name.

    Parameters
    ----------
    element_ir : ElementIR
        The element-level IR containing basis, quadrature, and topology.

    Returns
    -------
    dict[str, EinsumSpec]
        Mapping from operation name to EinsumSpec.  For Hex8 TL, the
        keys are: ``strain_displacement``, ``internal_force``,
        ``tangent_matvec``.

    Raises
    ------
    ValueError
        If the element type is not supported (only ``"hex8"`` for MVP).
    """
    if element_ir.element_type != "hex8":
        raise ValueError(
            f"Unsupported element type '{element_ir.element_type}' for "
            "einsum extraction. Only 'hex8' is supported in MVP. "
            "Tet4/Tet10 are planned for Plan B."
        )

    n_qp = element_ir.quadrature.n_points
    n_nodes = element_ir.n_nodes
    dim = element_ir.dim

    # 1. strain_displacement
    #    F_{iI} = delta_{iI} + sum_a( u_{ai} * dN_a/dX_I )
    #    The einsum captures the displacement-gradient contribution:
    #    dN(q,a,I) contracted with u(a,i) -> grad_u(q,i,I)
    strain_displacement = EinsumSpec(
        name="strain_displacement",
        einsum_string="qaI,ai->qiI",
        operand_shapes=((n_qp, n_nodes, dim), (n_nodes, dim)),
        result_shape=(n_qp, dim, dim),
        description=(
            "Displacement gradient at quadrature points: "
            "dN(q,a,I) x u(a,i) -> grad_u(q,i,I).  "
            "Add identity to obtain deformation gradient F."
        ),
    )

    # 2. internal_force
    #    f_{ai} = sum_q( w_q * detJ_q * dN_a/dX_I(q) * P_{iI}(q) )
    #    Core contraction per quadrature point (before weighting):
    #    dN(q,a,I) contracted with P(q,i,I) -> f(q,a,i)
    internal_force = EinsumSpec(
        name="internal_force",
        einsum_string="qaI,qiI->qai",
        operand_shapes=((n_qp, n_nodes, dim), (n_qp, dim, dim)),
        result_shape=(n_qp, n_nodes, dim),
        description=(
            "Internal force integration: "
            "dN(q,a,I) x P(q,i,I) -> f(q,a,i).  "
            "Weighted sum over quadrature points gives element "
            "internal force vector."
        ),
    )

    # 3. tangent_matvec
    #    K_{aibj} = sum_q( w_q * detJ_q * dN_a/dX_I * A_{iIjJ} * dN_b/dX_J )
    #    Combined einsum (conceptual, before splitting by the optimiser):
    tangent_matvec = EinsumSpec(
        name="tangent_matvec",
        einsum_string="qaI,qiIjJ,qbJ->qaibj",
        operand_shapes=(
            (n_qp, n_nodes, dim),
            (n_qp, dim, dim, dim, dim),
            (n_qp, n_nodes, dim),
        ),
        result_shape=(n_qp, n_nodes, dim, n_nodes, dim),
        description=(
            "Consistent tangent stiffness: "
            "dN(q,a,I) x A(q,i,I,j,J) x dN(q,b,J) -> K(q,a,i,b,j).  "
            "The einsum optimiser may split this into two contractions."
        ),
    )

    return {
        "strain_displacement": strain_displacement,
        "internal_force": internal_force,
        "tangent_matvec": tangent_matvec,
    }


# ---------------------------------------------------------------------------
# Matrix-free tangent matvec (PlanJune14 P3-1)
# ---------------------------------------------------------------------------
#
# The ``tangent_matvec`` spec above is the *full* per-quadrature element
# tangent stiffness ``K(q,a,i,b,j) = dN(q,a,I) A(q,i,I,j,J) dN(q,b,J)``. The
# matrix-free operator (D-A: never store element tangents) instead applies
# that tangent directly to a direction field ``v(b,j)`` at each matvec:
#
#     Kv(q,a,i) = sum_{b,J,j,I} dN(q,a,I) A(q,i,I,j,J) dN(q,b,J) v(b,j)
#
# i.e. the single contraction ``qaI,qiIjJ,qbJ,bj->qai``. Folding ``v`` into
# the contraction (rather than forming K first) lets the einsum optimiser
# pick a path that contracts the node index ``b`` against ``v`` early,
# collapsing the rank-5 K(q,a,i,b,j) intermediate to a rank-3 per-qp result
# and keeping the unrolled-line count well inside the @ti.func budget.
#
# This is the production replacement for the PJ-1 hand-written spike tangent
# kernel. P3-2 consumes the resulting ContractionPlan to emit the matvec
# @ti.kernel; nothing here touches the backend printer.

# Public name of the matrix-free tangent matvec contraction. P3-2 keys on
# this when locating the matvec plan among an element's contraction plans.
TANGENT_MATVEC_APPLY_NAME = "tangent_matvec_apply"

# The matrix-free tangent matvec subscripts: apply the consistent tangent
# A(q,i,I,j,J) to a direction v(b,j) via the two B-operators dN, summing the
# node/material/spatial dummies to leave Kv(q,a,i).
TANGENT_MATVEC_APPLY_EINSUM = "qaI,qiIjJ,qbJ,bj->qai"


def tangent_matvec_apply_spec(element_ir: ElementIR) -> EinsumSpec:
    """Build the matrix-free tangent matvec einsum spec for an ElementIR.

    Unlike :func:`extract_einsum_specs`' ``tangent_matvec`` entry — which is
    the *full* rank-5 element tangent ``K(q,a,i,b,j)`` — this spec already
    folds the direction field ``v(b,j)`` into the contraction, yielding the
    per-quadrature matrix-free product ``Kv(q,a,i)``. Operand order is
    ``(dN, A, dN, v)`` matching ``TANGENT_MATVEC_APPLY_EINSUM``.

    The spec is kept out of the ``extract_einsum_specs`` dict deliberately:
    that dict's three-key contract (``strain_displacement``,
    ``internal_force``, ``tangent_matvec``) is pinned by existing tests and
    golden artifacts. The matvec is an additional, optimiser-only view used
    by the matrix-free codegen path (PlanJune14 P3-2).

    Parameters
    ----------
    element_ir : ElementIR
        The element-level IR. Only ``hex8`` is supported in the MVP.

    Returns
    -------
    EinsumSpec
        The ``tangent_matvec_apply`` spec with operand shapes
        ``(dN, A, dN, v)`` and result shape ``(n_qp, n_nodes, dim)``.

    Raises
    ------
    ValueError
        If the element type is not ``hex8`` (mirrors
        :func:`extract_einsum_specs`).
    """
    if element_ir.element_type != "hex8":
        raise ValueError(
            f"Unsupported element type '{element_ir.element_type}' for "
            "tangent matvec extraction. Only 'hex8' is supported in MVP. "
            "Tet4/Tet10 are planned for Plan B."
        )

    n_qp = element_ir.quadrature.n_points
    n_nodes = element_ir.n_nodes
    dim = element_ir.dim

    return EinsumSpec(
        name=TANGENT_MATVEC_APPLY_NAME,
        einsum_string=TANGENT_MATVEC_APPLY_EINSUM,
        operand_shapes=(
            (n_qp, n_nodes, dim),  # dN(q,a,I)
            (n_qp, dim, dim, dim, dim),  # A(q,i,I,j,J)
            (n_qp, n_nodes, dim),  # dN(q,b,J)
            (n_nodes, dim),  # v(b,j)
        ),
        result_shape=(n_qp, n_nodes, dim),
        description=(
            "Matrix-free tangent matvec: "
            "dN(q,a,I) x A(q,i,I,j,J) x dN(q,b,J) x v(b,j) -> Kv(q,a,i).  "
            "The consistent tangent applied to a direction without ever "
            "forming the element stiffness K(q,a,i,b,j)."
        ),
    )


def build_tangent_matvec_plan(element_ir: ElementIR) -> ContractionPlan:
    """Produce the opt_einsum-optimised ContractionPlan for the matvec.

    Routes the :func:`tangent_matvec_apply_spec` contraction through the
    Layer-4b einsum optimiser (``codegen/einsum_optimizer``) and converts the
    resulting :class:`ContractionResult` into the persisted
    :class:`~mechdsl.codegen.artifact.ContractionPlan`. The plan records the
    opt_einsum contraction path, estimated FLOPs, tier, and template family,
    exactly as :func:`mechdsl.lowering.fe_localise.localise_and_optimize`
    does for the three standard specs.

    The matrix-free tangent operator (PlanJune14 P3-2) *is* this optimised
    contraction applied to ``v`` — the printer emits the recorded path rather
    than hand-rolling the contraction.

    Parameters
    ----------
    element_ir : ElementIR
        The element-level IR (hex8 only in the MVP).

    Returns
    -------
    ContractionPlan
        The optimiser view of the matvec contraction, ready to ride in an
        :class:`~mechdsl.codegen.artifact.ArtifactBundle`.

    Raises
    ------
    ValueError
        If the element type is not ``hex8`` (propagated from
        :func:`tangent_matvec_apply_spec`).
    mechdsl.codegen.einsum_optimizer.BudgetExceededError
        If the contraction exceeds the absolute JIT budget ceiling — never
        expected for Hex8 SVK (the optimised path estimates ~203 lines,
        Tier 2, well inside the 512-line @ti.func budget).
    """
    # Lazy imports keep einsum_extract free of the codegen import chain at
    # module load (mirrors fe_localise.localise_and_optimize).
    from mechdsl.codegen.artifact import ContractionPlan as _CP
    from mechdsl.codegen.einsum_optimizer import optimize_contraction as _opt

    spec = tangent_matvec_apply_spec(element_ir)
    result = _opt(spec.einsum_string, list(spec.operand_shapes))

    return _CP(
        einsum_string=result.einsum_string,
        contraction_path=result.contraction_path,
        estimated_flops=int(result.estimated_flops),
        tier=int(result.tier),
        family=result.family.name,
    )
