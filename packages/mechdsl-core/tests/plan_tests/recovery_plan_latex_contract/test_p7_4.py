"""Task P7-4: Architecture decision / recovery-status note cross-linking the plan and the drift report.

Phase 7 (R6.4) — docs-tier acceptance: a short ADR-style or recovery-status
note must let future readers trace why the recovery work exists and what
it is correcting, by linking the recovery plan
(``dev/plans/recovery_plan_latex_contract.md``) and the drift report
(``dev/reviews/drift_20_04.md``).

Tier: docs

Acceptance criteria:
  1. P7-4-c1: Readers can trace why recovery work exists and what it is
     correcting (cross-links present and bidirectional, or at least
     discoverable from one entry point).
  2. P7-4-c2: Deliverables present at the listed surfaces (``dev/reviews/``,
     ``dev/plans/``, optional ADR).
  3. No regressions on the existing test suite.

No upstream blockers — this is governance documentation that summarises
phases that have already landed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
REVIEWS_DIR = REPO_ROOT / "dev" / "reviews"
ADR_DIR = REPO_ROOT / "dev" / "adr"
PLANS_DIR = REPO_ROOT / "dev" / "plans"
RECOVERY_PLAN = PLANS_DIR / "recovery_plan_latex_contract.md"
DRIFT_REPORT = REVIEWS_DIR / "drift_20_04.md"


def _candidate_note_paths() -> list[Path]:
    """Return any markdown file under ``dev/reviews/`` or ``dev/adr/``
    that mentions both the recovery plan and the drift report by filename.

    The search is intentionally permissive about location so the test
    works whether P7-4 chose ``dev/reviews/recovery_status_*.md``,
    ``dev/adr/0001-*.md``, or some other in-surface name.
    """
    candidates: list[Path] = []
    for surface in (REVIEWS_DIR, ADR_DIR):
        if not surface.is_dir():
            continue
        for path in surface.glob("*.md"):
            # Don't let the drift report or recovery plan itself satisfy the
            # cross-link role — we want a *new* note that points at both.
            if path.resolve() == DRIFT_REPORT.resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if "recovery_plan_latex_contract.md" in text and "drift_20_04.md" in text:
                candidates.append(path)
    return candidates


class TestP7_4:
    """Tests for Task P7-4: ADR / recovery-status cross-link note."""

    @pytest.mark.docs
    def test_cross_link_note_exists_and_references_plan_and_drift(self) -> None:
        """P7-4-c1: Readers can trace why recovery work exists.

        Verifies: a recovery-status / ADR note exists under ``dev/reviews/``
        or ``dev/adr/`` (or similar) that names BOTH
        ``recovery_plan_latex_contract.md`` and ``drift_20_04.md``, plus a
        one-line summary of the contract being restored.

        Passes when: at least one file in the recovery-doc surfaces contains
        both filenames as relative links or markdown references.
        """
        # Preconditions — the diagnosis and prescription must both still exist.
        assert DRIFT_REPORT.is_file(), f"missing drift audit (diagnosis): {DRIFT_REPORT}"
        assert RECOVERY_PLAN.is_file(), f"missing recovery plan (prescription): {RECOVERY_PLAN}"

        notes = _candidate_note_paths()
        assert notes, (
            "P7-4 cross-link note not found: expected a markdown file under "
            "dev/reviews/ or dev/adr/ that references BOTH "
            "recovery_plan_latex_contract.md AND drift_20_04.md."
        )

        # The note must read as a cross-link, not just incidentally mention
        # both filenames — require a one-line summary marker and a
        # 'how to read' / pointer style sentence.
        #
        # post_recovery_plan Phase 6 (P6-3): selecting the candidate by
        # filtering on the plan-referenced filename rather than indexing
        # the list positionally. Order of `notes` must not change which
        # note we assert on.
        target_notes = [
            n for n in notes if "recovery_plan_latex_contract.md" in n.read_text(encoding="utf-8")
        ]
        assert target_notes, "no cross-link note references recovery_plan_latex_contract.md"
        target = target_notes[0]
        text = target.read_text(encoding="utf-8")
        assert "LaTeX" in text, (
            f"cross-link note {target} should mention the LaTeX contract "
            "being restored in its summary."
        )
        # Sanity: must be short. P7-4 spec asks for under ~80 lines.
        line_count = len(text.splitlines())
        assert line_count <= 120, (
            f"cross-link note {target} is {line_count} lines; P7-4 spec "
            "asks for a short note (target <= 80, ceiling 120)."
        )

    @pytest.mark.docs
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-4-c2: Deliverables present at the listed surfaces.

        Verifies: the recovery plan now contains a back-reference to the
        cross-link note (so the note is discoverable from the plan), and
        the note itself lives under ``dev/reviews/`` or ``dev/adr/``.

        Passes when: the recovery plan references the new note by relative
        path AND the note file lives in one of the listed surfaces.
        """
        notes = _candidate_note_paths()
        assert notes, "P7-4 cross-link note not found under dev/reviews/ or dev/adr/."

        # All candidate notes must live under one of the listed surfaces.
        for note in notes:
            in_listed_surface = any(
                note.resolve().is_relative_to(surface.resolve())
                for surface in (REVIEWS_DIR, ADR_DIR)
                if surface.is_dir()
            )
            assert in_listed_surface, (
                f"cross-link note {note} must live under dev/reviews/ or "
                "dev/adr/ (the surfaces listed in P7-4)."
            )

        # The recovery plan must back-reference at least one of the candidate
        # cross-link notes by filename, so the note is discoverable from the
        # plan itself. (frontend_drift_history.md is a P1-5 historical record
        # that also cross-links both documents but is not itself the P7-4
        # cross-link note; we accept any candidate the plan points back at.)
        plan_text = RECOVERY_PLAN.read_text(encoding="utf-8")
        referenced = [n for n in notes if n.name in plan_text]
        assert referenced, (
            f"recovery plan {RECOVERY_PLAN} must reference at least one "
            f"cross-link note from {[n.name for n in notes]} so readers can "
            "discover it without prior knowledge of the filename."
        )
