"""Create the 7 recovery-plan phase-skeleton issues, then patch the
plan-overview body and the github_issue_map.json.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "dev" / "tasks" / "recovery_plan_latex_contract"
MAP = TASKS / "github_issue_map.json"
SLUG = "recovery-plan-latex-contract"
PLAN_OVERVIEW_ISSUE = 140

PHASE_NAMES = {
    1: "Freeze the contract surface (R0)",
    2: "Restore the frontend as the canonical entry point (R1)",
    3: "Enrich `ProblemIR` into the semantic center again (R2)",
    4: "Enrich `ElementIR` and normalize lowering boundaries (R3)",
    5: "Re-anchor Taichi codegen as the stable path (R4)",
    6: "Integrate `algo2code` at the least risky seam (R5)",
    7: "Verification, governance, and closure (R6)",
}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw)


def phase_skeleton_body(phase: int, json_dir: Path) -> str:
    name = PHASE_NAMES[phase]
    # Pull the context summary content
    ctx_path = TASKS / f"Phase_{phase}_context_summary.md"
    ctx = ctx_path.read_text(encoding="utf-8") if ctx_path.is_file() else ""

    # Enumerate tasks
    task_jsons = sorted(json_dir.glob(f"P{phase}-*.json"))
    parts = [
        f"## Phase {phase}: {name}",
        "",
        "**Status:** ⏳ Not yet scaffolded",
        f"**Plan overview:** #{PLAN_OVERVIEW_ISSUE}",
    ]
    if phase > 1:
        parts.append(
            f"**Handoff from Phase {phase - 1}:** Pending — will be linked after Phase {phase - 1} completes"
        )
    parts.append("")
    parts.append("### Tasks (pending scaffold)")
    for jp in task_jsons:
        d = json.loads(jp.read_text())
        parts.append(f"- [ ] {d['task_id']}: {d['title']}")
    parts.append("")
    parts.append("### Phase Context Summary")
    parts.append(ctx)
    parts.append("")
    parts.append(
        "---\n*This issue will be populated with full task details, test coverage, "
        "and acceptance criteria when ScaffoldPhase is run.*"
    )
    return "\n".join(parts)


def main() -> None:
    issue_map = json.loads(MAP.read_text())
    json_dir = TASKS / "json"

    bodies_dir = ROOT / ".context" / "issue_bodies" / "recovery_phases"
    bodies_dir.mkdir(parents=True, exist_ok=True)

    for n in range(1, 8):
        body = phase_skeleton_body(n, json_dir)
        body_file = bodies_dir / f"phase_{n}.md"
        body_file.write_text(body)

        title = f"[{SLUG}] Phase {n}: {PHASE_NAMES[n]}"
        cmd = [
            "gh",
            "issue",
            "create",
            "--title",
            title,
            "--label",
            f"phase-issue,phase-{n},not-scaffolded,plan:{SLUG}",
            "--body-file",
            str(body_file),
        ]
        result = run(cmd)
        url = result.stdout.strip()
        issue_num = int(url.rsplit("/", 1)[-1])
        print(f"Phase {n} skeleton -> #{issue_num}")
        issue_map["phases"][str(n)]["issue_number"] = issue_num

    issue_map["plan_overview_issue"] = PLAN_OVERVIEW_ISSUE
    MAP.write_text(json.dumps(issue_map, indent=2) + "\n")

    # Also stamp every task JSON with the right phase_issue
    for n in range(1, 8):
        phase_issue = issue_map["phases"][str(n)]["issue_number"]
        for jp in sorted(json_dir.glob(f"P{n}-*.json")):
            d = json.loads(jp.read_text())
            d["github_issue"]["phase_issue"] = phase_issue
            jp.write_text(json.dumps(d, indent=4) + "\n")

    # Patch the plan overview body with real numbers
    body = run(
        ["gh", "issue", "view", str(PLAN_OVERVIEW_ISSUE), "--json", "body", "-q", ".body"]
    ).stdout
    for n in range(1, 8):
        body = body.replace(
            f"#<phase_{n}_issue>",
            f"#{issue_map['phases'][str(n)]['issue_number']}",
        )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(body)
        path = f.name
    run(["gh", "issue", "edit", str(PLAN_OVERVIEW_ISSUE), "--body-file", path])
    print(f"updated plan overview #{PLAN_OVERVIEW_ISSUE}")


if __name__ == "__main__":
    main()
