from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"
APPENDED_ROW = (
    "- [ ] All canonical task IDs in `dev/tasks/recovery_plan_latex_contract/json/` "
    "reach `done` status, with their corresponding GitHub issues closed."
)


def _success_block() -> str:
    text = PLAN.read_text(encoding="utf-8")
    match = re.search(r"^## Success criteria\b.*?(?=^## )", text, flags=re.MULTILINE | re.DOTALL)
    assert match, "Success criteria section missing"
    return match.group(0)


class TestTaskP1_9:
    """
    Tests for Task P1-9: Update success criteria checklist with canonical-IDs row
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_new_checkbox_appended_at_end(self) -> None:
        block = _success_block()
        rows = re.findall(r"^- \[ \] .+$", block, flags=re.MULTILINE)
        assert rows, "no checklist rows found in Success criteria"
        assert rows[-1] == APPENDED_ROW, f"appended row is not last; last row is: {rows[-1]!r}"

    @pytest.mark.audit
    def test_existing_checkbox_rows_unchanged(self) -> None:
        block = _success_block()
        # the original 9 rows + 1 appended = 10 total
        rows = re.findall(r"^- \[ \] .+$", block, flags=re.MULTILINE)
        assert len(rows) == 10, f"expected 10 checklist rows after append, found {len(rows)}"
        # spot-check a representative original row remains
        expected_original = (
            "- [ ] `mechdsl-core` exposes a canonical `compile_latex(...)` or equivalent façade."
        )
        assert expected_original in block, "original first checkbox row was modified or removed"

    @pytest.mark.audit
    def test_new_row_references_recovery_plan_json_dir(self) -> None:
        block = _success_block()
        assert "dev/tasks/recovery_plan_latex_contract/json/" in block, (
            "appended row missing the verbatim path reference"
        )
