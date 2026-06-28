"""Tests for Task P7-2 (PlanJune14 Phase 7) — governance allowlist + STATUS_LEGEND.

**Governance phase** (plan lines 138–143, "governance (no re-drift)"). Allowlist the
new generated/runtime modules in the anti-drift governance test (test_p7_5.py) so they
don't trip the anti-drift guard; add the PlanJune14 STATUS_LEGEND vocabulary so the
tracker vocabulary matches the legend.

Acceptance criteria covered:
  AC-1  test_p7_5 / test_p7_6 green with the new modules allowlisted.
        → **COVERED by existing governance guard**: recovery_plan_latex_contract/test_p7_5.py
            (lines ~55–82: ti_runtime, generated solver/operator modules already
            allowlisted in ACTIVE_PLAN_STEMS / ACTIVE_TASK_DIRS / ACTIVE_TRACKER_STEMS).
            DO NOT create a stub for AC-1; the standing guard is active.
  AC-2  STATUS_LEGEND includes PlanJune14 vocabulary (pending, etc.).
        → **MISSING**. dev/tracking/STATUS_LEGEND.md currently lists only recovery-era
            values (not_started, in_progress, done, deferred, implemented-via-substitute);
            no test asserts the legend includes PlanJune14 vocab. Stub case below.
"""

import re
from pathlib import Path

import pytest

# Repo root: this file is packages/mechdsl-core/tests/plan_tests/test_p7_2.py
# .parents[0] = plan_tests/
# .parents[1] = tests/
# .parents[2] = mechdsl-core/
# .parents[3] = packages/
# .parents[4] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]

_STATUS_LEGEND = _REPO_ROOT / "dev" / "tracking" / "STATUS_LEGEND.md"
_PLANJUNE14_TRACKER = _REPO_ROOT / "dev" / "tracking" / "tasks-tracker_PlanJune14.md"

# Status values the PlanJune14 tracker rows actually use (derived empirically from
# the tracker table — excludes values that appear only in prose/protocol sections).
# Assertion (b) below uses this as a belt-and-suspenders pin on the known vocab;
# assertion (c) is the authoritative drift guard that dynamically checks every value
# the tracker actually uses against the legend, so the two cannot silently diverge.
_PLANJUNE14_STATUS_VALUES = {"pending", "done"}


def _extract_legend_values(legend_text: str) -> set[str]:
    """Extract all backtick-quoted status values from the legend markdown.

    Matches lines of the form ``| `value` | ... |`` in the legend tables.
    """
    return set(re.findall(r"`([a-z_-]+)`", legend_text))


def _extract_tracker_row_statuses(tracker_text: str) -> set[str]:
    """Extract status-column values from the main tracker table rows.

    The main task table has 10 columns:
      Task ID | Title | Status | Owner | Blocked by (open) | Blocks |
      Plan lines | PR/Commit | Verified by | Completed on

    Only considers rows that start with ``| P`` (task data rows with at least
    10 pipe-delimited columns), skipping the secondary 3-column phase→test-file
    mapping tables that also start with ``| P``.

    A valid status token matches ``^[a-z][a-z_-]*$`` (lowercase, no slashes,
    no backticks, no path separators).
    """
    # Matches plain lowercase identifiers like done, pending, in_progress, deferred
    _status_re = re.compile(r"^[a-z][a-z_-]*$")
    statuses: set[str] = set()
    for line in tracker_text.splitlines():
        # Task data rows look like: | P0-1 | Title | done | ...
        if not line.startswith("| P"):
            continue
        cols = [c.strip() for c in line.split("|")]
        # cols[0] == '', cols[1] == task_id, cols[2] == title, cols[3] == status
        # The main table has ≥11 entries (including leading/trailing empty strings).
        # Secondary tables (Task ID | Title | Test file) have only 5.
        if len(cols) < 11:
            continue
        candidate = cols[3]
        if candidate and _status_re.match(candidate):
            statuses.add(candidate)
    return statuses


class TestTaskP7_2:
    """Tests for Task P7-2: governance allowlist + STATUS_LEGEND vocab.

    Case 1 (AC-1: test_p7_5 green with ti_runtime allowlisted) is covered by the
    standing anti-drift governance guard at recovery_plan_latex_contract/test_p7_5.py
    — ti_runtime and generated modules are already allowlisted (lines ~55–82).

    Case 2 (AC-2: STATUS_LEGEND parses and includes PlanJune14 vocab) is implemented
    below.
    """

    @pytest.mark.docs
    def test_status_legend_includes_planjune14_vocab(self):
        """AC-2: dev/tracking/STATUS_LEGEND.md parses and includes the PlanJune14
        status vocabulary (e.g., 'pending').

        PlanJune14 task tracker uses status values (pending, etc.) that must be
        documented in the canonical STATUS_LEGEND.md. This test verifies:
          (a) The legend file exists and is parseable.
          (b) Every status value the PlanJune14 tracker actually uses in its task rows
              is documented in the legend.
          (c) The tracker task rows reference only legend-defined status values.
        """
        # (a) Legend file exists and is non-empty.
        assert _STATUS_LEGEND.exists(), (
            f"STATUS_LEGEND not found at {_STATUS_LEGEND}. "
            "Create dev/tracking/STATUS_LEGEND.md with the canonical vocab."
        )
        legend_text = _STATUS_LEGEND.read_text(encoding="utf-8")
        assert legend_text.strip(), "STATUS_LEGEND.md is empty."

        # (b) Every value the PlanJune14 tracker uses must appear in the legend.
        legend_values = _extract_legend_values(legend_text)
        missing = _PLANJUNE14_STATUS_VALUES - legend_values
        assert not missing, (
            f"STATUS_LEGEND is missing PlanJune14 vocab: {sorted(missing)}. "
            f"Legend currently documents: {sorted(legend_values)}"
        )

        # (c) Tracker rows must only reference legend-documented values.
        assert _PLANJUNE14_TRACKER.exists(), (
            f"PlanJune14 tracker not found at {_PLANJUNE14_TRACKER}."
        )
        tracker_text = _PLANJUNE14_TRACKER.read_text(encoding="utf-8")
        actual_row_statuses = _extract_tracker_row_statuses(tracker_text)
        undocumented = actual_row_statuses - legend_values
        assert not undocumented, (
            f"Tracker rows use status values not in STATUS_LEGEND: "
            f"{sorted(undocumented)}. "
            f"Add them to dev/tracking/STATUS_LEGEND.md."
        )
