from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"
TIER_VOCABULARY = {"unit", "integration", "regression", "docs", "manual"}
EXPECTED_HEADER = (
    "| Task ID | Legacy ID | Action item | Files / surfaces | Blocked by | Tier | Verification |"
)


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


def _action_item_tables() -> list[list[str]]:
    """Return each action-item table's body rows (one list of row-strings per phase)."""
    text = _plan_text()
    tables: list[list[str]] = []
    # Each phase's action-item table is preceded by `### Action items` and starts at
    # the `| Task ID | …` header line.
    for action_match in re.finditer(r"^### Action items\b", text, flags=re.MULTILINE):
        tail = text[action_match.end() :]
        header_match = re.search(r"^\| Task ID .+\|$", tail, flags=re.MULTILINE)
        assert header_match, "action-item table missing Task ID header"
        body_start = tail.find("\n", header_match.end()) + 1
        # body rows continue until a blank line or the next `###` heading
        body_section = tail[body_start:]
        end_match = re.search(r"^\s*$|^###? ", body_section, flags=re.MULTILINE)
        body = body_section[: end_match.start()] if end_match else body_section
        rows = [
            line
            for line in body.splitlines()
            if line.startswith("|") and not line.startswith("|---") and "Task ID" not in line
        ]
        tables.append(rows)
    return tables


class TestTaskP1_3:
    """
    Tests for Task P1-3: Rewrite action-item tables with new columns
    Acceptance criteria covered: 1, 2, 3, 4
    """

    @pytest.mark.audit
    def test_seven_column_header_on_every_action_table(self) -> None:
        text = _plan_text()
        headers = re.findall(r"^\| Task ID \| Legacy ID \| .+\|$", text, flags=re.MULTILINE)
        assert len(headers) == 7, f"expected 7 canonical headers, found {len(headers)}"
        for h in headers:
            assert h == EXPECTED_HEADER, f"header mismatch: {h!r}"

    @pytest.mark.audit
    def test_task_ids_match_canonical_regex(self) -> None:
        tables = _action_item_tables()
        assert len(tables) == 7, f"expected 7 action-item tables, found {len(tables)}"
        for phase_idx, rows in enumerate(tables, start=1):
            assert rows, f"phase {phase_idx} has no action-item rows"
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                task_id = cells[0]
                assert re.fullmatch(r"P[1-7]-[0-9]+", task_id), (
                    f"phase {phase_idx} row has non-canonical Task ID: {task_id!r}"
                )
                assert task_id.startswith(f"P{phase_idx}-"), (
                    f"phase {phase_idx} contains foreign Task ID {task_id}"
                )

    @pytest.mark.audit
    def test_tier_values_drawn_from_vocabulary(self) -> None:
        tables = _action_item_tables()
        for phase_idx, rows in enumerate(tables, start=1):
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                tier = cells[5]
                assert tier in TIER_VOCABULARY, (
                    f"phase {phase_idx} task {cells[0]} has invalid tier {tier!r}; "
                    f"must be one of {sorted(TIER_VOCABULARY)}"
                )

    @pytest.mark.audit
    def test_cross_phase_blockers_use_canonical_ids(self) -> None:
        tables = _action_item_tables()
        for phase_idx, rows in enumerate(tables, start=1):
            for row in rows:
                cells = [c.strip() for c in row.strip("|").split("|")]
                blocked_by = cells[4]
                if blocked_by in ("", "—"):
                    continue
                tokens = [t.strip() for t in blocked_by.split(",")]
                for tok in tokens:
                    assert re.fullmatch(r"P[1-7]-[0-9]+", tok), (
                        f"phase {phase_idx} task {cells[0]} has non-canonical "
                        f"blocked_by token {tok!r}"
                    )
                    # legacy-style R-IDs must not appear
                    assert not re.match(r"R\d\.\d", tok), (
                        f"legacy R-style ID {tok} leaked into Blocked by"
                    )
