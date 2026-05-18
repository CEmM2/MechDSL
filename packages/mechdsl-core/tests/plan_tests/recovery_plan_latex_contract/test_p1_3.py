"""Live audit for recovery-plan P1-3: Add a stability-policy note.

Asserts the README has a Stability policy subsection that references both
the recovery plan and the status legend.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
README = REPO_ROOT / "README.md"


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def _stability_policy_block() -> str:
    text = _readme_text()
    match = re.search(
        r"^### Stability policy\b.*?(?=^### |^## )", text, flags=re.MULTILINE | re.DOTALL
    )
    assert match, "README missing '### Stability policy' subsection"
    return match.group(0)


class TestTaskP1_3:
    """
    Tests for Task P1-3: Add a lightweight stability-policy note.
    Tier: docs
    """

    @pytest.mark.audit
    def test_stability_policy_subsection_present(self) -> None:
        text = _readme_text()
        assert "### Stability policy" in text, (
            "README should include a '### Stability policy' subsection under Support tiers"
        )

    @pytest.mark.audit
    def test_policy_references_recovery_plan(self) -> None:
        block = _stability_policy_block()
        assert "recovery_plan_latex_contract.md" in block, (
            "Stability policy should reference the recovery plan"
        )

    @pytest.mark.audit
    def test_policy_references_status_legend(self) -> None:
        block = _stability_policy_block()
        assert "STATUS_LEGEND.md" in block, (
            "Stability policy should point at the canonical tracker status legend"
        )
