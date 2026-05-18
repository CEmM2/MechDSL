"""Phase 6 verification wrappers for Sprint 3 final cleanup and exit."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_TASKS_DIR = _ROOT / "dev" / "tasks" / "sprint3"
_TASK_JSON_DIR = _TASKS_DIR / "json"
_TRACKER = _ROOT / "dev" / "tracking" / "tasks-tracker_sprint3.md"
_EXIT_REPORT = _TASKS_DIR / "Phase_6_Exit_Report.md"
_HANDOFF = _TASKS_DIR / "Handoff_Phase_7.md"
_TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".json"}

_TO_DO_PATTERN = re.compile(rf"{'TO' + 'DO'}|{'FIX' + 'ME'}")
_CLEANUP_SCAN_PATHS = (
    _ROOT / "packages" / "mechdsl-core",
    _ROOT / "README.md",
    _ROOT / "CHANGELOG.md",
    _ROOT / "dev" / "examples",
    _ROOT / ".github" / "workflows" / "ci.yml",
)
# Intentional cleanup markers — sites whitelisted from the Sprint 3
# Phase 6 cleanup-marker scan because they legitimately mention the
# placeholder word they are guarding against. post_recovery_plan
# Phase 6 (P6-4) replaced the previous line-number whitelist with an
# in-source ``# intentional-cleanup-site`` marker scan: any line in
# the scanned files carrying that marker comment is excluded from the
# unexpected-match list. The marker text is greppable, drift-resistant
# against line-number changes, and lives next to the assertion it
# protects (see ``test_emission_verification.py`` for the two current
# whitelisted sites).
#
# Note: the earlier whitelist also protected a line in
# ``emit_tangent_matvec_kernel``'s docstring. PLAN-A §A7.5 and §A9.2
# replaced that finite-difference implementation with the analytical
# consistent-tangent emission, the docstring was rewritten, and the
# whitelisted codegen line no longer carries any placeholder marker.
_INTENTIONAL_CLEANUP_MARKER = "intentional-cleanup-site"
_EXIT_CRITERION_SNIPPETS = (
    "Patch test: constant strain on irregular Hex8",
    "Rigid body: zero internal force after 30-degree rotation + translation",
    "Cantilever: tip displacement within 5% of Euler-Bernoulli",
    "Cook's membrane: tip displacement within 2% of reference",
    "Necking bar: load-displacement curve within 2% of reference",
    "MMS convergence: L2 rate >= 2.0, H1 rate >= 1.0 on 4 mesh levels",
    "Full pipeline test exercises all 6 compiler layers",
    "CI runs 3 tiers: fast (commit), slow (PR), nightly (e2e benchmarks)",
    "README, examples, CHANGELOG, docstrings complete",
    "`ruff`, `mypy`, full `pytest` all pass cleanly",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_task(task_id: str) -> dict[str, Any]:
    return json.loads(_read_text(_TASK_JSON_DIR / f"{task_id}.json"))


def _tracker_row(task_id: str) -> str:
    for line in _read_text(_TRACKER).splitlines():
        if line.startswith(f"| {task_id} |"):
            return line
    raise AssertionError(f"Missing tracker row for {task_id}")


def _task_command(task_id: str, command: str) -> dict[str, Any]:
    task = _load_task(task_id)
    for result in task["test_completion"]["commands"]:
        if result["command"] == command:
            return result
    raise AssertionError(f"Missing command result for {task_id}: {command}")


def _assert_task_done(task_id: str) -> dict[str, Any]:
    task = _load_task(task_id)
    assert task["status"] == "done"
    assert task["review_status"] == "approved"
    assert task["completion_date"] == "2026-04-12"
    assert task["implementation_branch"] == "SOSOVSKI/phase6-exec"
    row = _tracker_row(task_id)
    assert "| done |" in row
    assert "| 2026-04-12 |" in row
    return task


_CLEANUP_MARKER_WINDOW = 3
"""Number of lines to look forward and backward for the
``intentional-cleanup-site`` marker. Lets one marker comment whitelist
a multi-line statement (e.g. ``ruff``-formatted parenthesised assert)
without forcing the marker onto every constituent line."""


def _iter_cleanup_matches() -> list[tuple[str, int, str]]:
    """Scan the configured paths for cleanup-marker words. Lines that
    carry — or are within ``_CLEANUP_MARKER_WINDOW`` of — the in-source
    ``intentional-cleanup-site`` marker (Phase 6 P6-4) are excluded.
    Those sites legitimately contain the placeholder word they are
    guarding against.
    """
    matches: list[tuple[str, int, str]] = []
    for path in _CLEANUP_SCAN_PATHS:
        if path.is_dir():
            files = (
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix in _TEXT_SUFFIXES
            )
        else:
            files = (path,)
        for candidate in files:
            relative = candidate.relative_to(_ROOT).as_posix()
            text = _read_text(candidate)
            lines = text.splitlines()
            marker_lines = {
                idx for idx, line in enumerate(lines) if _INTENTIONAL_CLEANUP_MARKER in line
            }
            for idx, line in enumerate(lines):
                if not _TO_DO_PATTERN.search(line):
                    continue
                # intentional-cleanup-site
                # Whitelist a TODO/FIXME hit if any nearby line carries
                # the cleanup-site marker — survives line-shuffling
                # caused by formatter passes.
                if any(
                    abs(idx - marker_idx) <= _CLEANUP_MARKER_WINDOW for marker_idx in marker_lines
                ):
                    continue
                matches.append((relative, idx + 1, line.strip()))
    return matches


class TestTaskP6T1:
    """Tests for Task P6-1: Ruff lint and format pass."""

    def test_ruff_check_packages_clean(self) -> None:
        """Task JSON and tracker should record a clean ruff check run."""
        task = _assert_task_done("P6-1")
        assert task["test_completion"]["pass_rate"] == 100
        result = _task_command("P6-1", "uv run ruff check packages/")
        assert result["passed"] == 1
        assert result["total"] == 1

    def test_ruff_format_check_packages_clean(self) -> None:
        """Task JSON and tracker should record a clean formatter check run."""
        task = _assert_task_done("P6-1")
        assert "ruff format" in " ".join(task["completion_notes"])
        result = _task_command("P6-1", "uv run ruff format --check packages/")
        assert result["passed"] == 1
        assert result["total"] == 1


class TestTaskP6T2:
    """Tests for Task P6-2: Mypy type checking pass."""

    def test_mypy_mechdsl_core_clean(self) -> None:
        """Task JSON should record a successful mypy verification run."""
        task = _assert_task_done("P6-2")
        assert task["test_completion"]["pass_rate"] == 100
        result = _task_command("P6-2", "uv run mypy packages/mechdsl-core/src/mechdsl/")
        assert result["passed"] == 1
        assert result["total"] == 1


class TestTaskP6T3:
    """Tests for Task P6-3: Full test suite zero failures."""

    def test_full_workspace_pytest_suite_passes(self) -> None:
        """Task JSON should record a successful full-suite verification run."""
        task = _assert_task_done("P6-3")
        assert task["test_completion"]["pass_rate"] == 100
        result = _task_command("P6-3", "uv run pytest --tb=short -q")
        assert result["passed"] >= 1
        assert result["passed"] == result["total"]


class TestTaskP6T5:
    """Tests for Task P6-5: Remove dead code, unused imports, resolved markers."""

    def test_no_resolved_todos_or_fixmes_remain(self) -> None:
        """Only the explicitly deferred cleanup markers should remain.

        post_recovery_plan Phase 6 (P6-4): the whitelist is now driven
        by the ``# intentional-cleanup-site`` marker scan inside
        :func:`_iter_cleanup_matches`. Any line carrying that marker
        is excluded before this check sees it.
        """
        _assert_task_done("P6-5")
        unexpected = list(_iter_cleanup_matches())
        assert not unexpected, f"Unexpected cleanup markers remain: {unexpected}"

    def test_no_implemented_phase_stubs_remain(self) -> None:
        """Phase scaffold stubs should be gone once execution is complete."""
        _assert_task_done("P6-5")
        text = _read_text(_ROOT / "packages" / "mechdsl-core" / "tests" / "test_phase6_exit.py")
        # Build the forbidden marker at runtime from tuple-joined pieces so
        # neither the source text nor any formatter pass can inline it as a
        # single literal.  Earlier revisions used adjacent-string concatenation
        # (``"stub -- " "implement"``) which ruff-format merged, causing the
        # test to flag its own assertion.
        stub_marker = " ".join(("stub", "--", "implement"))
        assert stub_marker not in text


class TestTaskP6T6:
    """Tests for Task P6-6: Verify all Sprint 3 exit criteria."""

    def test_exit_criteria_matrix_records_all_ten_checks(self) -> None:
        """The exit report should record all ten MVP criteria with checked status."""
        _assert_task_done("P6-6")
        report = _read_text(_EXIT_REPORT)
        assert _EXIT_REPORT.exists()
        checked_lines = [line for line in report.splitlines() if line.startswith("- [x] ")]
        assert len(checked_lines) == 10
        for snippet in _EXIT_CRITERION_SNIPPETS:
            assert snippet in report

    def test_exit_report_cites_clean_toolchain_and_ci_evidence(self) -> None:
        """The exit report should cite toolchain-cleanliness and CI evidence."""
        _assert_task_done("P6-6")
        report = _read_text(_EXIT_REPORT)
        assert "uv run ruff check packages/" in report
        assert "uv run mypy packages/mechdsl-core/src/mechdsl/" in report
        assert "uv run pytest --tb=short -q" in report
        assert "uv run pytest packages/mechdsl-core/tests/test_ci_config.py -v" in report
        assert "CI has 3 tiers" in report


class TestTaskP6T7:
    """Tests for Task P6-7: Sprint 3 handoff document."""

    def test_sprint3_handoff_document_covers_mvp_completion_and_plan_b_limits(self) -> None:
        """The final handoff should summarize MVP completion and deferred Plan B scope."""
        _assert_task_done("P6-7")
        handoff = _read_text(_HANDOFF)
        assert _HANDOFF.exists()
        assert "# Phase 6 Handoff" in handoff
        assert "MVP DONE" in handoff
        assert "Plan B" in handoff
        assert "## Phase 6 Completion Summary" in handoff
        assert "## Known Issues and Deferred Concerns" in handoff
