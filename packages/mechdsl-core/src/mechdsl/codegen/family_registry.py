"""Layer 4b — contraction-family registry (Phase 9 / Task P9-1).

Authoritative families are defined in
``dev/design_docs/09-EINSUM-OPTIMISER.md §9``. This module is the
executable mirror of §9.2-9.4 plus a minimal pattern-matching
classifier used by the P9-1 spec-completeness tests.

P9-2 will wire :func:`classify_einsum_string` into the
``optimize_contraction`` / ``plan_contraction`` flow and attach the
resulting :class:`Family` to :class:`ContractionResult`. P9-1 only
ships the registry.
"""

from __future__ import annotations

import enum

__all__ = [
    "ELEMENT_BACKEND_COVERAGE",
    "EMISSION_SHAPES",
    "FAMILIES",
    "FAMILY_DESCRIPTIONS",
    "FAMILY_EMITTERS_ENABLED",
    "Family",
    "classify_einsum_string",
]


# Feature flag for the P9-2 rollout. Kept here (not in
# ``einsum_optimizer.py``) so that importing the registry does not
# trigger any heavy imports from the optimiser.
FAMILY_EMITTERS_ENABLED: bool = True


class Family(enum.Enum):
    """Named contraction-family identifiers.

    Every contraction emitted by a backend printer is classified into
    exactly one family. Families are empirical — each value corresponds
    to a shape that appears in the codebase today.
    """

    DISPLACEMENT_GRADIENT = "DISPLACEMENT_GRADIENT"
    FORCE_INTEGRATION = "FORCE_INTEGRATION"
    MATERIAL_TANGENT_CONTRACTION = "MATERIAL_TANGENT_CONTRACTION"
    RANK2_OUTER = "RANK2_OUTER"
    RANK2_SYMMETRIC_OUTER = "RANK2_SYMMETRIC_OUTER"
    TANGENT_DOUBLE_CONTRACTION = "TANGENT_DOUBLE_CONTRACTION"
    PUSH_FORWARD_RANK4 = "PUSH_FORWARD_RANK4"
    FALLBACK = "FALLBACK"


FAMILIES: tuple[Family, ...] = tuple(Family)


FAMILY_DESCRIPTIONS: dict[Family, str] = {
    Family.DISPLACEMENT_GRADIENT: (
        "Node-scatter of displacements onto quadrature-point gradients (exemplar: 'qaI,ai->qiI')."
    ),
    Family.FORCE_INTEGRATION: (
        "Internal-force integrand: B^T . P per quadrature point (exemplar: 'qaI,qiI->qai')."
    ),
    Family.MATERIAL_TANGENT_CONTRACTION: (
        "Element tangent sandwich with B on both sides (exemplar: 'qaI,qiIjJ,qbJ->qaibj')."
    ),
    Family.RANK2_OUTER: ("Dyadic outer product of two rank-2 tensors (exemplar: 'ij,kl->ijkl')."),
    Family.RANK2_SYMMETRIC_OUTER: (
        "Minor-symmetric identity / symmetric outer product "
        "(exemplar: 'ik,jl->ijkl' or 'il,jk->ijkl')."
    ),
    Family.TANGENT_DOUBLE_CONTRACTION: (
        "Rank-4 : rank-2 double contraction — stress linearisation (exemplar: 'ijkl,kl->ij')."
    ),
    Family.PUSH_FORWARD_RANK4: (
        "Four-leg deformation push-forward of a rank-4 tensor (exemplar: 'iI,jJ,kK,lL,IJKL->ijkl')."
    ),
    Family.FALLBACK: ("Unclassified contraction — forces the Tier 3 runtime fallback path."),
}


