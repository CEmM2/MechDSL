"""Recursive Plan-2-Tasks: decompose dev/plans/recovery_plan_latex_contract.md.

Walks the seven action-item tables (already canonical-shaped after Phase 1 of
back2latex), and emits:
  - dev/tasks/recovery_plan_latex_contract/all-tasks.md
  - dev/tasks/recovery_plan_latex_contract/json/<task_id>.json (one per row)
  - dev/tasks/recovery_plan_latex_contract/Phase_<N>_context_summary.md (1..7)
  - dev/tasks/recovery_plan_latex_contract/github_issue_map.json (skeleton)
  - dev/tasks/recovery_plan_latex_contract/gates/  (empty folder)
  - dev/tracking/tasks-tracker_recovery_plan_latex_contract.md

Does NOT invoke gh — that's the responsibility of the calling agent (which
will then create labels, plan-overview issue, and 7 phase-skeleton issues).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "dev" / "plans" / "recovery_plan_latex_contract.md"
TASKS_DIR = ROOT / "dev" / "tasks" / "recovery_plan_latex_contract"
TRACKER_PATH = ROOT / "dev" / "tracking" / "tasks-tracker_recovery_plan_latex_contract.md"
SLUG = "recovery-plan-latex-contract"
PLAN_REL = "dev/plans/recovery_plan_latex_contract.md"
REPO = "SOSOVSKI/MechDSL"

PHASE_NAMES = {
    1: "Freeze the contract surface (R0)",
    2: "Restore the frontend as the canonical entry point (R1)",
    3: "Enrich `ProblemIR` into the semantic center again (R2)",
    4: "Enrich `ElementIR` and normalize lowering boundaries (R3)",
    5: "Re-anchor Taichi codegen as the stable path (R4)",
    6: "Integrate `algo2code` at the least risky seam (R5)",
    7: "Verification, governance, and closure (R6)",
}


def parse_plan() -> dict:
    text = PLAN_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Walk phase by phase, extracting action-item rows and the surrounding
    # Code reality anchor + Cross-phase dependencies prose.
    phase_starts: dict[int, int] = {}
    for i, line in enumerate(lines):
        m = re.match(r"^## Phase (\d+) — ", line)
        if m:
            phase_starts[int(m.group(1))] = i

    phases: dict[int, dict] = {}
    for n, start in phase_starts.items():
        next_start = min((s for k, s in phase_starts.items() if k > n), default=len(lines))
        section = lines[start:next_start]
        phases[n] = parse_phase_section(n, section)

    # Risks attribution
    risks_section_match = re.search(
        r"^## Risks and mitigations\b.*?(?=^## )", text, flags=re.MULTILINE | re.DOTALL
    )
    risk_attribution: dict[str, list[str]] = defaultdict(list)
    risk_text_for: dict[str, list[tuple[str, str]]] = defaultdict(list)
    if risks_section_match:
        for row in risks_section_match.group(0).splitlines():
            if not row.startswith("|") or row.startswith("|---") or "Affects task" in row:
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) < 4:
                continue
            risk, _why, mit, affects = cells[:4]
            for tok in (t.strip() for t in affects.split(",") if t.strip()):
                if re.fullmatch(r"P[1-7]-[0-9]+", tok):
                    risk_text_for[tok].append((risk, mit))

    return {"phases": phases, "risk_text_for": risk_text_for}


def parse_phase_section(phase_int: int, lines: list[str]) -> dict:
    """Extract action-item rows + anchor + cross-phase deps for a single phase."""
    text = "\n".join(lines)

    # Code reality anchor block
    anchor_match = re.search(
        r"^### Code reality anchor \(2026-04-26\)\s*\n(?P<body>.*?)(?=^###? )",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    anchor = anchor_match.group("body").strip() if anchor_match else ""

    # Cross-phase dependencies block
    deps_match = re.search(
        r"^### Cross-phase dependencies\s*\n(?P<body>.*?)(?=^###? |^---|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    deps_block = deps_match.group("body").strip() if deps_match else ""

    # Required constraints block (when present)
    constraints_match = re.search(
        r"^### Required constraints\s*\n(?P<body>.*?)(?=^###? )",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    constraints = constraints_match.group("body").strip() if constraints_match else ""

    # Exit criteria
    exit_match = re.search(
        r"^### Exit criteria\s*\n(?P<body>.*?)(?=^---|^## )",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    exit_criteria = exit_match.group("body").strip() if exit_match else ""

    # Why <…> line
    why_match = re.search(r"^\*\*Why .+?\*\* (.+?)$", text, flags=re.MULTILINE)
    why = why_match.group(1).strip() if why_match else ""

    # Goal
    goal_match = re.search(r"^\*\*Goal:\*\* (.+?)$", text, flags=re.MULTILINE)
    goal = goal_match.group(1).strip() if goal_match else ""

    # Action-item rows
    rows: list[dict] = []
    in_table = False
    for line in lines:
        if line.startswith("| Task ID | Legacy ID | "):
            in_table = True
            continue
        if in_table and line.startswith("|---"):
            continue
        if in_table:
            if not line.startswith("| P"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 7:
                continue
            tid, legacy, action, files_raw, blocked_raw, tier, verif = cells[:7]
            blocked = (
                []
                if blocked_raw in ("", "—")
                else [t.strip() for t in blocked_raw.split(",") if t.strip()]
            )
            rows.append(
                {
                    "task_id": tid,
                    "legacy_id": legacy,
                    "action_item": action,
                    "files_raw": files_raw,
                    "blocked_by": blocked,
                    "tier": tier,
                    "verification": verif,
                }
            )

    return {
        "phase": phase_int,
        "name": PHASE_NAMES[phase_int],
        "goal": goal,
        "why": why,
        "anchor": anchor,
        "deps_block": deps_block,
        "constraints": constraints,
        "exit_criteria": exit_criteria,
        "rows": rows,
    }


def parse_files(files_raw: str) -> list[str]:
    """Split a `Files / surfaces` cell into a deliverable-list approximation."""
    # Strip backticks, drop trailing prose like "(...)", split on commas
    items: list[str] = []
    for chunk in re.split(r",\s*", files_raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        items.append(chunk)
    return items


def task_objective(action: str) -> str:
    return action


def task_scope(action: str, files_raw: str) -> list[str]:
    return [
        action,
        f"Touched surfaces (per recovery plan): {files_raw}",
    ]


def task_deliverables(action: str, files_raw: str) -> list[str]:
    parsed = parse_files(files_raw)
    if not parsed:
        return [f"Implementation satisfying: {action}"]
    return [f"Changes to {p}" for p in parsed]


def task_implementation_steps(row: dict, phase: dict) -> list[str]:
    """Generic 4-step skeleton derived from action + verification."""
    return [
        f"Read the recovery plan section for Phase {phase['phase']} ({phase['name']}) and the task's row in the action-item table to scope the change.",
        f"Apply the action: {row['action_item']}",
        f"Touch only the listed surfaces: {row['files_raw']}.",
        f"Verify: {row['verification']}",
        "Update the task JSON status to done after Gate C passes.",
    ]


def task_acceptance(row: dict) -> list[str]:
    return [
        row["verification"],
        f"All deliverables for {row['task_id']} are in place at the surfaces listed.",
        "No regressions on the existing test suite.",
    ]


def task_test_cases(row: dict) -> list[str]:
    return [
        f"{row['task_id']}-c1: " + row["verification"],
        f"{row['task_id']}-c2: deliverables present at the listed surfaces",
    ]


def task_risks(tid: str, risk_text_for: dict[str, list[tuple[str, str]]]) -> list[str]:
    if tid not in risk_text_for:
        return ["No specific risk attributed in the plan; standard care applies."]
    return [f"{r}. Mitigation: {m}" for r, m in risk_text_for[tid]]


def task_plan_lines(phase: dict, row: dict) -> list[str]:
    """Approximate plan_lines using the phase heading position; precise enough."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    legacy = row["legacy_id"]
    legacy_match = re.search(rf"\| {legacy} \|", text)
    if legacy_match:
        # 1-based line number
        line_no = text[: legacy_match.start()].count("\n") + 1
        return [str(line_no), str(line_no)]
    return ["1", "1"]


