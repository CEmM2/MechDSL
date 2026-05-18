"""Live audit for recovery-plan P1-4: Normalize tracker vocabulary.

Asserts the canonical status legend exists and lists all four required values,
and the MVP-plan tracker has been wired to reference it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
LEGEND = REPO_ROOT / "dev" / "tracking" / "STATUS_LEGEND.md"
MVP_TRACKER = REPO_ROOT / "dev" / "tracking" / "tasks-tracker_MVP_plan.md"

REQUIRED_VALUES = ("not_started", "done", "deferred", "implemented-via-substitute")


class TestTaskP1_4:
    """
    Tests for Task P1-4: Normalize tracker vocabulary.
    Tier: docs
    """

    @pytest.mark.audit
    def test_status_legend_file_exists(self) -> None:
        assert LEGEND.is_file(), f"missing canonical legend: {LEGEND}"

    @pytest.mark.audit
    def test_legend_lists_all_four_required_values(self) -> None:
        text = LEGEND.read_text(encoding="utf-8")
        for value in REQUIRED_VALUES:
            assert f"`{value}`" in text, f"STATUS_LEGEND.md missing canonical value `{value}`"

    @pytest.mark.audit
    def test_mvp_plan_tracker_references_legend(self) -> None:
        text = MVP_TRACKER.read_text(encoding="utf-8")
        assert "STATUS_LEGEND.md" in text, (
            "MVP_plan tracker should reference STATUS_LEGEND.md so future readers can resolve status values"
        )
        assert "implemented-via-substitute" in text, (
            "MVP_plan tracker preamble should cite the new vocabulary explicitly"
        )
