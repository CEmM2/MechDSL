"""Tests for Task P6-4: replace _INTENTIONAL_CLEANUP_MATCHES line-number
whitelist with regex/marker comment matching.

Acceptance criteria:
1. test_phase6_exit.py no longer hardcodes line numbers for the
   intentional cleanup sites.
2. test_emission_verification.py carries the in-source markers
   (``# intentional-cleanup-site``) at the lines that were previously
   tracked by absolute number.
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


_PHASE6_EXIT = "packages/mechdsl-core/tests/test_phase6_exit.py"
_EMISSION = "packages/mechdsl-core/tests/test_emission_verification.py"


class TestTaskP6_4:
    """Tests for Task P6-4: marker-driven cleanup-site whitelist."""

    @pytest.mark.unit
    def test_phase6_exit_no_line_number_whitelist(self) -> None:
        text = (_repo_root() / _PHASE6_EXIT).read_text(encoding="utf-8")
        # The old whitelist hardcoded `("…test_emission_verification.py", 747)`
        # tuples. Phase 6 replaces them with marker-comment scanning.
        assert "_INTENTIONAL_CLEANUP_MATCHES" not in text or ("intentional-cleanup-site" in text), (
            "test_phase6_exit.py must either drop _INTENTIONAL_CLEANUP_MATCHES "
            "or rewrite it to scan for the in-source marker"
        )
        # No bare integer-line-number entries pointing at
        # test_emission_verification.py. (Pre-fix the whitelist held two
        # hardcoded line numbers.)
        import re

        bad = re.findall(r"test_emission_verification\.py\"?,\s*\d+", text)
        assert not bad, (
            f"test_phase6_exit.py still hardcodes line numbers for "
            f"test_emission_verification.py: {bad}"
        )

    @pytest.mark.unit
    def test_emission_verification_has_markers(self) -> None:
        text = (_repo_root() / _EMISSION).read_text(encoding="utf-8")
        assert "intentional-cleanup-site" in text, (
            "test_emission_verification.py must mark its intentional cleanup "
            "sites with the comment '# intentional-cleanup-site'"
        )

    @pytest.mark.unit
    def test_phase6_exit_uses_marker_scan(self) -> None:
        text = (_repo_root() / _PHASE6_EXIT).read_text(encoding="utf-8")
        # The marker scan is the new mechanism — must be referenced.
        assert "intentional-cleanup-site" in text, (
            "test_phase6_exit.py must scan for the in-source "
            "'intentional-cleanup-site' marker comment"
        )
