"""P2-2 verification — recursive `/Aut_Faciam tasks` on the recovery plan.

P2-2 is integration-tier; its evidence is the existence and shape of the
artifacts that Plan-2-Tasks produces under
`dev/tasks/recovery_plan_latex_contract/`. The tests below skip until that
directory exists, then assert on the expected layout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
RP_TASKS = REPO_ROOT / "dev" / "tasks" / "recovery_plan_latex_contract"
RP_TRACKER = REPO_ROOT / "dev" / "tracking" / "tasks-tracker_recovery_plan_latex_contract.md"


def _require_artifacts() -> None:
    if not RP_TASKS.is_dir():
        pytest.skip(
            "recovery_plan_latex_contract task tree not yet generated — run "
            "/Aut_Faciam tasks dev/plans/recovery_plan_latex_contract.md"
        )


class TestTaskP2_2:
    """
    Tests for Task P2-2: Run /Aut_Faciam tasks on amended recovery plan
    Acceptance criteria covered: 1, 2, 3, 4, 5
    """

    @pytest.mark.integration
    def test_all_tasks_md_row_count(self) -> None:
        _require_artifacts()
        all_tasks = (RP_TASKS / "all-tasks.md").read_text(encoding="utf-8")
        rows = [
            line
            for line in all_tasks.splitlines()
            if line.startswith("| P") and not line.startswith("|---")
        ]
        # Recovery plan decomposes to 6+6+5+5+5+5+6 = 38 rows after the P1-6
        # supersession task lands; allow a small window around that target.
        assert 30 <= len(rows) <= 42, f"expected 30-42 task rows in all-tasks.md, found {len(rows)}"

    @pytest.mark.integration
    def test_one_json_per_task_with_required_fields(self) -> None:
        _require_artifacts()
        json_dir = RP_TASKS / "json"
        assert json_dir.is_dir(), "json/ directory missing"
        files = sorted(json_dir.glob("P*.json"))
        assert files, "no task JSONs found"
        required_keys = ("objective", "scope", "acceptance_criteria")
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            for key in required_keys:
                assert data.get(key), f"{f.name} has empty {key}"
            tier = data.get("test_plan", {}).get("tier")
            assert tier, f"{f.name} has empty test_plan.tier"

    @pytest.mark.integration
    def test_seven_phase_context_summaries(self) -> None:
        _require_artifacts()
        for n in range(1, 8):
            ctx = RP_TASKS / f"Phase_{n}_context_summary.md"
            assert ctx.is_file(), f"missing {ctx.name}"

    @pytest.mark.integration
    def test_tracker_file_present(self) -> None:
        _require_artifacts()
        assert RP_TRACKER.is_file(), f"recovery-plan tracker missing: {RP_TRACKER}"

    @pytest.mark.integration
    def test_github_issue_map_populated(self) -> None:
        _require_artifacts()
        gh_map = RP_TASKS / "github_issue_map.json"
        if not gh_map.is_file():
            pytest.skip("github_issue_map.json not generated (gh integration deferred)")
        data = json.loads(gh_map.read_text(encoding="utf-8"))
        assert data.get("plan_overview_issue"), "plan_overview_issue missing"
        phases = data.get("phases", {})
        assert all(str(n) in phases for n in range(1, 8)), (
            f"expected phases 1..7 in issue map, got {sorted(phases)}"
        )
        for n in range(1, 8):
            assert phases[str(n)].get("issue_number"), f"phase {n} issue_number missing"