def emit_task_json(
    row: dict,
    phase: dict,
    risk_text_for: dict[str, list[tuple[str, str]]],
    out_dir: Path,
) -> None:
    tid = row["task_id"]
    plan_lines = task_plan_lines(phase, row)
    data = {
        "task_id": tid,
        "title": row["action_item"][:120],
        "phase": str(phase["phase"]),
        "objective": task_objective(row["action_item"]),
        "plan_file": PLAN_REL,
        "plan_lines": plan_lines,
        "plan_assets": [
            {
                "asset_description": (
                    f"Action-item row {tid} ({row['legacy_id']}) in Phase {phase['phase']} table"
                ),
                "asset_type": "table",
                "Plan_file_start_line": int(plan_lines[0]),
                "Plan_file_end_line": int(plan_lines[1]),
            }
        ],
        "blocked_by": row["blocked_by"],
        "blocks": [],  # filled in second pass
        "scope": task_scope(row["action_item"], row["files_raw"]),
        "implementation_steps": task_implementation_steps(row, phase),
        "deliverables": task_deliverables(row["action_item"], row["files_raw"]),
        "acceptance_criteria": task_acceptance(row),
        "verification_commands": [""],
        "test_plan": {
            "tier": row["tier"],
            "cases": task_test_cases(row),
        },
        "test_artifacts": [""],
        "risks": task_risks(tid, risk_text_for),
        "status": "pending",
        "completion_date": "",
        "test_completion": {
            "passed": 0,
            "total": 0,
            "pass_rate": 0,
            "commands": [{"command": "", "passed": 0, "total": 0}],
        },
        "review_score": 0,
        "review_breakdown": {"minor": 0, "medium": 0, "high": 0, "critical": 0},
        "review_status": "",
        "implementation_branch": "",
        "completion_notes": [""],
        "github_issue": {
            "phase_issue": None,
            "task_issue": None,
            "repo": REPO,
        },
    }
    (out_dir / f"{tid}.json").write_text(json.dumps(data, indent=4) + "\n")


