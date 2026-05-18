"""Live audit for recovery-plan P1-6: MVP plans superseded banners.

Asserts that MVP_plan.md and the three MVP_sprint plans carry a
supersession banner that points readers at the recovery plan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
PLANS_DIR = REPO_ROOT / "dev" / "plans"

SUPERSEDED_PLANS = (
    PLANS_DIR / "MVP_plan.md",
    PLANS_DIR / "MVP_sprint1.md",
    PLANS_DIR / "MVP_sprint2.md",
    PLANS_DIR / "MVP_sprint3.md",
)


def _head(p: Path, lines: int = 6) -> str:
    return "\n".join(p.read_text(encoding="utf-8").splitlines()[:lines])


class TestTaskP1_6:
    """
    Tests for Task P1-6: Mark MVP plans as superseded.
    Tier: docs
    """

    @pytest.mark.audit
    def test_each_superseded_plan_has_top_banner(self) -> None:
        for plan in SUPERSEDED_PLANS:
            head = _head(plan)
            assert "Superseded" in head, (
                f"{plan.relative_to(REPO_ROOT)} should have a Superseded banner near the top"
            )
            assert "recovery_plan_latex_contract.md" in head, (
                f"{plan.relative_to(REPO_ROOT)} banner should reference the recovery plan"
            )

    @pytest.mark.audit
    def test_main_plan_cites_status_vocabulary(self) -> None:
        head = _head(PLANS_DIR / "MVP_plan.md")
        # The main MVP plan's banner is the canonical place to cite the new
        # status vocabulary; sprint plans link out via STATUS_LEGEND.md only.
        assert "implemented-via-substitute" in head, (
            "MVP_plan.md banner should cite the implemented-via-substitute status"
        )
        assert "STATUS_LEGEND.md" in head, "MVP_plan.md banner should reference STATUS_LEGEND.md"

    @pytest.mark.audit
    def test_banner_links_drift_history_note(self) -> None:
        head = _head(PLANS_DIR / "MVP_plan.md")
        assert "frontend_drift_history.md" in head, (
            "MVP_plan.md banner should link the frontend_drift_history note from P1-5"
        )
