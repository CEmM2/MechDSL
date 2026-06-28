"""Tests for Task P7-1 (PlanJune14 Phase 7) — design-doc addenda governance.

**GOVERNANCE phase** (plan lines 138–143, "governance — no re-drift"). Write the
design-doc addenda that record the architecture change: extend Decision D8 in
``dev/design_docs/06-CODEGEN.md`` (solver now generated, not imported), mark
§8.3 in ``dev/design_docs/11-ALGO2CODE.md`` as the operator seam built, and apply
the deferred §2.4 edit (W5, previously hook-blocked in PlanJune14).

This is distinct from the **prior-phase implementation** (P2-2, P4-3) that
built the seams and the generated solver/operator. P7-1's job is to update
the *design documentation* so the codebase doesn't re-drift to stale claims
like "solver imported" or "operator seam not yet built". The addenda are
**externally observable**: tests anchor them to prevent future doc rot.

Acceptance criteria covered:
  AC-1  The extended D8 addendum is present in 06-CODEGEN, consistent with the
        opt-in flipped default (P4-3: generated is OPT-IN, imported is fallback).
  AC-2  The §8.3 operator seam in 11-ALGO2CODE is marked as built and documents
        the `% type A callable` directive; the deferred §2.4 edit is applied.


NOTE: no `from __future__ import annotations` — these tests read and parse design
docs (immutable files), so PEP 563 is not a concern.
"""

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Walk up to the workspace root (the dir holding ``pyproject.toml`` + ``dev/``)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("could not locate repo root (pyproject.toml + dev/)")


_DESIGN_DOCS = _repo_root() / "dev" / "design_docs"


def _normalize(text: str) -> str:
    """Lower-case, strip Markdown blockquote markers, and collapse whitespace.

    Addenda are prose that wraps across lines and (for D8) lives inside a ``>``
    blockquote, so anchor phrases are matched against a normalized stream rather
    than the raw file — robust to re-wrapping during a manual paste.
    """
    no_quote = re.sub(r"(?m)^\s*>\s?", "", text)
    return re.sub(r"\s+", " ", no_quote).lower()


class TestTaskP71:
    """Tests for Task P7-1: design-doc addenda governance. AC covered: 1, 2."""

    # xfail until the maintainer pastes the staged addenda (see module docstring).
    # strict=True ⇒ an xpass (docs applied) hard-fails, forcing marker removal.
    _PENDING = "P7-1 addenda not yet pasted into dev/design_docs/ (manual maintainer step)"

    @pytest.mark.docs
    def test_d8_addendum_solver_generated_imported_fallback(self):
        """AC-1: Decision D8 addendum in 06-CODEGEN reflects the architecture:
        solver is now GENERATED (the primary path via P2-2 and P4-3); the
        imported linear solver is a fallback only. The addendum must be present
        and consistent with the opt-in flipped default (P4-3 makes generated
        opt-in; imported is NOT the global default).
        """
        text = _normalize((_DESIGN_DOCS / "06-CODEGEN.md").read_text(encoding="utf-8"))

        anchors = {
            "Decision D8 addendum heading": "decision d8 addendum",
            "'solver is now generated' claim": "the solver is now generated",
            "imported solver kept as fallback": "default fallback",
            "imported ScipyCGSolver named as the fallback": "scipycgsolver",
            "generated path is opt-in (PJ-4 Option 1)": "opt-in",
        }
        missing = [label for label, needle in anchors.items() if needle not in text]
        assert not missing, (
            "06-CODEGEN.md is missing the D8 addendum anchors: "
            + ", ".join(missing)
            + ". Apply Edit 1 from dev/tasks/PlanJune14/P7-1_pending_design_doc_addenda.md."
        )

    @pytest.mark.docs
    def test_algo2code_section_8_3_operator_seam_built_and_2_4_edit(self):
        """AC-2: Section §8.3 in 11-ALGO2CODE documents the built operator seam
        and the `% type A callable` directive, and the deferred §2.4 edit (W5)
        is applied. The seam is no longer a "to-be-built" claim but a completed
        design anchor.
        """
        text = _normalize((_DESIGN_DOCS / "11-ALGO2CODE.md").read_text(encoding="utf-8"))

        # §8.3 — operator seam marked built (Edit 3).
        seam_anchors = {
            "§8.3 operator-interface heading": "matrix-free operator interface",
            "marked built": "built",
            "`% type A callable` directive documented": "% type a callable",
            "injected via set_operator seam": "set_operator".lower(),
            "PlanJune14 seam-coverage note (proves built, not planned)": "seam coverage",
        }
        # §2.4 — deferred W5 edit (Edit 4): fail-loud + spectral intrinsics note.
        w5_anchors = {
            "unsupported constructs now raise UnsupportedConstructError": "unsupportedconstructerror",
            "spectral / matrix-free intrinsics note": "spectral",
            "Gamma0 Green-operator callable named": "gamma0",
        }
        missing = [label for label, needle in seam_anchors.items() if needle not in text]
        missing += [label for label, needle in w5_anchors.items() if needle not in text]
        assert not missing, (
            "11-ALGO2CODE.md is missing the §8.3/§2.4 addenda anchors: "
            + ", ".join(missing)
            + ". Apply Edits 3 and 4 from "
            "dev/tasks/PlanJune14/P7-1_pending_design_doc_addenda.md."
        )
