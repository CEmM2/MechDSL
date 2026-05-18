"""Close all 9 Phase-1 task issues, update phase-1 issue body checklist,
close the phase-1 issue, and check off Phase 1 in the plan-overview issue."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "dev" / "tasks" / "back2latex" / "github_issue_map.json"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kwargs)


def close_task_issues(task_issues: dict[str, int]) -> None:
    for tid, num in task_issues.items():
        # Add done + gate labels, remove blocked, then close.
        run(
            [
                "gh",
                "issue",
                "edit",
                str(num),
                "--remove-label",
                "blocked",
                "--add-label",
                "done,gate-b-pass",
            ]
        )
        run(
            [
                "gh",
                "issue",
                "close",
                str(num),
                "--comment",
                f"{tid} done — Phase 1 compressed exec; see dev/tasks/back2latex/gates/phase_1_gates.md.",
            ]
        )
        print(f"closed task #{num} ({tid})")


def update_phase_issue(phase_issue: int, task_issues: dict[str, int]) -> None:
    # Fetch current body, replace `- [ ] #<num>` with `- [x] #<num>` for each task issue.
    body = run(["gh", "issue", "view", str(phase_issue), "--json", "body", "-q", ".body"]).stdout
    for num in task_issues.values():
        body = body.replace(f"- [ ] #{num} ", f"- [x] #{num} ")
    # Flip the status banner.
    body = body.replace(
        "**Status:** ✅ Scaffolded",
        "**Status:** ✅ Phase complete (all 9 tasks done, 27/27 audit tests pass)",
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
        body_path = f.name
    run(["gh", "issue", "edit", str(phase_issue), "--body-file", body_path])
    run(
        [
            "gh",
            "issue",
            "close",
            str(phase_issue),
            "--comment",
            "Phase 1 complete — 9/9 tasks done, 27/27 audit tests pass. See dev/tasks/back2latex/gates/phase_1_gates.md and Handoff_Phase_2.md.",
        ]
    )
    print(f"closed phase issue #{phase_issue}")


def check_off_in_overview(plan_overview: int, phase_issue: int) -> None:
    body = run(["gh", "issue", "view", str(plan_overview), "--json", "body", "-q", ".body"]).stdout
    body = body.replace("- [ ] Phase 1: ", "- [x] Phase 1: ")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
        body_path = f.name
    run(["gh", "issue", "edit", str(plan_overview), "--body-file", body_path])
    print(f"checked off Phase 1 in overview #{plan_overview}")


def main() -> None:
    issue_map = json.loads(MAP_PATH.read_text())
    phase1 = issue_map["phases"]["1"]
    close_task_issues(phase1["task_issues"])
    update_phase_issue(phase1["issue_number"], phase1["task_issues"])
    check_off_in_overview(issue_map["plan_overview_issue"], phase1["issue_number"])


if __name__ == "__main__":
    main()
