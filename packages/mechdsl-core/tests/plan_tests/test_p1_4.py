from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
PLAN = REPO_ROOT / "dev" / "plans" / "recovery_plan_latex_contract.md"
ANCHOR_HEADING = "### Code reality anchor (2026-04-26)"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


class TestTaskP1_4:
    """
    Tests for Task P1-4: Insert Code reality anchor blocks per phase
    Acceptance criteria covered: 1, 2, 3
    """

    @pytest.mark.audit
    def test_seven_code_reality_anchor_subsections(self) -> None:
        text = _plan_text()
        count = text.count(ANCHOR_HEADING)
        assert count == 7, f"expected 7 Code reality anchor subsections, found {count}"

    @pytest.mark.audit
    def test_each_anchor_has_at_least_three_bullets(self) -> None:
        text = _plan_text()
        positions = [m.start() for m in re.finditer(re.escape(ANCHOR_HEADING), text)]
        assert len(positions) == 7, f"expected 7 anchors, found {len(positions)}"
        for start in positions:
            tail = text[start + len(ANCHOR_HEADING) :]
            next_heading = re.search(r"\n###? ", tail)
            block = tail[: next_heading.start()] if next_heading else tail
            bullets = re.findall(r"^- ", block, flags=re.MULTILINE)
            assert len(bullets) >= 3, (
                f"anchor near offset {start} has only {len(bullets)} bullets; expected >= 3"
            )

    @pytest.mark.audit
    def test_citations_point_to_existing_files(self) -> None:
        text = _plan_text()
        positions = [m.start() for m in re.finditer(re.escape(ANCHOR_HEADING), text)]
        cited_paths: set[str] = set()
        for start in positions:
            tail = text[start + len(ANCHOR_HEADING) :]
            next_heading = re.search(r"\n###? ", tail)
            block = tail[: next_heading.start()] if next_heading else tail
            for match in re.finditer(
                r"`([A-Za-z0-9_./-]+\.(?:py|md|toml))(?::\d+(?:-\d+)?)?`", block
            ):
                cited_paths.add(match.group(1))
        assert cited_paths, "no file citations found inside anchors"
        # Citations are short-form relative paths (e.g. `mechanics_ir.py`,
        # `frontend/__init__.py`) that resolve somewhere under packages/.
        search_roots = (
            REPO_ROOT,
            REPO_ROOT / "packages" / "mechdsl-core" / "src",
            REPO_ROOT / "packages" / "algo2code" / "src",
        )

        def _resolves(short_path: str) -> bool:
            for root in search_roots:
                if (root / short_path).exists():
                    return True
            tail = short_path.rsplit("/", 1)[-1]
            for root in search_roots:
                if any(root.rglob(tail)):
                    return True
            return False

        resolved_missing = [p for p in cited_paths if not _resolves(p)]
        assert not resolved_missing, f"cited paths do not resolve: {resolved_missing}"
