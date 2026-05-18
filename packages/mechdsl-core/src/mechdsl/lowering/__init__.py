"""FE localisation: ProblemIR → ElementIR, einsum string extraction."""

from mechdsl.lowering.einsum_extract import extract_einsum_specs
from mechdsl.lowering.fe_localise import (
    EinsumSpec,
    LocalisationError,
    LocalisationResult,
    localise,
    localise_and_optimize,
)

__all__ = [
    "EinsumSpec",
    "LocalisationError",
    "LocalisationResult",
    "extract_einsum_specs",
    "localise",
    "localise_and_optimize",
]
