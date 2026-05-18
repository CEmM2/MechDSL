"""Live audit for recovery-plan P2-4: reconcile old MVP P2.x rows with recovery tasks.

Asserts that the legacy Phase-2 task rows (`P2.1..P2.5`) in the MVP_plan
tracker carry the canonical ``implemented-via-substitute`` status and cite
their substitute, removing the duplicate/conflicting frontend task set.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
MVP_TRACKER = REPO_ROOT / "dev" / "tracking" / "tasks-tracker_MVP_plan.md"

LEGACY_IDS = ("P2.1", "P2.2", "P2.3", "P2.4", "P2.5")


def _legacy_rows() -> dict[str, list[str]]:
    """Return main-task-table rows for P2.1..P2.5.

    The MVP tracker also has a 3-column verification mapping table whose rows
    start with ``| P2.`` — we discriminate by column count so only the main
    10-column task rows are collected.
    """
    text = MVP_TRACKER.read_text(encoding="utf-8")
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("| P2."):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9:  # skip the verification mapping table (3 cols)
            continue
        if cells and cells[0] in LEGACY_IDS:
            rows[cells[0]] = cells
    return rows


class TestTaskP2_4:
    """
    Tests for Task P2-4: Reconcile or replace old Phase 2 tasks with recovery tasks.
    Tier: docs
    """

    @pytest.mark.audit
    def test_all_five_legacy_rows_present(self) -> None:
        rows = _legacy_rows()
        missing = [tid for tid in LEGACY_IDS if tid not in rows]
        assert not missing, f"missing legacy MVP rows in tracker: {missing}"

    @pytest.mark.audit
    def test_no_legacy_row_still_marked_not_started(self) -> None:
        rows = _legacy_rows()
        for tid in LEGACY_IDS:
            cells = rows[tid]
            status = cells[2]
            assert status != "not_started", (
                f"{tid} should no longer be `not_started`; current status is {status!r}"
            )

    @pytest.mark.audit
    def test_each_legacy_row_uses_canonical_substitute_status(self) -> None:
        rows = _legacy_rows()
        for tid in LEGACY_IDS:
            cells = rows[tid]
            status = cells[2]
            assert status == "implemented-via-substitute", (
                f"{tid} status should be `implemented-via-substitute`, found {status!r}"
            )

    @pytest.mark.audit
    def test_each_legacy_row_cites_a_substitute(self) -> None:
        rows = _legacy_rows()
        for tid in LEGACY_IDS:
            cells = rows[tid]
            # The substitute citation lives in the `Verified by` column (index 8)
            verified_by = cells[8] if len(cells) > 8 else ""
            assert verified_by and verified_by != "—", (
                f"{tid} must cite its substitute in 'Verified by'; found {verified_by!r}"
            )
            # At least one canonical-recovery-task ID OR a concrete code path
            cites_recovery = re.search(r"recovery P\d-\d+", verified_by) is not None
            cites_code = re.search(r"`[a-z_/]+\.py", verified_by) is not None
            assert cites_recovery or cites_code, (
                f"{tid} 'Verified by' should cite a recovery task ID or a code path; "
                f"found {verified_by!r}"
            )
