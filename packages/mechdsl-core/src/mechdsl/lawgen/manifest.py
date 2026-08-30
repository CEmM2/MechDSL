"""Manifest emitter — writes ``_manifest.json`` matching Cycle 0's schema (Task P3-3).

Part of the MechDSL lawgen pipeline (YAML law spec → restricted SymPy →
Taichi carrier).

:func:`emit_manifest` produces one *laws entry* — and, via :func:`write_manifest`,
merges it into the ``{"_schema": {...}, "laws": [...]}`` file that
NumerixWeave's auto-register loop reads and that Task P4-2 relies on for
provenance (P4-2's own gate is run-to-run ``source_hash`` determinism, not a
whole-file byte-diff against Cycle 0). The authoritative schema is the real
Cycle 0 ``libs/ticonstit/src/ticonstit/generated/_manifest.json`` in the
NumerixWeave repo. Its ``laws[0]`` entry has **nine** fields, emitted in
**insertion order** (the real file is insertion-ordered, not alphabetical) — this
module reproduces those exact field names, order, and shapes:

``name``, ``kind``, ``source``, ``source_hash``, ``generated_by``,
``target_contract``, ``exports``, ``parameters`` (an object
``{"required": [...], "optional": [...]}``), and ``tests``.

Cross-repo discipline (R3)
--------------------------
Nothing here imports NumerixWeave or ``ticonstit``. The MechDSL↔NumerixWeave
seam is committed artifacts only: the manifest we *emit* is compared against the
real file by reading that file's **bytes** (in the tests), never by importing it.

``source_hash`` convention — hash the INPUT formula string (P4-2 reconciliation)
--------------------------------------------------------------------------------
# NOTE (P4-2): Cycle 0's ``_manifest.json`` defines ``source_hash`` as the
# SHA-256 of the **generator INPUT** — the canonical R formula string
# (``"R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)"`` → ``7b5af3a8…``),
# NOT the emitted-output-lines hash that P2-4's
# :func:`~mechdsl.lawgen.sympy_to_taichi.compute_source_hash` /
# :attr:`~mechdsl.lawgen.sympy_to_taichi.LoweredExpr.source_hash` produces.
# This module therefore hashes the input formula string via
# :func:`compute_input_formula_hash` and deliberately does **not** consume the
# P2-4 emitted-lines hash for the manifest. P2-4's hash remains valid provenance
# of the *output*; the manifest fingerprints the *input* so NumerixWeave can
# verify the law was generated from the formula it claims. P4-1 supplies the
# exact canonical formula string (from the law yaml's ``R`` formula) — the
# canonical-string convention this module locks is: the formula string is hashed
# **verbatim, UTF-8, no normalisation** (no whitespace collapsing, no operator
# reordering). Cycle 0's value is reproduced exactly under this convention (see
# ``test_manifest.py`` / ``test_P3-3.py``), so P4-1 must pass the formula string
# with the same spelling the yaml carries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from mechdsl import __version__ as _MECHDSL_VERSION

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from mechdsl.lawgen.contracts import PlasticityCarrierSpec

__all__ = [
    "GENERATED_BY",
    "LAWS_ENTRY_FIELDS",
    "compute_input_formula_hash",
    "emit_manifest",
    "formula_matches_spec",
    "write_manifest",
]

# The nine fields of a Cycle 0 ``laws`` entry, in the order the real
# ``_manifest.json`` lists them. Used to validate/emit a byte-stable entry and
# as the schema-fidelity key set the byte-compare tests check against.
LAWS_ENTRY_FIELDS: tuple[str, ...] = (
    "name",
    "kind",
    "source",
    "source_hash",
    "generated_by",
    "target_contract",
    "exports",
    "parameters",
    "tests",
)

#: ``generated_by`` value. Legacy hand-authored carriers used a placeholder
#: generator tag; the MechDSL lawgen emitter now stamps
#: ``"mechdsl-lawgen/<version>"`` with the mechdsl-core package version, so the
#: manifest records *which* generator + version produced the law.
GENERATED_BY: str = f"mechdsl-lawgen/{_MECHDSL_VERSION}"

#: Cycle 0 only emits the ``"plasticity"`` registry bucket.
_DEFAULT_KIND: str = "plasticity"


def compute_input_formula_hash(formula: str) -> str:
    """Return the SHA-256 of the canonical generator-input formula string.

    This is the manifest ``source_hash`` convention (see the module note): the
    formula string is hashed **verbatim** — UTF-8 encoded, with no whitespace
    normalisation and no operator reordering. Under this convention Cycle 0's
    ``R = sigma0 + Q*(1-exp(-b*p)) + K*((p+p0)**n - p0**n)`` reproduces the
    published hash ``7b5af3a8…`` exactly.

    Parameters
    ----------
    formula:
        The canonical input formula string (P4-1 supplies it from the law yaml's
        ``R`` formula). Must be a non-empty string.

    Returns
    -------
    str
        64 lowercase hex characters.
    """
    if not isinstance(formula, str) or not formula.strip():
        raise ValueError(
            "compute_input_formula_hash requires a non-empty formula string "
            f"(the canonical generator input), got {formula!r}."
        )
    return hashlib.sha256(formula.encode("utf-8")).hexdigest()


def formula_matches_spec(input_formula: str, spec: PlasticityCarrierSpec) -> bool:
    """Return ``True`` iff ``input_formula``'s RHS is symbolically equal to ``spec.R``.

    The manifest ``source_hash`` fingerprints the *verbatim* ``input_formula``
    string (so it can reproduce Cycle 0's published hash), while the entry ``name``
    / ``parameters`` come from the ``spec``. Those two inputs are independent, so
    nothing structurally guarantees the hashed formula is the same law the spec
    describes — a stale or mistyped ``input_formula`` would fingerprint the *wrong*
    law without complaint. This helper closes that gap for P4-1: parse the formula
    (stripping an optional ``R =`` / ``R:=`` left-hand side), sympify the RHS, and
    check it is symbolically equal to ``spec.R``.

    Naming caveat (Cycle 0 transition): Cycle 0's published formula string spells
    the saturation term ``Q`` while its material card names the parameter
    ``Q_inf`` — so for the *transitional* SwiftVoce law the formula variable names
    deliberately differ from ``spec.parameters`` and this check will return
    ``False``. That is exactly why :func:`emit_manifest`'s ``check_matches_spec``
    is **opt-in** (default off): turn it on once P4-1 authors a law whose formula
    spelling matches the spec's own symbols, so a drifted formula fails loud.

    Returns
    -------
    bool
        ``True`` when ``sympify(RHS) - spec.R`` simplifies to zero.

    Raises
    ------
    ValueError
        If ``input_formula`` (its RHS) cannot be parsed as a SymPy expression — an
        unparseable formula is itself a defect worth surfacing when a caller asks
        for the check.
    """
    import re  # identifier tokenising for the parse — not a codegen path

    import sympy as sp  # local import: only the opt-in consistency check needs SymPy

    rhs = input_formula.split(":=", 1)[-1] if ":=" in input_formula else input_formula
    rhs = rhs.split("=", 1)[-1] if "=" in rhs else rhs

    # Auto-symbolise every bare identifier in the formula so parsing is independent of
    # the spec's names and never resolves a variable to a SymPy global. Without this a
    # parameter spelled ``Q`` binds to ``sympy.Q`` (the assumptions object) and the
    # parse raises. Names immediately followed by ``(`` are function calls (``exp``,
    # ``log``, …) — left out of the symbol map so they resolve to the real SymPy
    # functions.
    all_names = set(re.findall(r"[A-Za-z_]\w*", rhs))
    func_names = set(re.findall(r"([A-Za-z_]\w*)\s*\(", rhs))
    local_dict = {name: sp.Symbol(name) for name in all_names - func_names}
    try:
        parsed = sp.sympify(rhs, locals=local_dict)
    except (sp.SympifyError, SyntaxError, TypeError, ValueError) as exc:
        raise ValueError(
            f"formula_matches_spec could not parse input_formula RHS {rhs!r} as a "
            f"SymPy expression: {exc}."
        ) from exc
    difference = sp.simplify(parsed - spec.R)
    return bool(difference == 0)


def _split_parameters(
    parameters: Sequence[str],
    *,
    required: Sequence[str] | None,
    optional: Sequence[str] | None,
) -> dict[str, list[str]]:
    """Resolve the ``{"required": [...], "optional": [...]}`` parameters object.

    Two modes, matching the Cycle 0 shape (``parameters`` is an *object*, not a
    flat list):

    * **Explicit** — when ``required`` and/or ``optional`` are given, they are
      used verbatim (order preserved). This is the path P4-1 takes: the law yaml
      states which parameters are required vs optional. Every name in
      ``required``/``optional`` must appear in the spec's ``parameters`` (no
      inventing parameters the law does not declare), the two lists must be
      disjoint, and together they must be a **complete partition** — every
      declared parameter is either required or optional. A parameter left out of
      both is rejected (not silently dropped), so a YAML typo that forgets to
      classify a load-bearing parameter fails loud instead of under-declaring the
      law's surface in the manifest.
    * **Convention** — when neither is given, the split defaults to *all* the
      spec's parameters being ``required`` and ``optional`` empty. Rationale: a
      carrier lists exactly the parameters its expressions reference, so absent
      an explicit yaml split every listed parameter is load-bearing (required).
      This keeps a spec-only call (tests, quick emission) valid while letting
      P4-1 override with the real required/optional partition.
    """
    all_params = list(parameters)
    if required is None and optional is None:
        return {"required": all_params, "optional": []}

    req = list(required or [])
    opt = list(optional or [])

    overlap = sorted(set(req) & set(opt))
    if overlap:
        raise ValueError(
            f"manifest parameters: required and optional overlap on {overlap}; "
            "a parameter is one or the other, not both."
        )
    known = set(all_params)
    unknown = [p for p in (*req, *opt) if p not in known]
    if unknown:
        raise ValueError(
            f"manifest parameters: {unknown} not declared in the spec's parameters "
            f"{all_params}; required/optional may only partition declared parameters."
        )
    covered = set(req) | set(opt)
    uncovered = [p for p in all_params if p not in covered]
    if uncovered:
        raise ValueError(
            f"manifest parameters: {uncovered} declared in the spec's parameters "
            f"{all_params} but classified as neither required nor optional; an explicit "
            "split must be a complete partition so a load-bearing parameter is never "
            "silently dropped from the manifest."
        )
    return {"required": req, "optional": opt}


def emit_manifest(
    spec: PlasticityCarrierSpec,
    *,
    input_formula: str,
    target_contract: str,
    exports: str,
    source: str,
    tests: Sequence[str],
    kind: str = _DEFAULT_KIND,
    required: Sequence[str] | None = None,
    optional: Sequence[str] | None = None,
    check_matches_spec: bool = False,
) -> dict[str, object]:
    """Build one Cycle 0-shaped ``laws`` entry (the nine-field object).

    Parameters
    ----------
    spec:
        The carrier law. ``spec.name`` becomes the entry ``name``; ``spec.parameters``
        is partitioned into the ``parameters`` object (see :func:`_split_parameters`).
    input_formula:
        The canonical generator-input formula string. Its SHA-256 (verbatim, UTF-8)
        is the entry ``source_hash`` — the INPUT-formula hash Cycle 0 uses, NOT the
        P2-4 emitted-lines hash (see the module note). ``input_formula`` and ``spec``
        are independent inputs; pass ``check_matches_spec=True`` to assert the
        hashed formula actually is ``spec.R``.
    check_matches_spec:
        When ``True``, verify via :func:`formula_matches_spec` that ``input_formula``
        is symbolically equal to ``spec.R`` and raise :class:`ValueError` if not — so
        a stale/mistyped formula fingerprints the wrong law loudly instead of
        silently. Default ``False`` because, during the Cycle 0 transition, the
        published formula string deliberately spells parameters differently from the
        spec's material card (``Q`` vs ``Q_inf``); P4-1 turns it on once a law's
        formula spelling matches its own symbols (see :func:`formula_matches_spec`).
    target_contract:
        The **runtime** contract the law implements (e.g. ``"VoceHardeningModel"``).
        Supplied explicitly by P4-1 from the law yaml — this is deliberately NOT
        ``TiconstitTarget.contract_id`` (the emission-contract id), which is a
        different thing.
    exports:
        The Python class name the generated submodule exports (e.g. ``"SwiftVoce"``).
    source:
        The generated module filename within ``ticonstit.generated.plasticity``
        (e.g. ``"swift_voce.py"``); its stem is the imported submodule.
    tests:
        Test file paths that pin the generated law (golden / FD-derivative /
        guard-audit) — the paths P3-2's ``emit_tests`` writes.
    kind:
        Registry bucket. Defaults to ``"plasticity"`` (the only Cycle 0 bucket).
    required, optional:
        Optional explicit required/optional parameter partition. When omitted, all
        of ``spec.parameters`` is treated as required (see :func:`_split_parameters`).

    Returns
    -------
    dict[str, object]
        A dict with exactly the nine :data:`LAWS_ENTRY_FIELDS`, ready to be placed
        in a ``{"laws": [...]}`` manifest. Fails loud (``ValueError``) on any
        missing/empty required input so a half-populated entry is never emitted.
    """
    _require_nonempty_str("target_contract", target_contract)
    _require_nonempty_str("exports", exports)
    _require_nonempty_str("source", source)
    _require_nonempty_str("kind", kind)
    tests_list = list(tests)
    if not tests_list:
        raise ValueError(
            "emit_manifest requires at least one test path (a generated law must be "
            "pinned by at least one test)."
        )
    for test_path in tests_list:
        _require_nonempty_str("tests entry", test_path)

    if check_matches_spec and not formula_matches_spec(input_formula, spec):
        raise ValueError(
            f"emit_manifest: input_formula {input_formula!r} is not symbolically equal "
            f"to spec.R ({spec.R}) for law {spec.name!r}; the manifest source_hash would "
            "fingerprint a different law than the spec describes. Fix the formula string "
            "or the spec, or drop check_matches_spec if the spelling divergence is "
            "intentional (see formula_matches_spec)."
        )

    source_hash = compute_input_formula_hash(input_formula)
    parameters = _split_parameters(spec.parameters, required=required, optional=optional)

    entry: dict[str, object] = {
        "name": spec.name,
        "kind": kind,
        "source": source,
        "source_hash": source_hash,
        "generated_by": GENERATED_BY,
        "target_contract": target_contract,
        "exports": exports,
        "parameters": parameters,
        "tests": tests_list,
    }
    # Invariant: the entry key set is exactly the Cycle 0 laws-entry field
    # set, guarding against future field drift.
    assert set(entry) == set(LAWS_ENTRY_FIELDS), (
        f"emit_manifest entry keys {sorted(entry)} drifted from the Cycle 0 "
        f"laws-entry schema {sorted(LAWS_ENTRY_FIELDS)}."
    )
    return entry


def write_manifest(
    entries: Sequence[Mapping[str, object]],
    out_path: str | Path,
    *,
    schema_doc: Mapping[str, object] | None = None,
) -> Path:
    """Write a byte-stable ``{"_schema": ..., "laws": [...]}`` manifest file.

    The file is serialised with ``indent=2``, a trailing newline, and keys in
    **insertion order** (no ``sort_keys``). Output is **byte-stable** across
    re-runs for a given set of entries — every entry is built via the fixed
    :data:`LAWS_ENTRY_FIELDS` literal — and that insertion order reproduces
    Cycle 0's real ``_manifest.json`` structure (``name, kind, source, …`` and
    ``{required, optional}``), which is insertion-ordered, *not* alphabetical.
    ``sort_keys=True`` would gratuitously reorder the keys away from Cycle 0, so
    a structural diff against the hand-authored artifact would differ only in the
    field *values* P4-1 supplies, never in key order.

    Parameters
    ----------
    entries:
        The ``laws`` entries (each a :func:`emit_manifest` result).
    out_path:
        Where to write ``_manifest.json``. Parent directories are created.
    schema_doc:
        Optional ``_schema`` documentation block. When omitted, a self-documenting
        ``_schema`` is written whose ``laws_entry_fields`` is an **object** (field
        name → description), matching Cycle 0's real ``_schema`` shape (not a flat
        list), so the emitted file mirrors Cycle 0's ``{"_schema": ..., "laws":
        [...]}`` structure. Pass a custom mapping for byte-exact Cycle 0 text.

    Returns
    -------
    pathlib.Path
        The path written.
    """
    manifest: dict[str, object] = {
        "_schema": dict(schema_doc) if schema_doc is not None else _default_schema_doc(),
        "laws": [dict(entry) for entry in entries],
    }
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # No sort_keys: keys serialise in insertion order, reproducing Cycle 0's
    # insertion-ordered laws entry (name, kind, source, …) and {required, optional}
    # exactly — Cycle 0's real _manifest.json is NOT alphabetical. Output stays
    # byte-stable across re-runs because emit_manifest builds every entry via the
    # fixed LAWS_ENTRY_FIELDS literal. ensure_ascii=False keeps any unicode
    # readable; the trailing newline is POSIX-clean and diff-friendly.
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


#: Per-field descriptions for the ``_schema.laws_entry_fields`` block, keyed by
#: the nine :data:`LAWS_ENTRY_FIELDS` in order. Cycle 0's real ``_manifest.json``
#: documents the schema as an **object** (field name → description), not a flat
#: list — reproducing that object shape keeps the emitted ``_schema`` structurally
#: identical to the hand-authored artifact. Descriptions are generator-neutral
#: (they describe the field, and note the MechDSL-lawgen conventions where they
#: differ from Cycle 0's hand-authored specifics).
_LAWS_ENTRY_FIELD_DESCRIPTIONS: dict[str, str] = {
    "name": (
        "Law name, unique within the plasticity bucket (e.g. 'SwiftVoce'), and the "
        "class exported by the submodule."
    ),
    "kind": "Registry bucket for this law. Cycle 0 only emits 'plasticity'.",
    "source": (
        "Generated module filename within ticonstit.generated.plasticity (e.g. "
        "'swift_voce.py'). Its stem is the submodule imported by the auto-register "
        "loop, decoupling the file name from the class name."
    ),
    "source_hash": (
        "SHA-256 fingerprint of the generator input (the verbatim R formula string), "
        "passed to register_plasticity(source_hash=...)."
    ),
    "generated_by": ("Tool + version that produced the file (e.g. 'mechdsl-lawgen/<version>')."),
    "target_contract": (
        "Runtime contract identifier the law implements (e.g. 'VoceHardeningModel'), "
        "passed to register_plasticity(contract=...)."
    ),
    "exports": "Name of the Python class exported by the submodule that implements the law.",
    "parameters": (
        "Object describing required/optional material-parameter names, passed to "
        "register_plasticity(required=..., optional=...)."
    ),
    "tests": (
        "List of test file paths that pin this generated law (golden / FD-derivative "
        "/ guard-audit)."
    ),
}


def _default_schema_doc() -> dict[str, object]:
    """A self-documenting ``_schema`` block describing the nine entry fields.

    Mirrors Cycle 0's real ``_manifest.json`` shape: a ``_comment`` string plus a
    ``laws_entry_fields`` **object** mapping each field name to a description (not a
    flat list of names), so the emitted ``_schema`` is structurally identical to the
    hand-authored artifact. Callers wanting byte-exact Cycle 0 text can still pass a
    custom ``schema_doc`` to :func:`write_manifest`.
    """
    return {
        "_comment": (
            "JSON has no comments; this key documents the per-law entry schema. It is "
            "ignored by the auto-register loop, which reads only the 'laws' list. Each "
            "entry in 'laws' is an object with the fields described below."
        ),
        "laws_entry_fields": dict(_LAWS_ENTRY_FIELD_DESCRIPTIONS),
    }


def _require_nonempty_str(label: str, value: object) -> None:
    """Raise ``ValueError`` unless ``value`` is a non-empty (non-blank) string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"emit_manifest: {label} must be a non-empty string, got {value!r}.")
