"""Tests for Task P2-3: audit and update CI workflow tier:docs selector.

Acceptance criteria covered:
1. CI workflow runs `pytest -m docs` on the doc-tier label or label-routed
   selector.
2. No remaining references to integration-marker fallback for the doc-tier
   tests in `.github/workflows/*.yml`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".github" / "workflows").is_dir():
            return parent
    raise RuntimeError("repo root with .github/workflows not found")


def _workflow_files() -> list[Path]:
    root = _repo_root()
    return sorted((root / ".github" / "workflows").glob("*.yml")) + sorted(
        (root / ".github" / "workflows").glob("*.yaml")
    )


_DOCS_SELECTOR_RE = re.compile(r"-m\s+(?:\"[^\"]*\bdocs\b[^\"]*\"|'[^']*\bdocs\b[^']*'|docs\b)")
_INTEGRATION_SELECTOR_RE = re.compile(
    r"-m\s+(?:\"[^\"]*\bintegration\b[^\"]*\"|'[^']*\bintegration\b[^']*'|integration\b)"
)
_DOC_TIER_TEST_RE = re.compile(r"test_p7_[3-6]")


class TestTaskP2_3:
    """Tests for Task P2-3: audit/update CI workflow tier:docs selector."""

    @pytest.mark.integration
    def test_workflow_invokes_pytest_dash_m_docs(self) -> None:
        """At least one workflow job runs `pytest -m docs`."""
        files = _workflow_files()
        assert files, "no workflow files found under .github/workflows/"
        matches: list[tuple[str, int, str]] = []
        for f in files:
            text = f.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if _DOCS_SELECTOR_RE.search(line):
                    matches.append((f.name, lineno, line.strip()))
        assert matches, (
            "expected at least one `pytest -m docs` selector in "
            ".github/workflows/*.yml; tier:docs label has no route"
        )

    @pytest.mark.integration
    def test_no_integration_fallback_for_doc_tier_tests(self) -> None:
        """No workflow job targets the P7-3..6 doc-tier tests via the
        integration-marker fallback. Generic `-m integration` references
        elsewhere (covering non-doc-tier tests) are permitted."""
        problems: list[str] = []
        for f in _workflow_files():
            text = f.read_text(encoding="utf-8")
            if _DOC_TIER_TEST_RE.search(text) and _INTEGRATION_SELECTOR_RE.search(text):
                # Narrow down to lines for reporting if possible, but flag the file if found anywhere
                found_on_line = False
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if _DOC_TIER_TEST_RE.search(line) and _INTEGRATION_SELECTOR_RE.search(line):
                        problems.append(f"{f.name}:{lineno}: {line.strip()}")
                        found_on_line = True
                if not found_on_line:
                    problems.append(
                        f"{f.name}: Found both integration marker and doc-tier tests (potential multi-line command)"
                    )
                    problems.append(f"{f.name}:{lineno}: {line.strip()}")
        assert not problems, (
            "integration-marker fallback still references doc-tier P7-3..6 "
            "tests:\n" + "\n".join(problems)
        )
