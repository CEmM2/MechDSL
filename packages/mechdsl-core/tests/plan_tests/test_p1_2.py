from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


def _phase_headings() -> list[str]:
    text = _plan_text()
    # match `## Phase <int> — ... (R<digit>)` only (the canonical form after P1-2)
    return re.findall(r"^## Phase \d+ — .*?\(R\d\)\s*$", text, flags=re.MULTILINE)


class TestTaskP1_2:
    """
    Tests for Task P1-2: Renumber phase headings to integer + (RX) form
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_seven_integer_phase_headings(self) -> None:
        text = _plan_text()
        # `^## Phase <digit> —` count must equal 7
        hits = re.findall(r"^## Phase \d+ — ", text, flags=re.MULTILINE)
        assert len(hits) == 7, f"expected 7 integer-form phase headings, found {len(hits)}"
        # no legacy `## Phase R<digit> —` headings should remain
        legacy = re.findall(r"^## Phase R\d — ", text, flags=re.MULTILINE)
        assert not legacy, f"legacy R-form headings still present: {legacy}"

    @pytest.mark.audit
    def test_each_heading_carries_legacy_r_label(self) -> None:
        headings = _phase_headings()
        assert len(headings) == 7, f"expected 7 canonical phase headings, found {len(headings)}"
        for h in headings:
            assert re.search(r"\(R\d\)\s*$", h), f"heading missing legacy (RX) suffix: {h!r}"

    @pytest.mark.audit
    def test_phase_numbers_strictly_increasing(self) -> None:
        headings = _phase_headings()
        nums = [int(re.match(r"## Phase (\d+) ", h).group(1)) for h in headings]
        assert nums == sorted(nums), f"phase numbers not in increasing order: {nums}"
        assert nums == list(range(1, 8)), f"expected exactly 1..7, got {nums}"
