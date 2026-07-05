"""Unit tests for the manifest emitter (Task P3-3).

Covers the four ``test_plan.cases`` from ``dev/plans/mfront_cycleM0/json/P3-3.json``:

1. the manifest entry for a SwiftVoce spec has all the Cycle 0 required fields;
2. ``source_hash`` matches the compile's source hash — reconciled to Cycle 0's
   convention (the INPUT-formula hash, *not* P2-4's emitted-lines hash);
3. ``generated_by`` contains ``"mechdsl-lawgen"``;
4. the written ``_manifest.json`` is valid, loadable JSON.

Plus the domain-quality bonuses that make the manifest safe for P4-2 to
byte-compare against Cycle 0's real ``_manifest.json``:

* the canonical SwiftVoce ``R`` formula reproduces Cycle 0's published
  ``source_hash`` (``7b5af3a8…``) exactly under the verbatim-UTF-8 convention;
* ``write_manifest`` is byte-stable (same entries → identical bytes twice);
* the entry key set is exactly the nine Cycle 0 ``laws`` fields;
* the ``parameters`` object partitions into ``{"required", "optional"}`` and
  ``emit_manifest`` fails loud on empty/invalid inputs (no half-populated entry).

Cross-repo discipline (R3): nothing here imports NumerixWeave or ``ticonstit``.
The reconciliation is proven by reproducing Cycle 0's *published hash value*
locally — the real file is only ever read as bytes by P4-2, never imported.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import sympy as sp

from mechdsl.lawgen.contracts import PlasticityCarrierSpec
from mechdsl.lawgen.manifest import (
    GENERATED_BY,
    LAWS_ENTRY_FIELDS,
    compute_input_formula_hash,
    emit_manifest,
    formula_matches_spec,
    write_manifest,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Cycle 0 reconciliation constants.
#
# The canonical SwiftVoce ``R`` formula string and the published ``source_hash``
# it must reproduce. These pin the manifest ``source_hash`` convention to Cycle
# 0's: hash the INPUT formula string verbatim (UTF-8, no normalisation). P4-1
# supplies this exact string from the law yaml; the value below is transcribed
# from Cycle 0's ``_manifest.json`` (read as data, not imported — R3).
# ---------------------------------------------------------------------------

CYCLE0_R_FORMULA = "R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)"
CYCLE0_R_SOURCE_HASH = "7b5af3a8bb79c2e44e0055a7076dd2c9de2ce8c75eb2e262b80bb4e0232d557f"

# The REAL Cycle 0 SwiftVoce ``parameters`` block (transcribed verbatim from
# NumerixWeave's ``_manifest.json`` — read as data, never imported: R3). Note the
# material-card names differ from the formula-string spelling: the card names the
# saturation parameter ``Q_inf`` while the hashed R formula spells it ``Q``. The
# realistic fixture below uses these exact names so the emitted ``parameters``
# object is byte-identical to the hand-authored artifact P4-2 compares against.
CYCLE0_REQUIRED = ["sigma0", "Q_inf", "b"]
CYCLE0_OPTIONAL = ["K", "n", "p0", "edot0", "m", "alpha", "T_ref"]


def _swift_voce_spec() -> PlasticityCarrierSpec:
    """A SwiftVoce carrier whose ``R`` matches Cycle 0's *formula string* spelling.

    ``R = sigma0 + Q*(1 - exp(-b*p)) + K*((p + p0)**n - p0**n)`` — the spec's
    symbols match the hashed formula (``Q``, not ``Q_inf``), so this fixture drives
    the ``source_hash`` reconciliation and the opt-in ``check_matches_spec`` path
    (where the formula and the spec must be symbolically equal). For the realistic
    material-card ``parameters`` block (``Q_inf`` + 10 names) see
    :func:`_cycle0_realistic_entry`.
    """
    p, edot, T = sp.symbols("p edot T")
    sigma0, Q, b, K, p0, n = sp.symbols("sigma0 Q b K p0 n")
    R = sigma0 + Q * (1 - sp.exp(-b * p)) + K * ((p + p0) ** n - p0**n)
    return PlasticityCarrierSpec(
        name="swift_voce",
        parameters=("sigma0", "Q", "b", "K", "p0", "n"),
        expressions={"R": R, "H": sp.Integer(1), "Q": sp.Integer(1)},
        variable_bindings={"p": p, "edot": edot, "T": T},
    )


def _cycle0_realistic_spec() -> PlasticityCarrierSpec:
    """A SwiftVoce carrier carrying the REAL Cycle 0 material card (10 parameters).

    ``spec.parameters`` is the full ``required ∪ optional`` name set in declaration
    order, so an explicit split reproduces Cycle 0's ``parameters`` block exactly.
    The R expression is a placeholder that references the card names (the manifest
    fingerprints the separately-supplied ``input_formula``, not ``spec.R``, so R's
    exact shape does not affect ``source_hash``).
    """
    p, edot, T = sp.symbols("p edot T")
    syms = sp.symbols(" ".join(CYCLE0_REQUIRED + CYCLE0_OPTIONAL))
    sigma0, Q_inf, b = syms[0], syms[1], syms[2]
    R = sigma0 + Q_inf * (1 - sp.exp(-b * p))
    return PlasticityCarrierSpec(
        name="SwiftVoce",
        parameters=tuple(CYCLE0_REQUIRED + CYCLE0_OPTIONAL),
        expressions={"R": R, "H": sp.Integer(1), "Q": sp.Integer(1)},
        variable_bindings={"p": p, "edot": edot, "T": T},
    )


def _cycle0_realistic_entry() -> dict[str, object]:
    """``emit_manifest`` for the realistic card with Cycle 0's explicit split."""
    return emit_manifest(
        _cycle0_realistic_spec(),
        input_formula=CYCLE0_R_FORMULA,
        target_contract="VoceHardeningModel",
        exports="SwiftVoce",
        source="swift_voce.py",
        tests=["libs/ticonstit/tests/plan_tests/mfront_cycle0/test_P2-2.py"],
        required=CYCLE0_REQUIRED,
        optional=CYCLE0_OPTIONAL,
    )


