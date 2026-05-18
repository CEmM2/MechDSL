from __future__ import annotations

import re
from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parents[4] / "dev" / "plans" / "recovery_plan_latex_contract.md"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


class TestTaskP1_1:
    """
    Tests for Task P1-1: Insert Phase ID mapping (R-label ↔ Aut_Faciam integer) table
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_phase_id_mapping_section_present(self) -> None:
        text = _plan_text()
        hits = re.findall(r"^## Phase ID mapping", text, flags=re.MULTILINE)
        assert len(hits) == 1, (
            f"expected exactly one '## Phase ID mapping' heading, found {len(hits)}"
        )

    @pytest.mark.audit
    def test_mapping_appears_before_first_phase_heading(self) -> None:
        text = _plan_text()
        mapping = text.find("## Phase ID mapping")
        first_phase = re.search(r"^## Phase (?:R\d|\d) ", text, flags=re.MULTILINE)
        assert mapping >= 0, "mapping section missing"
        assert first_phase is not None, "no phase heading found"
        assert mapping < first_phase.start(), (
            f"mapping at offset {mapping} should precede first phase heading at {first_phase.start()}"
        )

    @pytest.mark.audit
    def test_all_seven_phases_listed_with_r_label(self) -> None:
        text = _plan_text()
        section_match = re.search(
            r"## Phase ID mapping.*?(?=^---|^## )", text, flags=re.MULTILINE | re.DOTALL
        )
        assert section_match is not None
        section = section_match.group(0)
        for phase_int in range(1, 8):
            assert re.search(rf"^\|\s*{phase_int}\s*\|", section, flags=re.MULTILINE), (
                f"missing row for Aut_Faciam phase {phase_int}"
            )
        for r_label in ("R0", "R1", "R2", "R3", "R4", "R5", "R6"):
            assert re.search(rf"\|\s*{r_label}\s*\|", section), f"missing R-label {r_label}"
