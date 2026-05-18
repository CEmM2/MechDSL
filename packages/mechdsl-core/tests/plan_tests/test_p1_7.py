from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"
EXPECTED_MVP_FILES = (
    "dev/plans/MVP_plan.md",
    "dev/plans/MVP_sprint1.md",
    "dev/plans/MVP_sprint2.md",
    "dev/plans/MVP_sprint3.md",
)


def _phase1_action_rows() -> list[list[str]]:
    text = PLAN.read_text(encoding="utf-8")
    phase1_match = re.search(
        r"^## Phase 1 —.*?(?=^## Phase 2 —)", text, flags=re.MULTILINE | re.DOTALL
    )
    assert phase1_match, "Phase 1 section not found"
    section = phase1_match.group(0)
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("| P1-") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows


class TestTaskP1_7:
    """
    Tests for Task P1-7: Add P1-6 supersession task in recovery plan
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_phase1_action_table_has_six_rows(self) -> None:
        rows = _phase1_action_rows()
        assert len(rows) == 6, (
            f"expected 6 P1-* rows in Phase 1, found {len(rows)}: {[r[0] for r in rows]}"
        )
        ids = [r[0] for r in rows]
        assert ids == [f"P1-{n}" for n in range(1, 7)], f"unexpected Task IDs in Phase 1: {ids}"

    @pytest.mark.audit
    def test_p1_6_row_has_correct_metadata(self) -> None:
        rows = _phase1_action_rows()
        p1_6 = next((r for r in rows if r[0] == "P1-6"), None)
        assert p1_6 is not None, "P1-6 row missing from Phase 1 action-item table"
        # cells: Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification
        tier = p1_6[5]
        blocked_by = p1_6[4]
        assert tier == "docs", f"P1-6 Tier should be 'docs', got {tier!r}"
        assert blocked_by == "P1-4", f"P1-6 Blocked by should be 'P1-4', got {blocked_by!r}"

    @pytest.mark.audit
    def test_all_four_mvp_plan_files_listed(self) -> None:
        rows = _phase1_action_rows()
        p1_6 = next((r for r in rows if r[0] == "P1-6"), None)
        assert p1_6 is not None
        files_cell = p1_6[3]
        for expected in EXPECTED_MVP_FILES:
            assert expected in files_cell, f"P1-6 row missing reference to {expected}"