# Per-backend emission shapes. Keys are (family, backend); values are
# brief one-line identifiers mirroring §9.3. Backend strings are lower-case.
EMISSION_SHAPES: dict[tuple[Family, str], str] = {
    (Family.DISPLACEMENT_GRADIENT, "taichi"): "ti.static nest over (i,I); runtime loop over a",
    (Family.DISPLACEMENT_GRADIENT, "mfem"): "for(int a) for(int i) with DS(a,I) flat indexing",
    (
        Family.DISPLACEMENT_GRADIENT,
        "moose",
    ): "RankTwoTensor F assembled via MultABt (action-driven)",
    (
        Family.FORCE_INTEGRATION,
        "taichi",
    ): "ti.static nest over (i,I); runtime a; accumulate f_elem[a,i]",
    (Family.FORCE_INTEGRATION, "mfem"): "for(int a) { acc += FS(i,j)*DS(a,j); } flat loops",
    (
        Family.FORCE_INTEGRATION,
        "moose",
    ): "_stress[_qp] consumed by TensorMechanicsAction (no explicit loop)",
    (
        Family.MATERIAL_TANGENT_CONTRACTION,
        "taichi",
    ): "ti.static on (i,j,I,J); runtime (a,b); split into two rank-3 steps",
    (Family.MATERIAL_TANGENT_CONTRACTION, "mfem"): "Voigt-projected B^T C_eng B with 6x6 tangent",
    (
        Family.MATERIAL_TANGENT_CONTRACTION,
        "moose",
    ): "_Jacobian_mult[_qp] RankFourTensor (action-driven)",
    (Family.RANK2_OUTER, "taichi"): "inline 4-deep ti.static nest C4[i,j,k,l] = A[i,j]*B[k,l]",
    (Family.RANK2_OUTER, "mfem"): "flat loop over i,j,k,l with linearised DenseTensor<4> layout",
    (Family.RANK2_OUTER, "moose"): "RankFourTensor::outerProduct(A, B)",
    (
        Family.RANK2_SYMMETRIC_OUTER,
        "taichi",
    ): "two ti.static nests summed: A[i,k]*B[j,l] + A[i,l]*B[j,k]",
    (Family.RANK2_SYMMETRIC_OUTER, "mfem"): "flat loop with remapped indices; no native helper",
    (
        Family.RANK2_SYMMETRIC_OUTER,
        "moose",
    ): "C.fillSymmetricFromInputVector or manual four-deep loop",
    (
        Family.TANGENT_DOUBLE_CONTRACTION,
        "taichi",
    ): "ti.static 4-deep nest sig[i,j] = sum_{k,l} C4[i,j,k,l]*eps[k,l]",
    (
        Family.TANGENT_DOUBLE_CONTRACTION,
        "mfem",
    ): "for(i,j) { for(k,l) sig(i,j) += C(i,j,k,l)*eps(k,l); }",
    (Family.TANGENT_DOUBLE_CONTRACTION, "moose"): "RankFourTensor::innerContract(strain) built-in",
    (Family.PUSH_FORWARD_RANK4, "taichi"): "pairwise split with ti.Matrix intermediates",
    (Family.PUSH_FORWARD_RANK4, "mfem"): "unsupported; delegates to FALLBACK emitter",
    (
        Family.PUSH_FORWARD_RANK4,
        "moose",
    ): "F.initialContraction(C_material, F) push-forward primitive",
    (Family.FALLBACK, "taichi"): "innermost dim ti.static; outer indices runtime for-loops",
    (Family.FALLBACK, "mfem"): "fully runtime nested loops; no unrolling",
    (Family.FALLBACK, "moose"): "fully runtime nested loops over tensor-op components",
}


