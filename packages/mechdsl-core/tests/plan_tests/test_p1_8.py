from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"
ONE_SENTENCE_NOTE = (
    "PR boundaries are tracked per task in "
    "`dev/tasks/recovery_plan_latex_contract/json/`; one task = one PR is the default."
)


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


class TestTaskP1_8:
    """
    Tests for Task P1-8: Drop or fold the 'Suggested PR slices' section
    Acceptance criteria covered: 1, 2
    """

    @pytest.mark.audit
    def test_no_legacy_pr_slice_patterns(self) -> None:
        text = _plan_text()
        # legacy slicing patterns interleaved tasks across phases (e.g. "PR-2 ... R1.1")
        assert not re.search(r"PR-\d.*R\d\.\d", text), "legacy interleaved PR slicing still present"
        for legacy_header in ("### PR-1 ", "### PR-2 ", "### PR-3 ", "### PR-4 "):
            assert legacy_header not in text, (
                f"legacy PR-slice header still present: {legacy_header!r}"
            )

    @pytest.mark.audit
    def test_section_either_deleted_or_one_sentence(self) -> None:
        text = _plan_text()
        match = re.search(r"^## Suggested PR slices\b", text, flags=re.MULTILINE)
        if match is None:
            return  # section deleted entirely is acceptable
        # section retained — body must contain the canonical one-sentence note
        # and be brief (no nested ### sub-sections).
        tail = text[match.end() :]
        next_top = re.search(r"^## ", tail, flags=re.MULTILINE)
        body = tail[: next_top.start()] if next_top else tail
        assert ONE_SENTENCE_NOTE in body, "one-sentence note missing from retained section"
        assert "### " not in body, "retained section should have no sub-headings"
