"""Tests for Task P7-3: rename gen_p7_2 module-name + drop obsolete
traction-string-gap comment.

Acceptance:
1. test_p7_2.py no longer hardcodes a literal `"gen_p7_2"` module name —
   the helper invocation passes a fixture-derived value (e.g. uuid or
   nodeid-based).
2. The traction-string-gap comment that pointed at Phase 1 closure is
   removed (Phase 1 has landed).
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


def _target() -> Path:
    return (
        _repo_root()
        / "packages"
        / "mechdsl-core"
        / "tests"
        / "plan_tests"
        / "recovery_plan_latex_contract"
        / "test_p7_2.py"
    )


class TestTaskP7_3:
    @pytest.mark.docs
    def test_module_name_no_longer_hardcoded(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # No bare ``name="gen_p7_2"`` literal at any call site.
        assert not re.search(r'name\s*=\s*"gen_p7_2"', text), (
            'test_p7_2.py must not hardcode name="gen_p7_2" — '
            "derive from a fixture (uuid or pytest nodeid)"
        )

    @pytest.mark.docs
    def test_module_name_uses_fixture_or_uuid(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # Must reference a fixture-derived source — either uuid or the
        # pytest request fixture's node id.
        assert "uuid" in text or "request.node" in text or "request.nodeid" in text, (
            "test_p7_2.py must derive module name from uuid or pytest request fixture"
        )

    @pytest.mark.docs
    def test_obsolete_traction_string_gap_comment_removed(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # Phase 1 closure landed — the forward-pointer comment that
        # said "blocked on Phase 1" must be gone.
        assert "blocked on Phase 1" not in text.lower().replace("-", " ")
        # The substantive traction-string-gap comment block (item 9 in
        # the post_recovery_plan follow-ups) is no longer needed.
        assert "traction-string gap" not in text and "traction string gap" not in text.lower(), (
            "obsolete traction-string-gap comment must be removed (Phase 1 has landed)"
        )
