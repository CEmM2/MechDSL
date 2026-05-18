"""Tests for Task P7-5: clarify Plan-B `_SUPERSEDED.md` runtime-active
vs archived sub-deliverables.

Acceptance: ``_SUPERSEDED.md`` contains a sub-section listing
runtime-active vs archived Plan-B sub-deliverables.

Resolution path: the original P7-5 edit landed at
``dev/tasks/PLAN-B/_SUPERSEDED.md``; subsequent main-branch archival
(commit 69c13b9) moved the Plan-B task folder under
``dev/archived/completed/PLAN-B/tasks/``. We accept both locations so
the test survives the move and any future re-archival.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("repo root not found")


_CANDIDATES = (
    ("dev", "tasks", "PLAN-B", "_SUPERSEDED.md"),
    ("dev", "archived", "completed", "PLAN-B", "tasks", "_SUPERSEDED.md"),
)


def _target() -> Path:
    root = _repo_root()
    for parts in _CANDIDATES:
        candidate = root.joinpath(*parts)
        if candidate.is_file():
            return candidate
    # Return the canonical (active) path so the failure message points
    # at the location P7-5 originally targeted.
    return root.joinpath(*_CANDIDATES[0])


class TestTaskP7_5:
    @pytest.mark.docs
    def test_superseded_has_runtime_vs_archived_section(self) -> None:
        path = _target()
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        assert "runtime-active" in lower or "runtime active" in lower, (
            "_SUPERSEDED.md must label runtime-active sub-deliverables"
        )
        assert "archived" in lower, "_SUPERSEDED.md must label archived sub-deliverables"

    @pytest.mark.docs
    def test_superseded_has_explicit_subsection_heading(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # A markdown heading (## or ###) referencing runtime-active /
        # archived split must exist so readers can navigate to it.
        import re

        assert re.search(
            r"^#{2,4}\s+.*(runtime[- ]active|archived).*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        ), (
            "_SUPERSEDED.md must add a markdown heading distinguishing "
            "runtime-active from archived sub-deliverables"
        )
