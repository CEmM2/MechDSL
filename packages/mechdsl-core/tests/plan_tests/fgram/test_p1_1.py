"""Docs-governance tests for fgram P1-1."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "dev").is_dir():
            return parent
    raise RuntimeError("Repository root not found")


REPO_ROOT = _find_repo_root()
FGRAM_TASKS = REPO_ROOT / "dev" / "tasks" / "fgram"
FGRAM_JSON = FGRAM_TASKS / "json"
FGRAM_INDEX = FGRAM_TASKS / "all-tasks.md"
FGRAM_TRACKER = REPO_ROOT / "dev" / "tracking" / "tasks-tracker_fgram.md"
FGRAM_REVIEW = REPO_ROOT / "dev" / "reviews" / "fgram_recovery_continuation.md"

FOUNDATION_SOURCES = ("recovery_plan_latex_contract", "post_recovery_plan")
EXPECTED_TASKS = {f"P{phase}-1": str(phase) for phase in range(1, 8)}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_design_doc_base_ref() -> str | None:
    """Return a git ref to diff committed design-doc changes against, or ``None``.

    Prefers ``origin/main`` (the ref a CI checkout has after fetching the base)
    and falls back to ``main`` for local runs. Returns ``None`` when neither
    resolves — e.g. a detached or shallow clone with no base ref — so the
    committed-change check degrades to a skip rather than a spurious failure
    (the concern raised in issue #271).
    """
    for ref in ("origin/main", "main"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return ref
    return None


def _load_task(task_id: str) -> dict[str, object]:
    return json.loads((FGRAM_JSON / f"{task_id}.json").read_text(encoding="utf-8"))


class TestFgramP1_1Governance:
    """Tests for Task P1-1: Plan/task governance scaffold."""

    def test_fgram_review_note_marks_recovery_as_continuation(self) -> None:
        """fgram is the next plan, not a replacement for completed recovery work."""
        note = _read(FGRAM_REVIEW)

        assert "fgram" in note
        assert "continues after" in note
        assert "does not replace" in note
        for source in FOUNDATION_SOURCES:
            assert source in note
        assert note.count("foundation reused") >= len(FOUNDATION_SOURCES)

    def test_all_task_json_records_foundation_reuse_notes(self) -> None:
        """Every task carries the reused recovery foundations as notes, not scope."""
        for task_id in EXPECTED_TASKS:
            task = _load_task(task_id)
            notes = task.get("foundation_notes")
            assert isinstance(notes, list), f"{task_id} missing foundation_notes list"
            note_text = "\n".join(str(note) for note in notes)

            for source in FOUNDATION_SOURCES:
                assert source in note_text, f"{task_id} missing {source} foundation note"
            assert note_text.count("foundation reused") >= len(FOUNDATION_SOURCES)

            scope_text = "\n".join(str(item) for item in task.get("scope", []))
            assert "recovery_plan_latex_contract" not in scope_text
            assert "post_recovery_plan" not in scope_text

    def test_task_ids_map_cleanly_to_seven_fgram_phases(self) -> None:
        """The index, tracker, and JSON records expose one task per plan phase."""
        index = _read(FGRAM_INDEX)
        tracker = _read(FGRAM_TRACKER)

        for task_id, phase in EXPECTED_TASKS.items():
            task = _load_task(task_id)
            assert task["task_id"] == task_id
            assert task["phase"] == phase
            assert f"| {task_id} | {phase} |" in index
            assert f"| {task_id} |" in tracker

        assert len(list(FGRAM_JSON.glob("P*-1.json"))) == len(EXPECTED_TASKS)

    def test_no_design_doc_files_changed(self) -> None:
        """The read-only design-doc source of truth must not be modified.

        ``git status --short`` only inspects the working tree, which is always
        clean after a CI checkout — so a PR that *commits* design-doc edits would
        slip past that gate (issue #271). Check both surfaces: uncommitted edits
        in the working tree, and committed edits on this branch relative to the
        base branch (``origin/main``/``main``).
        """
        uncommitted = subprocess.run(
            ["git", "status", "--short", "--", "dev/design_docs"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert uncommitted.stdout == "", (
            f"Uncommitted design-doc changes detected (read-only):\n{uncommitted.stdout}"
        )

        base_ref = _resolve_design_doc_base_ref()
        if base_ref is None:
            pytest.skip("no base ref (origin/main or main) available to diff against")

        # Three-dot ``base...HEAD`` diffs from the merge-base, so it reports only
        # what THIS branch changed since it forked — not design-doc edits that
        # landed on the base branch afterwards.
        committed = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD", "--", "dev/design_docs"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert committed.stdout == "", (
            f"Committed design-doc changes detected vs {base_ref} "
            f"(design docs are read-only in PRs):\n{committed.stdout}"
        )