def write_all_tasks_md(phases: dict, blocks_map: dict[str, list[str]], out_path: Path) -> None:
    lines = [
        "# All Tasks — recovery_plan_latex_contract",
        "",
        "Plan source: `dev/plans/recovery_plan_latex_contract.md`",
        "Tracker: `dev/tracking/tasks-tracker_recovery_plan_latex_contract.md`",
        "",
        "Decomposed by `/Aut_Faciam tasks` (recursive invocation from back2latex P2-2). "
        "Phase IDs and Task IDs were already canonical in the recovery plan after the "
        "Phase-1 amendments of back2latex; this decomposition copies them verbatim.",
        "",
        "| Task ID | Phase | Title | Blocked by (immediate) | Blocks (immediate) | Derived from plan lines |",
        "|---|---|---|---|---|---|",
    ]
    for n in sorted(phases):
        for row in phases[n]["rows"]:
            tid = row["task_id"]
            blocked = ", ".join(row["blocked_by"]) if row["blocked_by"] else "—"
            blocks = ", ".join(blocks_map.get(tid, [])) or "—"
            plan_line = task_plan_lines(phases[n], row)[0]
            lines.append(
                f"| {tid} | {n} | {row['action_item'][:80]} | {blocked} | {blocks} | {plan_line} |"
            )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Cross-phase blockers were authored in the recovery plan during back2latex "
        "Phase 1 (P1-3 + P1-5) and are reproduced verbatim here."
    )
    lines.append("- Within-phase dependency edges are taken from each table's `Blocked by` column.")
    out_path.write_text("\n".join(lines) + "\n")


def write_context_summary(phase: dict, out_dir: Path) -> None:
    n = phase["phase"]
    body = [
        f"# Phase {n} Context Summary: {phase['name']}",
        "",
        f"**Plan:** `{PLAN_REL}`",
        f"**Original plan phase name:** {phase['name']}",
        "",
        "## Goal",
        phase["goal"] or "(see plan section)",
        "",
        "## Why this phase",
        phase["why"] or "(see plan section)",
        "",
        "## Code reality anchor (2026-04-26)",
        phase["anchor"] or "(see plan section)",
        "",
        "## Required constraints",
        phase["constraints"] or "(none documented separately)",
        "",
        "## Cross-phase dependencies",
        phase["deps_block"] or "(none documented)",
        "",
        "## Exit criteria",
        phase["exit_criteria"] or "(see plan section)",
        "",
        "## Tasks in this phase",
    ]
    for row in phase["rows"]:
        body.append(
            f"- **{row['task_id']}** ({row['legacy_id']}, tier={row['tier']}): {row['action_item']}"
        )
    out_dir.joinpath(f"Phase_{n}_context_summary.md").write_text("\n".join(body) + "\n")


