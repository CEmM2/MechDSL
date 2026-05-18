"""Task P7-6: Closing drift/alignment review after Phases R1–R4 land.

Phase 7 (R6.6) docs-tier acceptance: once the four pillars (R1 frontend,
R2 ProblemIR, R3 ElementIR, R4 Taichi codegen) are landed, the recovery
loop is closed by a follow-up to ``dev/reviews/drift_20_04.md`` that
records explicit per-pillar verdicts.

Tier: docs. Blocked by: P2-1, P3-1, P4-1, P5-1 (the four pillars).

Acceptance: (c1) follow-up review answers each pillar with one of
RESTORED / PARTIAL / STILL DRIFTING; (c2) review file lives under
``dev/reviews/`` and reconciles ≥5 of the recovery plan's success
criteria.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repo root: this file is at
# packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_6.py
# so .parents[5] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REVIEWS_DIR = _REPO_ROOT / "dev" / "reviews"
_RECOVERY_PLAN = _REPO_ROOT / "dev" / "plans" / "recovery_plan_latex_contract.md"

# Verdict words the follow-up review may assign to a pillar.
_VERDICT_PATTERN = re.compile(
    r"\b(RESTORED|STILL\s+DRIFTING|PARTIAL)\b",
    re.IGNORECASE,
)


def _find_followup_review() -> Path:
    """Locate ``drift_post_recovery*.md`` under ``dev/reviews/`` (parallels
    the ``drift_20_04.md`` naming; glob tolerates a date suffix)."""
    candidates = sorted(_REVIEWS_DIR.glob("drift_post_recovery*.md"))
    assert candidates, f"P7-6 expected drift_post_recovery*.md under {_REVIEWS_DIR}; found none."
    return candidates[0]


def _section_for_pillar(text: str, pillar: str) -> str:
    """Slice of ``text`` belonging to one R-pillar section, delimited by
    markdown headings (``## R1 ...`` or ``### R1 — ...``); ends at the
    next heading of equal-or-higher level."""
    head_re = re.compile(rf"^(#+)\s+{pillar}\b", re.MULTILINE | re.IGNORECASE)
    m = head_re.search(text)
    assert m, f"Follow-up review has no heading for pillar {pillar!r}."
    depth = len(m.group(1))
    next_head_re = re.compile(rf"^#{{1,{depth}}}\s+\S", re.MULTILINE)
    nxt = next_head_re.search(text, pos=m.end())
    return text[m.start() : (nxt.start() if nxt else len(text))]


class TestP7_6:
    """Tests for Task P7-6: post-R1–R4 closing drift/alignment review."""

    @pytest.mark.docs
    def test_follow_up_review_confirms_contract_status(self) -> None:
        """P7-6-c1: review references the original drift report and
        records an explicit verdict (RESTORED / PARTIAL / STILL DRIFTING)
        per pillar R1–R4."""
        review = _find_followup_review()
        text = review.read_text(encoding="utf-8")
        assert "drift_20_04.md" in text, (
            f"{review.name} must reference drift_20_04.md so readers can "
            "trace the recovery-loop closure."
        )
        for pillar in ("R1", "R2", "R3", "R4"):
            section = _section_for_pillar(text, pillar)
            assert _VERDICT_PATTERN.search(section), (
                f"Pillar {pillar} in {review.name} has no verdict "
                "(RESTORED / PARTIAL / STILL DRIFTING)."
            )

    @pytest.mark.docs
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-6-c2: review lives under ``dev/reviews/`` and reconciles
        ≥5 of the recovery plan's 9 success-criteria checklist bullets
        (matched by lowercased 5-word fingerprint, with a tail-fingerprint
        fallback for bullets starting with stop-words)."""
        review = _find_followup_review()
        assert review.parent == _REVIEWS_DIR, f"{review} is not under dev/reviews/."

        raw_review = review.read_text(encoding="utf-8").lower()
        review_text = re.sub(r"\s+", " ", raw_review)

        assert _RECOVERY_PLAN.is_file(), f"Recovery plan missing at {_RECOVERY_PLAN}."
        plan_lines = _RECOVERY_PLAN.read_text(encoding="utf-8").splitlines()
        # Success-criteria block lives ~lines 60–69; widen window for drift.
        block_window = "\n".join(plan_lines[55:75])
        bullet_re = re.compile(r"^- \[[ x]\] (?P<body>.+)$", re.MULTILINE)
        bullets = [m.group("body").strip() for m in bullet_re.finditer(block_window)]
        assert len(bullets) >= 9, (
            f"Plan success-criteria block changed shape (found {len(bullets)}; "
            "expected ≥9). Update P7-6 alongside any plan rewrite."
        )

        def fingerprint(bullet: str, lo: int = 0, hi: int = 5) -> str:
            words = re.findall(r"[A-Za-z_]+", bullet)
            return " ".join(words[lo:hi]).lower()

        matched = 0
        for bullet in bullets:
            fp = fingerprint(bullet)
            if not fp:
                continue
            if fp in review_text or (
                len(re.findall(r"[A-Za-z_]+", bullet)) >= 8
                and fingerprint(bullet, 3, 8) in review_text
            ):
                matched += 1

        assert matched >= 5, (
            f"Follow-up review {review.name} mirrors only {matched} of "
            f"{len(bullets)} plan success criteria; P7-6 requires ≥5."
        )
