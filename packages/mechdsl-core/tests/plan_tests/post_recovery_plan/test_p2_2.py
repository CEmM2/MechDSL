"""Tests for Task P2-2: swap @pytest.mark.integration → @pytest.mark.docs
on doc-tier P7-3..P7-6 tests.

Acceptance criteria covered:
1. No `@pytest.mark.integration` decorators remain on doc-tier tests in
   `test_p7_*` files (test_p7_3, test_p7_4, test_p7_5, test_p7_6).
2. `uv run pytest -m docs` selects the doc-tier tests; the selection is
   confined to the recovery_plan_latex_contract test_p7_*.py files (and
   any tests explicitly tagged docs in this plan's stubs).

Tier note: P2-2 task JSON sets test_plan.tier="docs" (the swap target
marker), but this meta-stub itself verifies *source files* and runs in
the fast suite, so it is registered at tier `unit`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / ".github").is_dir():
            return parent
    raise RuntimeError("repo root not found")


_DOC_TIER_FILES = (
    "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_3.py",
    "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_4.py",
    "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_5.py",
    "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_6.py",
)


class TestTaskP2_2:
    """Tests for Task P2-2: swap integration → docs marker on P7-3..6 doc-tier tests."""

    @pytest.mark.unit
    def test_no_integration_marker_on_doc_tier_files(self) -> None:
        """Each doc-tier P7 file must contain zero @pytest.mark.integration
        decorators and at least one @pytest.mark.docs decorator post-swap."""
        root = _repo_root()
        problems: list[str] = []
        for relpath in _DOC_TIER_FILES:
            f = root / relpath
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8")
            integration_hits = re.findall(r"@pytest\.mark\.integration\b", text)
            docs_hits = re.findall(r"@pytest\.mark\.docs\b", text)
            if integration_hits:
                problems.append(
                    f"{relpath}: {len(integration_hits)} @pytest.mark.integration decorator(s) remain"
                )
            if not docs_hits:
                problems.append(f"{relpath}: missing @pytest.mark.docs decorator")
        assert not problems, "\n".join(problems)

    @pytest.mark.unit
    def test_docs_marker_selects_only_p7_doc_tier_tests(self) -> None:
        """`pytest -m docs --collect-only` returns nodeids only under the doc-tier
        scope (recovery_plan_latex_contract/test_p7_*.py for the swap target;
        post_recovery_plan-stub paths for explicit P2 tagging are also allowed
        via @pytest.mark.docs but no such stub uses it today)."""
        root = _repo_root()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                str(root / "pyproject.toml"),
                "--rootdir",
                str(root),
                "-m",
                "docs",
                "--collect-only",
                "-q",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"pytest -m docs collection failed (rc={result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
        nodeids = [
            line for line in result.stdout.splitlines() if "::" in line and not line.startswith("=")
        ]
        assert nodeids, "expected at least one collected docs-marked test"
        # Allowed doc-tier homes:
        # - The P2-2 swap target — recovery_plan_latex_contract/test_p7_3..6.
        # - The post_recovery_plan-doc-tier paragraph regression tests
        #   (test_compile_latex_docstring.py + test_p3_*.py / test_p5_*.py
        #   meta-stubs) added by Phase 3 P3-1/P3-2 and Phase 5 P5-5.
        # - The Phase 4 nrpylatex round-trip suite
        #   (test_nrpylatex_round_trip.py) which exercises the math
        #   import chain at the docs tier.
        # NOTE: post_recovery_plan Phase 7 (P7-2) generalises the
        # explicit prefix list — any docs-tier test file under the
        # post_recovery_plan stub directory is admitted, plus the two
        # standalone regression-guard files. Replaces the old
        # phase-by-phase widening pattern (P3-1, P4-5, P5-5, P7).
        # The fgram plan (the continuation after post_recovery_plan)
        # carries its own docs-tier governance/round-trip stubs under
        # plan_tests/fgram/, admitted here on the same footing.
        # PlanJune14 (PJ-7 governance) adds two top-level doc-anchor stubs under
        # plan_tests/: test_p7_1 pins the 06-CODEGEN/11-ALGO2CODE design-doc addenda,
        # test_p7_2 pins the STATUS_LEGEND vocabulary contract. Admitted here on the
        # same footing as the recovery_plan / post_recovery_plan / fgram doc-tier tests.
        allowed_prefixes = (
            "packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_",
            "packages/mechdsl-core/tests/plan_tests/post_recovery_plan/",
            "packages/mechdsl-core/tests/plan_tests/fgram/",
            "packages/mechdsl-core/tests/plan_tests/test_p7_1.py",
            "packages/mechdsl-core/tests/plan_tests/test_p7_2.py",
            "packages/mechdsl-core/tests/test_compile_latex_docstring.py",
            "packages/mechdsl-core/tests/test_nrpylatex_round_trip.py",
        )
        for nodeid in nodeids:
            normalised = nodeid.split("::", 1)[0]
            assert any(normalised.startswith(p) for p in allowed_prefixes), (
                f"unexpected docs-marked nodeid outside doc-tier scope: {nodeid}"
            )
