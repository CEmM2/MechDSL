"""Plan-tests for Task P3-3: manifest emitter matching Cycle 0 _manifest.json schema.

Plan: dev/plans/mfront_cycleM0.md (lines 104-106) — MFront-mimic Cycle M0, Phase 3.
Deliverable under test: mechdsl.lawgen.manifest — emit_manifest(spec, ...) + write_manifest(...).

Six fields matching Cycle 0 _manifest.json: source_hash, generated_by,
target_contract, exports, parameters, tests (the real Cycle 0 laws entry has nine
fields — name/kind/source added — this asserts the six the AC names are present).
generated_by = "mechdsl-lawgen/<version>".

⚠️ RECONCILIATION (from Phase-2 handoff, RESOLVED in P3-3): the AC text says
source_hash matches LoweredResult.source_hash (emitted-lines hash), but Cycle 0's
manifest source_hash is the hash of the canonical INPUT formula string. P3-3
reconciled to Cycle 0's convention (manifest.compute_input_formula_hash hashes the
input formula verbatim/UTF-8) so P4-2 can byte-verify against the real
_manifest.json. These tests assert against the reconciled input-formula convention.
Cross-repo discipline (R3): the Cycle 0 published hash is transcribed as a literal
constant here, never imported from NumerixWeave.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import sympy as sp

from mechdsl.lawgen.contracts import PlasticityCarrierSpec
from mechdsl.lawgen.manifest import (
    compute_input_formula_hash,
    emit_manifest,
    write_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path

# Cycle 0's canonical SwiftVoce R formula string and its published source_hash
# (transcribed from NumerixWeave libs/ticonstit/.../generated/_manifest.json — read
# as data, never imported: R3). The input-formula-hash convention reproduces it.
_CYCLE0_R_FORMULA = "R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)"
_CYCLE0_R_SOURCE_HASH = "7b5af3a8bb79c2e44e0055a7076dd2c9de2ce8c75eb2e262b80bb4e0232d557f"


def _swift_voce_entry() -> dict[str, object]:
    """emit_manifest for a SwiftVoce carrier matching Cycle 0's R formula."""
    p, edot, T = sp.symbols("p edot T")
    sigma0, Q, b, K, p0, n = sp.symbols("sigma0 Q b K p0 n")
    R = sigma0 + Q * (1 - sp.exp(-b * p)) + K * ((p + p0) ** n - p0**n)
    spec = PlasticityCarrierSpec(
        name="swift_voce",
        parameters=("sigma0", "Q", "b", "K", "p0", "n"),
        expressions={"R": R, "H": sp.Integer(1), "Q": sp.Integer(1)},
        variable_bindings={"p": p, "edot": edot, "T": T},
    )
    return emit_manifest(
        spec,
        input_formula=_CYCLE0_R_FORMULA,
        target_contract="SwiftVoce",
        exports="SwiftVoce",
        source="swift_voce.py",
        tests=["tests/generated/test_swift_voce.py"],
    )


class TestTaskP3_3:
    """Tests for Task P3-3: manifest emitter. AC covered: 1-5."""

    @pytest.mark.unit
    def test_manifest_has_all_six_required_fields(self) -> None:
        """Verifies: the emitted manifest entry has all six Cycle-0 fields.
        AC2/AC4: source_hash, generated_by, target_contract, exports, parameters, tests.
        Passes when: every one of the six keys is present."""
        entry = _swift_voce_entry()
        for required_field in (
            "source_hash",
            "generated_by",
            "target_contract",
            "exports",
            "parameters",
            "tests",
        ):
            assert required_field in entry, f"manifest entry missing {required_field!r}"

    @pytest.mark.unit
    def test_manifest_source_hash_matches_lowered_result(self) -> None:
        """Verifies: the manifest's source_hash is the compile source hash.
        AC3 (reconciled to Cycle 0): source_hash is the hash of the canonical INPUT
        formula string, and it reproduces Cycle 0's published value.
        Passes when: source_hash == compute_input_formula_hash(formula) == Cycle 0 hash."""
        entry = _swift_voce_entry()
        assert entry["source_hash"] == compute_input_formula_hash(_CYCLE0_R_FORMULA)
        assert entry["source_hash"] == _CYCLE0_R_SOURCE_HASH

    @pytest.mark.unit
    def test_generated_by_contains_mechdsl_lawgen(self) -> None:
        """Verifies: generated_by names the generator.
        AC: generated_by contains 'mechdsl-lawgen'.
        Passes when: manifest['generated_by'] contains 'mechdsl-lawgen'."""
        assert "mechdsl-lawgen" in str(_swift_voce_entry()["generated_by"])

    @pytest.mark.unit
    def test_manifest_is_valid_json(self, tmp_path: Path) -> None:
        """Verifies: the emitted _manifest.json is valid, loadable JSON.
        AC1: manifest is valid JSON.
        Passes when: json.loads of the written manifest succeeds and carries the law."""
        out = write_manifest([_swift_voce_entry()], tmp_path / "_manifest.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["laws"][0]["source_hash"] == _CYCLE0_R_SOURCE_HASH