def _swift_voce_entry(**overrides: object) -> dict[str, object]:
    """``emit_manifest`` for the SwiftVoce spec with sensible P4-1-shaped args."""
    kwargs: dict[str, object] = {
        "input_formula": CYCLE0_R_FORMULA,
        "target_contract": "SwiftVoce",
        "exports": "SwiftVoce",
        "source": "swift_voce.py",
        "tests": ["tests/generated/test_swift_voce.py"],
    }
    kwargs.update(overrides)
    return emit_manifest(_swift_voce_spec(), **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Case 1 — all Cycle 0 required fields present.
# ---------------------------------------------------------------------------


class TestManifestFields:
    def test_entry_has_all_cycle0_required_fields(self) -> None:
        """AC2: the six named fields (and the full nine-field Cycle 0 shape)."""
        entry = _swift_voce_entry()
        required_six = {
            "source_hash",
            "generated_by",
            "target_contract",
            "exports",
            "parameters",
            "tests",
        }
        assert required_six <= set(entry)
        # The full Cycle 0 laws entry is exactly nine fields, no more, no less.
        assert set(entry) == set(LAWS_ENTRY_FIELDS)

    def test_entry_key_order_is_cycle0_order(self) -> None:
        """The entry lists fields in Cycle 0's declared order (byte-stability aid)."""
        entry = _swift_voce_entry()
        assert tuple(entry) == LAWS_ENTRY_FIELDS

    def test_parameters_is_required_optional_object(self) -> None:
        """AC4: ``parameters`` is the ``{"required", "optional"}`` object, not a flat list."""
        params = _swift_voce_entry()["parameters"]
        assert isinstance(params, dict)
        assert set(params) == {"required", "optional"}
        # Convention path: no explicit split → all spec parameters are required.
        assert params["required"] == list(_swift_voce_spec().parameters)
        assert params["optional"] == []

    def test_explicit_required_optional_partition(self) -> None:
        """An explicit required/optional split (the P4-1 path) is preserved verbatim."""
        params = _swift_voce_entry(
            required=["sigma0", "Q", "b", "K", "n"],
            optional=["p0"],
        )["parameters"]
        assert params == {"required": ["sigma0", "Q", "b", "K", "n"], "optional": ["p0"]}


# ---------------------------------------------------------------------------
# Case 2 — source_hash matches the compile source hash (Cycle 0 reconciliation).
# ---------------------------------------------------------------------------


class TestSourceHash:
    def test_source_hash_matches_input_formula_hash(self) -> None:
        """AC3 (reconciled): ``source_hash`` == hash of the INPUT formula string."""
        entry = _swift_voce_entry()
        assert entry["source_hash"] == compute_input_formula_hash(CYCLE0_R_FORMULA)

    def test_source_hash_reproduces_cycle0_published_value(self) -> None:
        """The canonical SwiftVoce R formula reproduces Cycle 0's ``7b5af3a8…``.

        This is the P4-2 reconciliation guarantee: MechDSL's emitted manifest
        source_hash equals the value already published in Cycle 0's
        ``_manifest.json`` — so provenance verification passes.
        """
        assert _swift_voce_entry()["source_hash"] == CYCLE0_R_SOURCE_HASH

    def test_input_formula_hash_is_verbatim_utf8(self) -> None:
        """The convention is verbatim UTF-8 — whitespace/reordering changes the hash."""
        base = compute_input_formula_hash(CYCLE0_R_FORMULA)
        # Collapsing a space is a different input → a different hash (no normalisation).
        assert compute_input_formula_hash(CYCLE0_R_FORMULA.replace(" + ", "+")) != base

    def test_empty_formula_rejected(self) -> None:
        for bad in ("", "   ", None):
            with pytest.raises(ValueError, match="non-empty formula string"):
                compute_input_formula_hash(bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Case 3 — generated_by names the generator.
# ---------------------------------------------------------------------------


class TestGeneratedBy:
    def test_generated_by_contains_mechdsl_lawgen(self) -> None:
        entry = _swift_voce_entry()
        assert "mechdsl-lawgen" in str(entry["generated_by"])

    def test_generated_by_carries_a_version(self) -> None:
        """``mechdsl-lawgen/<version>`` — the '/' + a version tail is present."""
        assert GENERATED_BY.startswith("mechdsl-lawgen/")
        assert GENERATED_BY.split("/", 1)[1] != ""


# ---------------------------------------------------------------------------
# Case 4 — the written _manifest.json is valid, loadable JSON.
# ---------------------------------------------------------------------------


class TestWriteManifest:
    def test_written_manifest_is_valid_json(self, tmp_path: Path) -> None:
        """AC1: ``json.load`` of the emitted file succeeds and round-trips the entry."""
        out = write_manifest([_swift_voce_entry()], tmp_path / "_manifest.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert "laws" in loaded
        assert loaded["laws"][0]["source_hash"] == CYCLE0_R_SOURCE_HASH
        assert loaded["laws"][0]["generated_by"] == GENERATED_BY

    def test_written_manifest_has_schema_and_laws_top_level(self, tmp_path: Path) -> None:
        """Top-level shape mirrors Cycle 0: ``{"_schema": ..., "laws": [...]}``."""
        out = write_manifest([_swift_voce_entry()], tmp_path / "_manifest.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert set(loaded) == {"_schema", "laws"}
        assert isinstance(loaded["laws"], list)

    def test_write_is_byte_stable(self, tmp_path: Path) -> None:
        """Same entries → byte-identical file across re-runs (deterministic output)."""
        first = write_manifest([_swift_voce_entry()], tmp_path / "a.json").read_bytes()
        second = write_manifest([_swift_voce_entry()], tmp_path / "b.json").read_bytes()
        assert first == second
        assert first.endswith(b"\n")

    def test_written_entry_key_order_matches_cycle0(self, tmp_path: Path) -> None:
        """The serialised laws entry keeps Cycle 0's insertion order (no sort_keys).

        Cycle 0's real _manifest.json lists the entry keys as name, kind, source, …
        (insertion order, NOT alphabetical) and parameters as {required, optional}.
        json.loads preserves file key order (py3.7+), so this pins the on-disk order.
        """
        out = write_manifest([_swift_voce_entry()], tmp_path / "_manifest.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert tuple(loaded["laws"][0]) == LAWS_ENTRY_FIELDS
        assert tuple(loaded["laws"][0]["parameters"]) == ("required", "optional")


# ---------------------------------------------------------------------------
# Fail-loud — a half-populated entry is never emitted.
# ---------------------------------------------------------------------------


class TestFailLoud:
    @pytest.mark.parametrize("field", ["target_contract", "exports", "source"])
    def test_empty_string_field_rejected(self, field: str) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            _swift_voce_entry(**{field: "  "})

    def test_no_tests_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one test"):
            _swift_voce_entry(tests=[])

    def test_required_optional_overlap_rejected(self) -> None:
        with pytest.raises(ValueError, match="overlap"):
            _swift_voce_entry(required=["sigma0"], optional=["sigma0"])

    def test_unknown_parameter_rejected(self) -> None:
        with pytest.raises(ValueError, match="not declared"):
            _swift_voce_entry(required=["not_a_param"])

    def test_incomplete_partition_rejected(self) -> None:
        """An explicit split that omits a declared parameter fails loud (no silent drop)."""
        # Only sigma0 classified; Q, b, K, p0, n covered by neither list.
        with pytest.raises(ValueError, match="neither required nor optional"):
            _swift_voce_entry(required=["sigma0"], optional=[])


# ---------------------------------------------------------------------------
# Cycle 0 parameters parity — the realistic material card reproduces the real
# {required, optional} block byte-for-byte (not just the 6-name mechanism spec).
# ---------------------------------------------------------------------------


class TestCycle0ParametersParity:
    def test_parameters_block_matches_real_cycle0(self) -> None:
        """The emitted ``parameters`` object equals Cycle 0's real required/optional lists."""
        entry = _cycle0_realistic_entry()
        assert entry["parameters"] == {"required": CYCLE0_REQUIRED, "optional": CYCLE0_OPTIONAL}

    def test_realistic_entry_still_reproduces_source_hash(self) -> None:
        """Realistic card + the verbatim formula still fingerprints Cycle 0's hash."""
        assert _cycle0_realistic_entry()["source_hash"] == CYCLE0_R_SOURCE_HASH

    def test_realistic_entry_written_key_order(self, tmp_path: Path) -> None:
        """Realistic entry serialises with Cycle 0's insertion order end-to-end."""
        out = write_manifest([_cycle0_realistic_entry()], tmp_path / "_manifest.json")
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert tuple(loaded["laws"][0]) == LAWS_ENTRY_FIELDS
        assert loaded["laws"][0]["parameters"]["required"] == CYCLE0_REQUIRED


# ---------------------------------------------------------------------------
# formula ↔ spec consistency — the opt-in guard that closes the "hashed formula
# is a different law than the spec" gap for P4-1.
# ---------------------------------------------------------------------------


class TestFormulaMatchesSpec:
    def test_matching_formula_is_true(self) -> None:
        """The Cycle 0 formula (Q-spelled) is symbolically equal to the Q-spelled spec.R."""
        assert formula_matches_spec(CYCLE0_R_FORMULA, _swift_voce_spec()) is True

    def test_formula_without_lhs_prefix_also_matches(self) -> None:
        """The 'R =' prefix is optional — a bare RHS matches too."""
        rhs = CYCLE0_R_FORMULA.split("=", 1)[1].strip()
        assert formula_matches_spec(rhs, _swift_voce_spec()) is True

    def test_mismatched_formula_is_false(self) -> None:
        """A formula that is not spec.R is reported as a mismatch (no false positive)."""
        assert formula_matches_spec("R = sigma0 + b*p", _swift_voce_spec()) is False

    def test_unparseable_formula_raises(self) -> None:
        with pytest.raises(ValueError, match="could not parse"):
            formula_matches_spec("R = sigma0 +* b", _swift_voce_spec())

    def test_emit_manifest_check_matches_spec_passes_when_consistent(self) -> None:
        """check_matches_spec=True is a no-op when the formula equals spec.R."""
        entry = _swift_voce_entry(check_matches_spec=True)
        assert entry["source_hash"] == CYCLE0_R_SOURCE_HASH

    def test_emit_manifest_check_matches_spec_raises_on_drift(self) -> None:
        """A drifted formula fingerprints the wrong law → fails loud under the check."""
        with pytest.raises(ValueError, match="not symbolically equal"):
            _swift_voce_entry(input_formula="R = sigma0 + b*p", check_matches_spec=True)

    def test_check_defaults_off_for_cycle0_naming_divergence(self) -> None:
        """Default (off) tolerates the Cycle 0 Q vs Q_inf spelling divergence."""
        # The realistic card spells the parameter Q_inf while the formula spells Q,
        # so the formula is NOT spec.R — but the default path still emits (hash intact).
        assert formula_matches_spec(CYCLE0_R_FORMULA, _cycle0_realistic_spec()) is False
        assert _cycle0_realistic_entry()["source_hash"] == CYCLE0_R_SOURCE_HASH


# ---------------------------------------------------------------------------
# _schema shape — laws_entry_fields is an object (name → description), matching
# Cycle 0's real _schema, not a flat list of names.
# ---------------------------------------------------------------------------


class TestSchemaShape:
    def test_laws_entry_fields_is_name_to_description_object(self, tmp_path: Path) -> None:
        out = write_manifest([_swift_voce_entry()], tmp_path / "_manifest.json")
        schema = json.loads(out.read_text(encoding="utf-8"))["_schema"]
        fields = schema["laws_entry_fields"]
        assert isinstance(fields, dict)
        assert tuple(fields) == LAWS_ENTRY_FIELDS
        assert all(isinstance(v, str) and v.strip() for v in fields.values())
