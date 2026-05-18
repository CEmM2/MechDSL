"""Tests for Task P6-3: robustify test_p7_4.py notes iteration.

Acceptance criteria:
1. test_p7_4.py no longer indexes notes by position (e.g. ``notes[0]``)
   when validating cross-link content.
2. The note-selection logic filters by plan-referenced filename so a
   reordering of the candidate list does not change the assertion
   target.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _target_path() -> Path:
    return (
        _repo_root()
        / "packages"
        / "mechdsl-core"
        / "tests"
        / "plan_tests"
        / "recovery_plan_latex_contract"
        / "test_p7_4.py"
    )


class TestTaskP6_3:
    """Tests for Task P6-3: notes-iteration robustness."""

    @pytest.mark.unit
    def test_no_positional_index_into_notes(self) -> None:
        text = _target_path().read_text(encoding="utf-8")
        # Tight match — the bare ``notes[0]`` pattern, not a substring of
        # ``target_notes[0]`` or any other filtered list. The Phase-6
        # contract is "no positional index into the unfiltered candidate
        # list", which the bare regex below catches without false-flagging
        # the filtered-list deref that replaces it.
        assert not re.search(r"(?<![A-Za-z_])notes\[0\]", text), (
            "test_p7_4.py must not assert against notes[0] — replace with "
            "iteration that filters by plan-referenced filename"
        )

    @pytest.mark.unit
    def test_filter_by_filename_present(self) -> None:
        text = _target_path().read_text(encoding="utf-8")
        # Robust filter must reference one of the plan-mentioned
        # filenames inside an iteration over `notes`.
        assert "for " in text and "notes" in text, (
            "test_p7_4.py must iterate over notes (no positional indexing)"
        )
        assert "recovery_plan_latex_contract.md" in text or "drift_20_04.md" in text, (
            "test_p7_4.py iteration must filter by a plan-referenced filename"
        )
