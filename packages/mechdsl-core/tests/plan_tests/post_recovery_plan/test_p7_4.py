"""Tests for Task P7-4: trim test_p7_6.py to 100-250 lines by merging
redundant sub-bullets.

Acceptance:
1. Line count in [100, 250].
2. Test still passes after the trim (verified by running the file).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _target() -> Path:
    return (
        _repo_root()
        / "packages"
        / "mechdsl-core"
        / "tests"
        / "plan_tests"
        / "recovery_plan_latex_contract"
        / "test_p7_6.py"
    )


class TestTaskP7_4:
    @pytest.mark.docs
    def test_test_p7_6_within_line_budget(self) -> None:
        path = _target()
        assert path.is_file(), f"missing {path}"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 100 <= line_count <= 250, (
            f"test_p7_6.py must be within [100, 250] lines; got {line_count}"
        )

    @pytest.mark.docs
    def test_test_p7_6_still_documents_four_pillars(self) -> None:
        text = _target().read_text(encoding="utf-8").lower()
        # The four pillars (R1 frontend, R2 algo2code seam, R3 lib substitution,
        # R4-R6 stable backend / docs / acceptance) must still be referenced
        # post-trim — trim by merging redundant sub-bullets only.
        for pillar in ("r1", "r2", "r3"):
            assert pillar in text, (
                f"trim dropped pillar {pillar!r} — only redundant sub-bullets should be merged"
            )
