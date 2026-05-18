"""Live audit for recovery-plan P1-5: Record frontend deferral as historical drift.

Asserts the dev/reviews/frontend_drift_history.md note exists and
distinguishes 'planned but deferred' from 'never planned' from
'implemented via substitute'.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
NOTE = REPO_ROOT / "dev" / "reviews" / "frontend_drift_history.md"


def _note_text() -> str:
    return NOTE.read_text(encoding="utf-8")


class TestTaskP1_5:
    """
    Tests for Task P1-5: Record the frontend deferral as historical execution drift.
    Tier: docs
    """

    @pytest.mark.audit
    def test_drift_note_exists(self) -> None:
        assert NOTE.is_file(), f"missing frontend drift note: {NOTE}"

    @pytest.mark.audit
    def test_distinguishes_planned_vs_never_planned_vs_substituted(self) -> None:
        text = _note_text()
        for pattern in (
            "Planned but never implemented",
            "Never planned",
            "Implemented via substitute",
        ):
            assert pattern in text, f"drift note missing classification: {pattern!r}"

    @pytest.mark.audit
    def test_links_back_to_drift_audit_and_recovery_plan(self) -> None:
        text = _note_text()
        assert "drift_20_04.md" in text, (
            "drift note should reference the original audit (drift_20_04.md)"
        )
        assert "recovery_plan_latex_contract.md" in text, (
            "drift note should reference the recovery plan that handles it"
        )
