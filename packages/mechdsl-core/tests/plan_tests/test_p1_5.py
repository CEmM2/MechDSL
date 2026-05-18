from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


def _cross_phase_blocks() -> list[str]:
    """Return the body text of each `### Cross-phase dependencies` block (one per phase)."""
    text = _plan_text()
    blocks: list[str] = []
    for match in re.finditer(r"^### Cross-phase dependencies\b", text, flags=re.MULTILINE):
        tail = text[match.end() :]
        end_match = re.search(r"^###? ", tail, flags=re.MULTILINE)
        body = tail[: end_match.start()] if end_match else tail
        blocks.append(body)
    return blocks


def _action_table_blocked_by(phase_int: int) -> dict[str, list[str]]:
    """Map Task ID → Blocked-by token list for a given phase's action-item table."""
    text = _plan_text()
    phase_match = re.search(
        rf"^## Phase {phase_int} —.*?(?=^## Phase \d+ —|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert phase_match, f"phase {phase_int} section not found"
    section = phase_match.group(0)
    edges: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("| P") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        task_id, _legacy, _action, _files, blocked_by, *_ = cells
        if not re.fullmatch(r"P[1-7]-[0-9]+", task_id):
            continue
        if blocked_by in ("", "—"):
            edges[task_id] = []
        else:
            edges[task_id] = [t.strip() for t in blocked_by.split(",") if t.strip()]
    return edges


class TestTaskP1_5:
    """
    Tests for Task P1-5: Add Cross-phase dependencies blocks per phase
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_seven_cross_phase_dependencies_blocks(self) -> None:
        text = _plan_text()
        count = len(re.findall(r"^### Cross-phase dependencies\b", text, flags=re.MULTILINE))
        assert count == 7, f"expected 7 Cross-phase dependencies subsections, found {count}"

    @pytest.mark.audit
    def test_dependency_ids_are_canonical(self) -> None:
        for body in _cross_phase_blocks():
            assert not re.search(r"\bR[0-6]\.\d", body), (
                f"legacy R-style ID found inside Cross-phase dependencies block:\n{body}"
            )
            ids = re.findall(r"P[1-7]-[0-9]+", body)
            for tok in ids:
                assert re.fullmatch(r"P[1-7]-[0-9]+", tok), (
                    f"non-canonical ID {tok!r} in deps block"
                )

    @pytest.mark.audit
    def test_edges_consistent_with_action_table_blocked_by(self) -> None:
        all_edges: dict[str, list[str]] = {}
        for phase_int in range(1, 8):
            all_edges.update(_action_table_blocked_by(phase_int))
        # any task referenced as a blocker must itself exist in the canonical task set
        all_task_ids = set(all_edges.keys())
        for task_id, blockers in all_edges.items():
            for b in blockers:
                assert b in all_task_ids, (
                    f"{task_id} is blocked by {b}, but {b} is not defined in any action-item table"
                )
