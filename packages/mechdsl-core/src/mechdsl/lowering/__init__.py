"""FE localisation: ProblemIR → ElementIR, einsum string extraction."""

from mechdsl.lowering.einsum_extract import (
    TANGENT_MATVEC_APPLY_EINSUM,
    TANGENT_MATVEC_APPLY_NAME,
    build_tangent_matvec_plan,
    extract_einsum_specs,
    tangent_matvec_apply_spec,
)
from mechdsl.lowering.fe_localise import (
    EinsumSpec,
    LocalisationError,
    LocalisationResult,
    localise,
    localise_and_optimize,
)

__all__ = [
    "TANGENT_MATVEC_APPLY_EINSUM",
    "TANGENT_MATVEC_APPLY_NAME",
    "EinsumSpec",
    "LocalisationError",
    "LocalisationResult",
    "build_tangent_matvec_plan",
    "extract_einsum_specs",
    "localise",
    "localise_and_optimize",
    "tangent_matvec_apply_spec",
]
