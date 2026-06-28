"""Task P7-5: Archive or annotate superseded sprint/task documents.

Phase 7 (R6.5) — docs-tier acceptance: superseded sprint/plan/tracker
artifacts must be obviously historical so that no future contributor
mistakes them for the active execution source. Builds on P1-6 (which
already added superseded banners to ``MVP_plan.md`` and
``MVP_sprint{1,2,3}.md``) and extends the same treatment to any other
plans, task folders, and trackers that are no longer authoritative.

Tier: docs

Acceptance criteria:
  1. P7-5-c1: No historical plan appears to be the active execution
     source by accident — every superseded artifact carries a banner or
     directory marker pointing to the recovery plan as the active source.
  2. P7-5-c2: Deliverables present at the listed surfaces (``dev/plans/``,
     ``dev/tasks/``, ``dev/tracking/``).
  3. No regressions on the existing test suite.

Blocked by: P5-1 (the stable Taichi-only contract must already be the
active story before older sprint plans can be safely archived).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repository root: this file lives at
# packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_5.py
# so .parents[5] is the workspace root.
REPO_ROOT = Path(__file__).resolve().parents[5]
PLANS_DIR = REPO_ROOT / "dev" / "plans"
TASKS_DIR = REPO_ROOT / "dev" / "tasks"
TRACKING_DIR = REPO_ROOT / "dev" / "tracking"

# Active execution sources: completed recovery foundations plus the current
# successor plans that explicitly continue after them. ``constitutive_latex``
# is the current active plan (the LaTeX-derived constitutive pipeline — Phase 3
# is merged on main, Phase 4 (Mooney-Rivlin + Ogden) is pending), so it is
# authoritative, not superseded. ``akms_executable_bridge`` is the active
# coupling plan (MechDSL as the AKMS-Learn executable_bridge — Phase 1 / Tier-1
# integration surface is implemented; Phases 2-3 execute in the AKMS and
# Logic-Loom repos), so it is authoritative, not superseded.
# ``issue307`` is the active algo2code parser/codegen fix plan (issue #307);
# workstreams W1–W6 are implemented in this PR (fail-loud foundation, SSA vector
# lowering, transpose alias, PCG parity gate, deferral tests, and inclusive
# for-loop lowering), so the plan remains authoritative pending merge/close, not
# superseded.
# ``PlanJune14`` is the active SVK/J2 all-Taichi-seam plan; ``pj14_fix`` (its
# Codex-remediation child) and ``pj316_resolution`` (the active plan resolving
# the PR #316 review findings) continue it, so all three are authoritative, not
# superseded — allowlisted rather than bannered (the "still active" model).
ACTIVE_PLAN_STEMS = {
    "recovery_plan_latex_contract",
    "fgram",
    "constitutive_latex",
    "akms_executable_bridge",
    "issue307",
    "PlanJune14",
    "pj14_fix",
    "pj316_resolution",
    # ``PlanJune14_closure`` is the active closure record for PlanJune14 (PJ-7
    # governance) — an authoritative governance artifact, not a superseded plan.
    "PlanJune14_closure",
    # ``june16`` is an active backlog/roadmap planning note (2026-06-16), not a
    # superseded plan.
    "june16",
}
ACTIVE_TASK_DIRS = {
    "recovery_plan_latex_contract",
    "post_recovery_plan",
    "fgram",
    "constitutive_latex",
    "akms_executable_bridge",
    # PlanJune14 is active (see ACTIVE_PLAN_STEMS) -> its task folder is too.
    "PlanJune14",
}
ACTIVE_TRACKER_STEMS = {
    "tasks-tracker_recovery_plan_latex_contract",
    "tasks-tracker_post_recovery_plan",
    "tasks-tracker_fgram",
    "tasks-tracker_constitutive_latex",
    "tasks-tracker_akms_executable_bridge",
    # PlanJune14 is active (see ACTIVE_PLAN_STEMS) -> its tracker is too.
    "tasks-tracker_PlanJune14",
}

# Trackers that are conventions / vocabulary, not plan execution sources.
TRACKER_NON_PLAN_STEMS = {"STATUS_LEGEND", "verification_matrix"}

# A "superseded" marker is any case-insensitive occurrence of the literal
# substring ``superseded``. P1-6 established this convention via the
# ``> ⚠️ **Superseded ...`` banner on ``MVP_plan.md`` and
# ``MVP_sprint{1,2,3}.md``; P7-5 extends it across the rest of dev/.
SUPERSEDED_MARKER = "superseded"


def _has_superseded_marker(text: str) -> bool:
    return SUPERSEDED_MARKER in text.lower()


class TestP7_5:
    """Tests for Task P7-5: superseded artifacts marked historical."""

    @pytest.mark.docs
    def test_no_historical_plan_appears_active_by_accident(self) -> None:
        """P7-5-c1: No historical plan appears to be the active source.

        Every top-level ``.md`` file under ``dev/plans/`` other than the
        canonical-active set must carry a ``superseded`` marker pointing
        at the recovery plan as the active execution source.
        """
        assert PLANS_DIR.is_dir(), f"missing {PLANS_DIR}"

        plan_files = sorted(p for p in PLANS_DIR.iterdir() if p.is_file() and p.suffix == ".md")
        assert plan_files, f"no plan files found under {PLANS_DIR}"

        offenders: list[str] = []
        for plan in plan_files:
            if plan.stem in ACTIVE_PLAN_STEMS:
                continue
            text = plan.read_text(encoding="utf-8")
            if not _has_superseded_marker(text):
                offenders.append(str(plan.relative_to(REPO_ROOT)))

        assert not offenders, (
            "Plan files lack a 'superseded' banner pointing at the recovery plan "
            "(the active execution source); either banner them or add to the "
            f"ACTIVE_PLAN_STEMS allowlist with justification: {offenders}"
        )

    @pytest.mark.docs
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-5-c2: Deliverables present at the listed surfaces.

        Every non-recovery task folder under ``dev/tasks/`` must contain a
        ``_SUPERSEDED.md`` marker, and every non-recovery tracker file
        under ``dev/tracking/`` must carry a ``superseded`` banner. The
        recovery plan's task folder and tracker remain banner-free.
        """
        assert TASKS_DIR.is_dir(), f"missing {TASKS_DIR}"
        assert TRACKING_DIR.is_dir(), f"missing {TRACKING_DIR}"

        # --- dev/tasks/ ---
        task_dirs = sorted(d for d in TASKS_DIR.iterdir() if d.is_dir())
        assert task_dirs, f"no task folders found under {TASKS_DIR}"

        task_offenders: list[str] = []
        for tdir in task_dirs:
            if tdir.name in ACTIVE_TASK_DIRS:
                continue
            marker = tdir / "_SUPERSEDED.md"
            if not marker.is_file():
                task_offenders.append(str(tdir.relative_to(REPO_ROOT)))
                continue
            if not _has_superseded_marker(marker.read_text(encoding="utf-8")):
                task_offenders.append(str(marker.relative_to(REPO_ROOT)))

        assert not task_offenders, (
            "Task folders lack a `_SUPERSEDED.md` marker pointing at the "
            f"recovery plan: {task_offenders}"
        )

        # --- dev/tracking/ ---
        tracker_files = sorted(
            p
            for p in TRACKING_DIR.iterdir()
            if p.is_file() and p.suffix == ".md" and p.stem.startswith("tasks-tracker_")
        )
        assert tracker_files, f"no tracker files found under {TRACKING_DIR}"

        tracker_offenders: list[str] = []
        for tracker in tracker_files:
            if tracker.stem in ACTIVE_TRACKER_STEMS:
                continue
            if tracker.stem in TRACKER_NON_PLAN_STEMS:
                continue
            text = tracker.read_text(encoding="utf-8")
            if not _has_superseded_marker(text):
                tracker_offenders.append(str(tracker.relative_to(REPO_ROOT)))

        assert not tracker_offenders, (
            "Tracker files lack a 'superseded' banner pointing at the "
            f"recovery plan: {tracker_offenders}"
        )

        # --- positive checks: the active set must not carry the marker
        # at the top of file (the recovery plan / its tracker / its tasks
        # folder must read as authoritative). ---
        active_plan = PLANS_DIR / "recovery_plan_latex_contract.md"
        active_tracker = TRACKING_DIR / "tasks-tracker_recovery_plan_latex_contract.md"
        active_task_dir = TASKS_DIR / "recovery_plan_latex_contract"

        assert active_plan.is_file(), f"active plan missing: {active_plan}"
        assert active_tracker.is_file(), f"active tracker missing: {active_tracker}"
        assert active_task_dir.is_dir(), f"active task folder missing: {active_task_dir}"

        # The active task folder must NOT have a _SUPERSEDED.md.
        assert not (active_task_dir / "_SUPERSEDED.md").exists(), (
            f"active task folder must not be marked superseded: {active_task_dir}"
        )

        # The active plan's first line / first 500 chars must not look superseded.
        active_plan_head = active_plan.read_text(encoding="utf-8")[:500]
        assert not _has_superseded_marker(active_plan_head), (
            "Active recovery plan unexpectedly carries a 'superseded' marker in its header."
        )
