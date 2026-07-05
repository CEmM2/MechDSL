"""MechDSL lawgen — constitutive-law emission for the ticonstit target.

MFront-mimic Cycle M0. Phase 1 lands the emission *contracts* here; Phase 2
adds the lowerer that consumes them. The two public contracts,
:class:`TiconstitTarget` (target profile) and :class:`PlasticityCarrierSpec`
(one carrier law), are the sole shared types between the CLI and the lowerer.
"""

from __future__ import annotations

from mechdsl.lawgen.contracts import (
    TICONSTIT_CONTRACT_ID,
    TICONSTIT_PACKAGE,
    PlasticityCarrierSpec,
    TiconstitTarget,
)
from mechdsl.lawgen.manifest import (
    GENERATED_BY,
    LAWS_ENTRY_FIELDS,
    compute_input_formula_hash,
    emit_manifest,
    formula_matches_spec,
    write_manifest,
)

__all__ = [
    "GENERATED_BY",
    "LAWS_ENTRY_FIELDS",
    "TICONSTIT_CONTRACT_ID",
    "TICONSTIT_PACKAGE",
    "PlasticityCarrierSpec",
    "TiconstitTarget",
    "compute_input_formula_hash",
    "emit_manifest",
    "formula_matches_spec",
    "write_manifest",
]