def write_tracker(phases: dict, blocks_map: dict[str, list[str]], out_path: Path) -> None:
    lines = [
        "# Development Task Tracker — recovery_plan_latex_contract",
        "",
        "Generated on: 2026-04-26 by /Aut_Faciam tasks (recursive invocation from back2latex P2-2).",
        "",
        "## recovery_plan_latex_contract Tracker",
        "",
        "Plan source: `dev/plans/recovery_plan_latex_contract.md`",
        "Task index: `dev/tasks/recovery_plan_latex_contract/all-tasks.md`",
        "",
        "| Task ID | Title | Status | Owner | Blocked by (open) | Blocks | Plan lines | PR/Commit | Verified by | Completed on |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for n in sorted(phases):
        for row in phases[n]["rows"]:
            tid = row["task_id"]
            blocked = ", ".join(row["blocked_by"]) if row["blocked_by"] else "—"
            blocks = ", ".join(blocks_map.get(tid, [])) or "—"
            plan_line = task_plan_lines(phases[n], row)[0]
            lines.append(
                f"| {tid} | {row['action_item'][:60]} | pending |  | {blocked} | {blocks} | {plan_line} |  |  |  |"
            )
    lines.extend(
        [
            "",
            "## Update protocol",
            "",
            "1. When a task starts, set `Status` to `in_progress`, assign `Owner`, and keep unresolved blockers in `Blocked by (open)`.",
            "2. When a task is done, set `Status` to `done`, fill `PR/Commit`, `Verified by`, and `Completed on` (YYYY-MM-DD).",
            "3. For each newly completed task, remove its ID from downstream rows in `Blocked by (open)` when applicable.",
            "",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parsed = parse_plan()
    phases = parsed["phases"]
    risk_text_for = parsed["risk_text_for"]

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / "json").mkdir(exist_ok=True)
    (TASKS_DIR / "gates").mkdir(exist_ok=True)

    # Build blocks_map (inverse of blocked_by)
    blocks_map: dict[str, list[str]] = defaultdict(list)
    for n in phases:
        for row in phases[n]["rows"]:
            for blocker in row["blocked_by"]:
                blocks_map[blocker].append(row["task_id"])

    # Emit task JSONs
    total_tasks = 0
    for n in sorted(phases):
        for row in phases[n]["rows"]:
            emit_task_json(row, phases[n], risk_text_for, TASKS_DIR / "json")
            # patch blocks
            tid = row["task_id"]
            jpath = TASKS_DIR / "json" / f"{tid}.json"
            d = json.loads(jpath.read_text())
            d["blocks"] = blocks_map.get(tid, [])
            jpath.write_text(json.dumps(d, indent=4) + "\n")
            total_tasks += 1

    write_all_tasks_md(phases, blocks_map, TASKS_DIR / "all-tasks.md")
    for n in sorted(phases):
        write_context_summary(phases[n], TASKS_DIR)
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_tracker(phases, blocks_map, TRACKER_PATH)

    # Skeleton GH issue map (gh calls happen in the calling script)
    gh_map = {
        "plan_file": PLAN_REL,
        "plan_slug": SLUG,
        "plan_overview_issue": None,
        "phases": {str(n): {"issue_number": None, "task_issues": {}} for n in sorted(phases)},
        "repo": REPO,
    }
    (TASKS_DIR / "github_issue_map.json").write_text(json.dumps(gh_map, indent=2) + "\n")

    print(f"emitted {total_tasks} task JSONs across {len(phases)} phases")
    for n in sorted(phases):
        print(f"  Phase {n}: {len(phases[n]['rows'])} tasks")


if __name__ == "__main__":
    main()
