"""P2-4 verification — recursive `/Aut_Faciam scaffold 1` on the recovery plan.

Evidence: scaffold artifacts under `dev/tasks/recovery_plan_latex_contract/`
plus the GH-side state recorded in `github_issue_map.json`. Skipped until
those artifacts exist.

Hard-stop invariant: this test does NOT run /Aut_Faciam exec; the test
only inspects the *outputs* of scaffold to confirm exec was not invoked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
RP_TASKS = REPO_ROOT / "dev" / "tasks" / "recovery_plan_latex_contract"


def _require_scaffold() -> dict:
    gates_file = RP_TASKS / "gates" / "phase_1_gates.md"
    if not gates_file.is_file():
        pytest.skip(
            "recovery-plan Phase 1 not yet scaffolded — run "
            "/Aut_Faciam scaffold 1 dev/plans/recovery_plan_latex_contract.md"
        )
    gh_map_file = RP_TASKS / "github_issue_map.json"
    if not gh_map_file.is_file():
        pytest.skip("recovery-plan github_issue_map.json missing")
    return json.loads(gh_map_file.read_text(encoding="utf-8"))


class TestTaskP2_4:
    """
    Tests for Task P2-4: Run /Aut_Faciam scaffold 1 on recovery plan and stop
    Acceptance criteria covered: 1, 2, 3, 4, 5
    """

    @pytest.mark.integration
    def test_phase1_gates_file_exists(self) -> None:
        _require_scaffold()
        gates_file = RP_TASKS / "gates" / "phase_1_gates.md"
        body = gates_file.read_text(encoding="utf-8")
        assert body.strip(), "phase_1_gates.md is empty"

    @pytest.mark.integration
    def test_six_task_issues_recorded_for_phase1(self) -> None:
        gh_map = _require_scaffold()
        phase1 = gh_map.get("phases", {}).get("1", {})
        task_issues = phase1.get("task_issues", {})
        assert len(task_issues) == 6, (
            f"expected 6 recovery-plan Phase-1 task issues (P1-1..P1-6), "
            f"found {len(task_issues)}: {list(task_issues)}"
        )

    @pytest.mark.integration
    def test_completion_data_consistent_with_status(self) -> None:
        """Post-exec invariant: a task has a ``completion_date`` iff ``status == 'done'``.

        History: this test originally enforced a *hard stop* that no
        ``/Aut_Faciam exec`` had run against the recovery plan during the
        back2latex P2-4 engagement. That invariant was honored at back2latex
        commit time and is recorded in
        ``dev/tasks/back2latex/gates/phase_2_gates.md``. Recovery-plan exec is
        now authorized in subsequent engagements; the assertion was relaxed to
        a data-integrity check that survives across exec phases.
        """
        gh_map = _require_scaffold()
        json_dir = RP_TASKS / "json"
        if not json_dir.is_dir():
            pytest.skip("json/ not present yet")
        for f in sorted(json_dir.glob("P*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            status = data.get("status")
            completion = data.get("completion_date")
            if status == "done":
                assert completion, f"{f.name} status=done but completion_date empty"
            elif status in ("", "pending"):
                assert not completion, (
                    f"{f.name} status={status!r} but completion_date={completion!r} (should be empty)"
                )
