"""Live audit for recovery-plan P6-4: Defer radial-return replacement.

Task: P6-4 — Defer radial-return replacement until frontend + IR alignment
is settled.
Phase: 6 (Integrate ``algo2code`` at the least risky seam — R5)
Tier: docs (planning docs only)

Acceptance criteria:

1. Recovery docs explicitly label radial-return substitution as later-stage
   work.
2. All deliverables for P6-4 are in place at the surfaces listed
   (planning docs only).
3. No regressions on the existing test suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# P6-4 is a docs-tier task — no mechdsl runtime symbol is checked here.
# The deferral surface is the recovery plan; tests audit its prose.

_ROOT = Path(__file__).resolve().parents[5]
_RECOVERY_PLAN = _ROOT / "dev" / "plans" / "recovery_plan_latex_contract.md"

_LATER_STAGE_MARKERS = ("later-stage", "deferred", "post-MVP")
_PREREQUISITE_MARKERS = ("frontend", "IR alignment", "R2", "R3")


def _normalize(text: str) -> str:
    return text.lower()


def _contains_radial_return(text: str) -> bool:
    """Match either ``radial-return`` or ``radial return`` (case-insensitive)."""
    lowered = _normalize(text)
    return "radial-return" in lowered or "radial return" in lowered


def _has_later_stage_marker(text: str) -> bool:
    lowered = _normalize(text)
    return any(marker.lower() in lowered for marker in _LATER_STAGE_MARKERS)


def _has_prerequisite_marker(text: str) -> bool:
    """Frontend / IR / R2 / R3 / alignment cue (case-insensitive substring,
    except R2 / R3 which we match as whole tokens to avoid false positives)."""
    lowered = _normalize(text)
    if "frontend" in lowered or "ir alignment" in lowered or "alignment" in lowered:
        return True
    # R2 / R3 as standalone tokens (allow surrounding punctuation / parens).
    return bool(re.search(r"\br[23]\b", text, flags=re.IGNORECASE))


def _split_paragraphs(text: str) -> list[str]:
    """Split a markdown body into paragraph blocks separated by blank lines."""
    return [block for block in re.split(r"\n\s*\n", text) if block.strip()]


class TestP6_4:
    """
    Tests for Task P6-4: Defer radial-return replacement until
    frontend + IR alignment is settled.
    Tier: docs (recovery-plan documentation audit)
    """

    @pytest.mark.regression
    def test_recovery_plan_labels_radial_return_as_later_stage(self) -> None:
        """
        Verifies: dev/plans/recovery_plan_latex_contract.md explicitly labels
                  radial-return substitution as later-stage work.
        Acceptance criterion: P6-4-c1 (recovery docs explicitly label
                              radial-return substitution as later-stage work).
        Passes when: the recovery plan contains both 'radial-return' and a
                     later-stage label (e.g. 'later-stage', 'deferred',
                     'post-MVP') in the same context.
        Expected: a sentence like "radial-return substitution is later-stage
                  work, deferred until frontend + IR alignment is settled."
        """
        assert _RECOVERY_PLAN.exists(), f"Missing recovery plan at {_RECOVERY_PLAN}"
        text = _RECOVERY_PLAN.read_text(encoding="utf-8")

        assert _contains_radial_return(text), (
            "Recovery plan must mention 'radial-return' (or 'radial return') "
            "to anchor the P6-4 deferral note."
        )
        assert _has_later_stage_marker(text), (
            f"Recovery plan must label the radial-return work with one of {_LATER_STAGE_MARKERS}."
        )

        # 'In the same context' check: at least one paragraph block carries
        # both the radial-return token and a later-stage marker.
        paragraphs = _split_paragraphs(text)
        co_located = [
            block
            for block in paragraphs
            if _contains_radial_return(block) and _has_later_stage_marker(block)
        ]
        assert co_located, (
            "Recovery plan must place 'radial-return' and a later-stage "
            "marker in the same paragraph / callout block."
        )

    @pytest.mark.regression
    def test_p6_4_deliverables_present_in_planning_docs(self) -> None:
        """
        Verifies: the P6-4 deliverable surface (planning docs only) carries
                  the deferral note where the recovery plan promises it.
        Acceptance criterion: P6-4-c2 (deliverables present at the listed
                              surfaces — 'planning docs only').
        Passes when: dev/plans/recovery_plan_latex_contract.md contains the
                     P6-4 row AND a clarifying paragraph or note that
                     classifies radial-return replacement as later-stage /
                     deferred work, not just a one-line table entry.
        Expected: a section, callout, or paragraph in the recovery plan that
                  expands on the P6-4 row and pins the radial-return work
                  to a later phase.
        """
        assert _RECOVERY_PLAN.exists(), f"Missing recovery plan at {_RECOVERY_PLAN}"
        text = _RECOVERY_PLAN.read_text(encoding="utf-8")

        # The original P6-4 table-row anchor must remain intact for traceability
        # with dev/tasks/recovery_plan_latex_contract/json/P6-4.json.
        assert "P6-4 | R5.4" in text, (
            "Recovery plan must keep the 'P6-4 | R5.4' table row as the anchor "
            "for the deferral note."
        )

        # Locate a paragraph / callout block (multi-line, NOT the table row)
        # that mentions radial-return AND a frontend / IR / R2 / R3 cue.
        paragraphs = _split_paragraphs(text)
        candidates = [
            block
            for block in paragraphs
            if _contains_radial_return(block)
            and _has_prerequisite_marker(block)
            and block.count("\n") >= 1  # multi-line: paragraph or blockquote
            and not block.lstrip().startswith("| ")  # exclude the table row
        ]
        assert candidates, (
            "Recovery plan must contain a multi-line paragraph or blockquote "
            "that expands the P6-4 row and pins radial-return work behind a "
            "frontend / IR alignment (R2 / R3) prerequisite."
        )

        # Sanity: at least one such block also flags the work as later-stage,
        # so c1's 'in same context' guarantee co-locates with c2's expansion.
        expanded = [block for block in candidates if _has_later_stage_marker(block)]
        assert expanded, (
            "The expanded P6-4 paragraph must itself carry a later-stage / "
            "deferred / post-MVP marker, not just the bare table row."
        )
