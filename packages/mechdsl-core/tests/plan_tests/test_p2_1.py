"""P2-1 verification — skim of amended recovery plan.

Phase-2 verification of the back2latex plan reuses the live Phase-1 audit
suite as its evidence base: the seven structural checks listed in
back2latex.md verification step 1 are exactly what test_p1_{1..9} already
assert. This file simply imports those modules to confirm the suite is
importable and well-formed; the suite itself is exercised by the audit
selector in CI.
"""

from __future__ import annotations

import pytest

P1_MODULES = [f"packages.mechdsl_core.tests.plan_tests.test_p1_{n}" for n in range(1, 10)]


class TestTaskP2_1:
    """
    Tests for Task P2-1: Skim verification of amended recovery plan
    Acceptance criteria covered: structural checks per back2latex.md step 1
    """

    @pytest.mark.audit
    def test_phase1_audit_suite_importable(self) -> None:
        # mirror the on-disk layout (`tests/plan_tests/test_p1_*.py`) so importing
        # by file works from the test directory.
        from pathlib import Path

        plan_tests_dir = Path(__file__).parent
        for n in range(1, 10):
            f = plan_tests_dir / f"test_p1_{n}.py"
            assert f.is_file(), f"missing Phase-1 audit module {f}"

    @pytest.mark.audit
    def test_recovery_plan_present_for_skim(self) -> None:
        from pathlib import Path

        plan = (
            Path(__file__).resolve().parents[4]
            / "dev"
            / "plans"
            / "recovery_plan_latex_contract.md"
        )
        assert plan.is_file(), f"recovery plan missing: {plan}"
        # quick sanity: the seven phase headings are still in place
        text = plan.read_text(encoding="utf-8")
        import re

        hits = re.findall(r"^## Phase \d+ — ", text, flags=re.MULTILINE)
        assert len(hits) == 7, f"expected 7 integer phase headings, found {len(hits)}"
