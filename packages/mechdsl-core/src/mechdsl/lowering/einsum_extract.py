"""Extract einsum strings from Element IR for the optimiser.

This is the canonical location for einsum extraction, per ``.claude/rules/ir.md``.
The function is deterministic and runs once per localisation pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
