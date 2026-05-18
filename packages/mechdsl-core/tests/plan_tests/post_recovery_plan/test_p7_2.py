"""Tests for Task P7-2: robustify test_p7_3.py ordering check + path matching.

Acceptance:
1. Ordering check uses a first-runnable-code-block detector (markdown
   ```python``` fence regex), not a bare `text.find("compile_latex(")`
   that breaks if prose mentions appear earlier.
2. README path matching accepts `dev/examples/`, `./dev/examples/`, and
   absolute prefixes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "packages").is_dir():
            return parent
    raise RuntimeError("repo root not found")


def _target() -> Path:
    return (
        _repo_root()
        / "packages"
        / "mechdsl-core"
        / "tests"
        / "plan_tests"
        / "recovery_plan_latex_contract"
        / "test_p7_3.py"
    )


class TestTaskP7_2:
    @pytest.mark.docs
    def test_no_bare_text_find_for_compile_latex(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # The bare `text.find("compile_latex(")` returns the position of
        # the first prose mention — replace with a detector that looks
        # at runnable code blocks only.
        bad = re.search(r'text\.find\(\s*"compile_latex\(', text)
        assert bad is None, (
            'test_p7_3.py must not use bare text.find("compile_latex(") — '
            "use a runnable-code-block detector"
        )

    @pytest.mark.docs
    def test_uses_runnable_code_block_detector(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # Must reference a markdown code fence pattern (```python, ```bash, etc.)
        # to scope the search to runnable blocks.
        assert "```" in text or "code_fence" in text or "code_block" in text, (
            "test_p7_3.py must scope the ordering check to runnable code blocks"
        )

    @pytest.mark.docs
    def test_path_matching_accepts_three_variants(self) -> None:
        text = _target().read_text(encoding="utf-8")
        # Loosened path matching must mention each acceptable prefix
        # form so the regression check is documented.
        for variant in ("dev/examples/", "./dev/examples/"):
            assert variant in text, f"test_p7_3.py path matching must accept {variant!r}"
        # Absolute-prefix branch — at minimum mention "absolute" or
        # rely on Path.is_absolute logic.
        assert "absolute" in text.lower() or "is_absolute" in text, (
            "test_p7_3.py must accept absolute-path prefixes"
        )
