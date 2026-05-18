from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


def _risks_table() -> tuple[str, list[list[str]]]:
    """Return (header_row, body_rows) of the Risks and mitigations table."""
    text = _plan_text()
    section_match = re.search(
        r"^## Risks and mitigations\b.*?(?=^## )", text, flags=re.MULTILINE | re.DOTALL
    )
    assert section_match, "Risks and mitigations section missing"
    section = section_match.group(0)
    rows = [line for line in section.splitlines() if line.startswith("|")]
    assert rows, "no table rows in Risks and mitigations"
    header = rows[0]
    body = [r for r in rows[1:] if not r.startswith("|---")]
    parsed = [[c.strip() for c in r.strip("|").split("|")] for r in body]
    return header, parsed


def _all_canonical_task_ids() -> set[str]:
    text = _plan_text()
    return set(re.findall(r"\bP[1-7]-[0-9]+\b", text))


class TestTaskP1_6:
    """
    Tests for Task P1-6: Add 'Affects task(s)' column to risks table
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_risks_table_has_affects_column(self) -> None:
        header, _ = _risks_table()
        assert "Affects task(s)" in header, f"header missing 'Affects task(s)' column: {header!r}"

    @pytest.mark.audit
    def test_no_blank_affects_cells(self) -> None:
        _, body = _risks_table()
        assert body, "no risk rows found"
        for row in body:
            assert len(row) >= 4, f"row too short: {row!r}"
            affects = row[3]
            assert affects, f"blank Affects task(s) cell in row: {row!r}"

    @pytest.mark.audit
    def test_affected_task_ids_exist_in_action_tables(self) -> None:
        _, body = _risks_table()
        canonical = _all_canonical_task_ids()
        assert canonical, "no canonical task IDs found anywhere in plan — P1-3 must run first"
        for row in body:
            affects = row[3]
            if affects in ("", "—"):
                continue
            tokens = [t.strip() for t in affects.split(",") if t.strip()]
            for tok in tokens:
                assert re.fullmatch(r"P[1-7]-[0-9]+", tok), (
                    f"non-canonical token {tok!r} in Affects task(s) cell of row: {row!r}"
                )
                assert tok in canonical, (
                    f"affected task {tok!r} is not defined in any action-item table"
                )
