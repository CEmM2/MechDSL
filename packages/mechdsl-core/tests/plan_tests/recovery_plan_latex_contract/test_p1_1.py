"""Live audit for recovery-plan P1-1: Define two support tiers (MVP-stable / experimental).

Asserts that README.md publishes the two tier names with their expected
membership boundaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
README = REPO_ROOT / "README.md"


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


class TestTaskP1_1:
    """
    Tests for Task P1-1: Define two support tiers for the repo: `MVP-stable` and `experimental`.
    Tier: docs
    """

    @pytest.mark.audit
    def test_support_tiers_section_present(self) -> None:
        """README.md exposes the canonical Support tiers heading."""
        text = _readme_text()
        assert "## Support tiers" in text, "README missing '## Support tiers' heading"

    @pytest.mark.audit
    def test_both_tier_names_and_canonical_membership_listed(self) -> None:
        """Both tier names appear with their expected canonical / experimental members."""
        text = _readme_text()
        assert "`MVP-stable`" in text, "MVP-stable tier name missing"
        assert "`experimental`" in text, "experimental tier name missing"
        # Canonical-tier surfaces called out by name
        for canonical in ("Hex8", "Total Lagrangian", "Taichi"):
            assert canonical in text, f"MVP-stable tier should reference {canonical!r}"
        # Experimental-tier surfaces called out by name
        for experimental in ("MFEM", "MOOSE"):
            assert experimental in text, f"experimental tier should reference {experimental!r}"
