"""Scaffold stubs for Task P1-3: Reuse audit (REUSE.md) documenting MechDSL module composition.

Plan: dev/plans/mfront_cycleM0.md (lines 63-65) — MFront-mimic Cycle M0, Phase 1.
Deliverable under test (built in P1-3 exec):
  packages/mechdsl-core/src/mechdsl/lawgen/REUSE.md

P1-3 is a doc-only task; these stubs assert the reuse-map artifact exists and covers
the four modules the ticonstit target composes. AutViam scaffold stubs — each
`pytest.skip`s until P1-3 writes REUSE.md; ExecPhase replaces the bodies with real
file assertions. One stub per test_plan case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import mechdsl.lawgen

# REUSE.md lives inside the importable ``mechdsl.lawgen`` package, so resolve it
# relative to the package directory (robust to cwd, mirroring the sibling
# plan_tests' package-import style rather than a hand-built source-tree path).
_REUSE_MD = Path(mechdsl.lawgen.__file__).resolve().parent / "REUSE.md"


class TestTaskP1_3:
    """Tests for Task P1-3: REUSE.md reuse-map artifact. AC covered: 1,2,3."""

    @pytest.mark.unit
    def test_reuse_md_exists_and_nonempty(self) -> None:
        """Verifies: lawgen/REUSE.md exists and is non-empty.
        AC1/AC2: reuse-map committed into MechDSL.
        Passes when: packages/mechdsl-core/src/mechdsl/lawgen/REUSE.md is present and > 0 bytes."""
        assert _REUSE_MD.is_file(), f"REUSE.md not found at {_REUSE_MD}"
        assert _REUSE_MD.stat().st_size > 0, f"REUSE.md is empty at {_REUSE_MD}"

    @pytest.mark.unit
    def test_reuse_md_mentions_all_four_modules(self) -> None:
        """Verifies: REUSE.md names taichi_printer, artifact, lowering/, and the scaffold emitters.
        AC1: every lawgen concern maps to an existing module (or is flagged as a P2 gap).
        Passes when: all four module references appear in REUSE.md."""
        text = _REUSE_MD.read_text(encoding="utf-8")
        # The scaffold reference may appear as either token; accept either.
        scaffold_ok = "sympy_to_taichi" in text or "mechdsl_lawgen" in text
        assert "taichi_printer" in text, "REUSE.md must mention taichi_printer"
        assert "artifact" in text, "REUSE.md must mention artifact"
        assert "lowering" in text, "REUSE.md must mention lowering"
        assert scaffold_ok, (
            "REUSE.md must reference the scaffold (sympy_to_taichi or mechdsl_lawgen)"
        )
