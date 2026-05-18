"""Task P7-3: Update examples so the stable story begins from LaTeX input.

Phase 7 (R6.3) — docs-tier acceptance: the canonical first-run example in
``README.md`` and ``dev/examples/`` must use ``compile_latex(...)`` as the
primary entry point. Programmatic ``build_context()`` / direct ProblemIR
construction is preserved (P2-2 mandate) but demoted to advanced/testing
aid status.

Tier: docs

Acceptance criteria:
  1. P7-3-c1: First-run example in docs uses the canonical path
     (``compile_latex`` reading a LaTeX source).
  2. P7-3-c2: Deliverables present at the listed surfaces (``examples/``,
     ``README.md``).
  3. No regressions on the existing test suite.

Blocked by: P2-1 (the canonical ``compile_latex`` façade must exist
before examples can call it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Repo-root anchor: this test lives at
# packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p7_3.py
REPO_ROOT = Path(__file__).resolve().parents[5]
README_PATH = REPO_ROOT / "README.md"
EXAMPLES_DIR = REPO_ROOT / "dev" / "examples"


class TestP7_3:
    """Tests for Task P7-3: examples present LaTeX-first canonical story."""

    @pytest.mark.docs
    def test_first_run_example_in_readme_uses_canonical_path(self) -> None:
        """P7-3-c1: First-run example in docs uses the canonical path.

        Verifies: the first end-to-end example in ``README.md`` (the one
        users hit when scanning top-down) imports ``compile_latex`` /
        starts from a LaTeX string, and any programmatic ProblemIR example
        appears later under an "advanced" / "testing" heading.

        Passes when: README parsing locates a ``compile_latex`` snippet
        before any ``build_context`` / ``ProblemIR(...)`` snippet.
        """
        assert README_PATH.is_file(), f"missing README at {README_PATH}"
        text = README_PATH.read_text(encoding="utf-8")

        # post_recovery_plan Phase 7 (P7-2): scope ordering check to
        # *runnable code blocks* (markdown ```python ... ``` fences),
        # not raw text. Bare prose mentions of `compile_latex(` /
        # `build_context(` near the top of the README no longer flip
        # the assertion. Robust against doc copy edits.
        import re as _re_runnable

        _CODE_BLOCK_RE = _re_runnable.compile(
            r"```(?:python|py|bash|shell)?\s*\n(.*?)```", _re_runnable.DOTALL
        )

        def _first_in_runnable_blocks(needle: str) -> int:
            for match in _CODE_BLOCK_RE.finditer(text):
                if needle in match.group(1):
                    return match.start()
            return -1

        first_compile_latex = _first_in_runnable_blocks("compile_latex(")
        first_build_context = _first_in_runnable_blocks("build_context(")
        first_problem_ir = _first_in_runnable_blocks("ProblemIR(")

        assert first_compile_latex != -1, (
            "README.md must contain a `compile_latex(` snippet so the "
            "canonical LaTeX-first path is documented (P7-3-c1)."
        )

        # The canonical LaTeX example must precede any programmatic
        # ``build_context(...)`` / ``ProblemIR(...)`` example. Either the
        # programmatic substring is absent, or it appears strictly after
        # the canonical one.
        if first_build_context != -1:
            assert first_compile_latex < first_build_context, (
                "README.md must show `compile_latex(` before "
                "`build_context(`; the LaTeX-first path is the stable "
                "story (P7-3-c1)."
            )
        if first_problem_ir != -1:
            assert first_compile_latex < first_problem_ir, (
                "README.md must show `compile_latex(` before "
                "`ProblemIR(`; the programmatic API is an advanced / "
                "testing aid only (P7-3-c1)."
            )

    @pytest.mark.docs
    def test_deliverables_present_at_surfaces(self) -> None:
        """P7-3-c2: Deliverables present at the listed surfaces.

        Verifies: at least one runnable script under ``dev/examples/`` (or
        ``examples/``) is a LaTeX-input example; README references it; the
        Programmatic / build_context path remains documented but secondary.

        Passes when: a LaTeX example file exists, README links to it, and
        the README ordering keeps the LaTeX example first.
        """
        assert EXAMPLES_DIR.is_dir(), f"missing examples dir at {EXAMPLES_DIR}"

        # Leg (a): at least one .py file under dev/examples/ imports
        # ``compile_latex`` AND opens or contains a literal LaTeX source
        # (either reads a .tex file or embeds a raw string with the
        # canonical ``% mechanics`` directive prefix).
        latex_first_scripts: list[Path] = []
        for script in sorted(EXAMPLES_DIR.glob("*.py")):
            content = script.read_text(encoding="utf-8")
            imports_compile_latex = "from mechdsl import compile_latex" in content or (
                "import mechdsl" in content and "compile_latex" in content
            )
            has_literal_latex = "% mechanics" in content or ".tex" in content
            if imports_compile_latex and has_literal_latex:
                latex_first_scripts.append(script)

        assert latex_first_scripts, (
            "Expected at least one LaTeX-first script under "
            f"{EXAMPLES_DIR}: a .py file that imports `compile_latex` "
            "and either embeds a `% mechanics` literal or reads a .tex "
            "file (P7-3-c2)."
        )

        # Leg (b): README references at least one of those scripts by
        # relative path, so users can copy/paste the runnable command.
        #
        # post_recovery_plan Phase 7 (P7-2): accept three path-prefix
        # variants — `dev/examples/<name>`, `./dev/examples/<name>`,
        # and any absolute prefix ending in `/dev/examples/<name>`.
        # Robust against doc-style differences across READMEs.
        readme_text = README_PATH.read_text(encoding="utf-8")
        relative_names = {script.name for script in latex_first_scripts}
        accepted_prefixes = ("dev/examples/", "./dev/examples/", "/dev/examples/")
        # The third entry above also covers any absolute prefix (e.g.
        # `/Users/.../dev/examples/...`) because `is_absolute()` paths
        # always contain the substring `/dev/examples/`.
        found = any(
            f"{prefix}{name}" in readme_text
            for prefix in accepted_prefixes
            for name in relative_names
        )
        assert found, (
            "README.md must reference at least one LaTeX-first example "
            f"script by one of {accepted_prefixes!r} (basenames: "
            f"{sorted(relative_names)}) so the canonical first-run path "
            "is reachable (P7-3-c2)."
        )