# Per-element coverage: which families each (element, backend) pair
# must have an emission shape for. Tet4/Tet10/Hex20 reuse the Hex8
# family set because einsum_extract will produce identically-shaped
# einsum strings once those element types are unlocked (only n_nodes
# / n_qp differ).
_HEX8_TAICHI: frozenset[Family] = frozenset(
    {
        Family.DISPLACEMENT_GRADIENT,
        Family.FORCE_INTEGRATION,
        Family.MATERIAL_TANGENT_CONTRACTION,
        Family.TANGENT_DOUBLE_CONTRACTION,
    }
)
_HEX8_MFEM: frozenset[Family] = frozenset(
    {
        Family.DISPLACEMENT_GRADIENT,
        Family.FORCE_INTEGRATION,
        Family.MATERIAL_TANGENT_CONTRACTION,
        Family.TANGENT_DOUBLE_CONTRACTION,
    }
)
_HEX8_MOOSE: frozenset[Family] = frozenset(
    {
        Family.MATERIAL_TANGENT_CONTRACTION,
        Family.TANGENT_DOUBLE_CONTRACTION,
        Family.RANK2_OUTER,
        Family.RANK2_SYMMETRIC_OUTER,
    }
)


ELEMENT_BACKEND_COVERAGE: dict[tuple[str, str], set[Family]] = {
    ("hex8", "taichi"): set(_HEX8_TAICHI),
    ("hex8", "mfem"): set(_HEX8_MFEM),
    ("hex8", "moose"): set(_HEX8_MOOSE),
    ("tet4", "taichi"): set(_HEX8_TAICHI),
    ("tet4", "mfem"): set(_HEX8_MFEM),
    ("tet4", "moose"): set(_HEX8_MOOSE),
    ("tet10", "taichi"): set(_HEX8_TAICHI),
    ("tet10", "mfem"): set(_HEX8_MFEM),
    ("tet10", "moose"): set(_HEX8_MOOSE),
    ("hex20", "taichi"): set(_HEX8_TAICHI) | {Family.FALLBACK},
    ("hex20", "mfem"): set(_HEX8_MFEM) | {Family.FALLBACK},
    ("hex20", "moose"): set(_HEX8_MOOSE) | {Family.FALLBACK},
}


_EXACT_MATCH: dict[str, Family] = {
    "qaI,ai->qiI": Family.DISPLACEMENT_GRADIENT,
    "qaI,qiI->qai": Family.FORCE_INTEGRATION,
    "qaI,qiIjJ,qbJ->qaibj": Family.MATERIAL_TANGENT_CONTRACTION,
    "ij,kl->ijkl": Family.RANK2_OUTER,
    "ik,jl->ijkl": Family.RANK2_SYMMETRIC_OUTER,
    "il,jk->ijkl": Family.RANK2_SYMMETRIC_OUTER,
    "ijkl,kl->ij": Family.TANGENT_DOUBLE_CONTRACTION,
    "iI,jJ,kK,lL,IJKL->ijkl": Family.PUSH_FORWARD_RANK4,
}


def classify_einsum_string(
    einsum_string: str,
    operand_shapes: list[tuple[int, ...]],
) -> Family:
    """Classify an einsum contraction into a named :class:`Family`.

    This is the P9-1 design scaffold. Unrecognised strings resolve to
    :attr:`Family.FALLBACK`; P9-2 will refine the pattern-matching
    using operand shapes to split coarser families if needed.
    """
    _ = operand_shapes  # reserved for P9-2 refinement
    if einsum_string in _EXACT_MATCH:
        return _EXACT_MATCH[einsum_string]

    if "->" in einsum_string:
        lhs, rhs = einsum_string.split("->", maxsplit=1)
        inputs = lhs.split(",")
        if len(inputs) == 2 and all(len(op) == 2 for op in inputs) and len(rhs) == 4:
            a, b = inputs
            if rhs == a + b:
                return Family.RANK2_OUTER
            if set(rhs) == set(a) | set(b):
                return Family.RANK2_SYMMETRIC_OUTER
        if len(inputs) == 2 and {len(inputs[0]), len(inputs[1])} == {4, 2} and len(rhs) == 2:
            return Family.TANGENT_DOUBLE_CONTRACTION

    return Family.FALLBACK
