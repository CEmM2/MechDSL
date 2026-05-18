"""Tests for Task P5-5: design-doc note on substitution + feature-flag fallback.

Acceptance criteria covered:
1. Doc contains MECHDSL_USE_IMPORTED_RR mention.
2. Doc cross-links to dev/algorithms/radial_return_j2.tex.
3. Doc describes substitution default + fallback role.
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


def _doc_candidates() -> list[Path]:
    """Per plan line 252-256, the note lands in 06-PLASTICITY.md or
    07-CONVENTIONS.md. Return whichever exists."""
    return [
        p
        for p in (
            _repo_root() / "dev" / "design_docs" / "06-PLASTICITY.md",
            _repo_root() / "dev" / "design_docs" / "07-CONVENTIONS.md",
        )
        if p.is_file()
    ]


def _doc_text() -> str:
    docs = _doc_candidates()
    assert docs, "neither 06-PLASTICITY.md nor 07-CONVENTIONS.md found"
    return "\n".join(p.read_text(encoding="utf-8") for p in docs)


class TestTaskP5_5:
    """Tests for Task P5-5: design-doc note on substitution."""

    @pytest.mark.docs
    def test_doc_mentions_feature_flag(self) -> None:
        text = _doc_text()
        assert "MECHDSL_USE_IMPORTED_RR" in text, (
            "design doc must mention the MECHDSL_USE_IMPORTED_RR env-var name"
        )

    @pytest.mark.docs
    def test_doc_cross_links_algorithm_source(self) -> None:
        text = _doc_text()
        assert "dev/algorithms/radial_return_j2.tex" in text, (
            "design doc must reference dev/algorithms/radial_return_j2.tex"
        )

    @pytest.mark.docs
    def test_doc_describes_substitution_default(self) -> None:
        text = _doc_text().lower()
        # The note must state that algo2code is default and imported is the
        # feature-flagged fallback, matching post-Phase-5 reality.
        assert "default" in text and "fallback" in text, (
            "design doc must describe default-vs-fallback dispatch roles"
        )
        assert "algo2code" in text, "design doc must name the algo2code path"
        assert "imported" in text, "design doc must name the imported (legacy) path"
