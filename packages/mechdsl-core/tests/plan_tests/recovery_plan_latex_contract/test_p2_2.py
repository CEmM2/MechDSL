"""Live audit for recovery-plan P2-2: preserve ``build_context`` as documented secondary API.

Asserts:
1. ``build_context`` is still importable and functional.
2. The frontend module docstring + the function docstring flag it as
   secondary while pointing at ``compile_latex`` as canonical.
3. README's Quickstart leads with the LaTeX-source example, not the
   programmatic ``build_context`` one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
README = REPO_ROOT / "README.md"
FRONTEND_INIT = (
    REPO_ROOT / "packages" / "mechdsl-core" / "src" / "mechdsl" / "frontend" / "__init__.py"
)


class TestTaskP2_2:
    """
    Tests for Task P2-2: Preserve ``build_context()`` as documented secondary API.
    Tier: unit
    """

    @pytest.mark.unit
    def test_build_context_still_importable_and_functional(self) -> None:
        from mechdsl.frontend import build_context

        ctx = build_context(
            dim=3,
            cell_type="hex8",
            formulation="total_lagrangian",
            material_type="svk",
            params={"E": 200e3, "nu": 0.3},
            boundaries=[
                {"name": "fix", "type": "dirichlet", "value": 0.0},
            ],
        )
        # Returns the same context-dict shape it always did.
        assert ctx["dim"] == 3
        assert ctx["cell_type"] == "hex8"
        assert ctx["material_type"] == "svk"

    @pytest.mark.unit
    def test_frontend_module_doc_marks_build_context_secondary(self) -> None:
        text = FRONTEND_INIT.read_text(encoding="utf-8")
        # The module docstring should explicitly call out compile_latex as
        # canonical and list build_context under a secondary header.
        assert "compile_latex" in text, "frontend docstring should reference compile_latex"
        assert "Secondary" in text or "secondary" in text, (
            "frontend module docstring should label build_context as secondary"
        )

    @pytest.mark.unit
    def test_build_context_docstring_marks_secondary(self) -> None:
        from mechdsl.frontend import build_context

        doc = build_context.__doc__ or ""
        assert "secondary" in doc.lower(), "build_context docstring should mark itself as secondary"
        assert "compile_latex" in doc, (
            "build_context docstring should point at compile_latex as canonical"
        )

    @pytest.mark.unit
    def test_readme_quickstart_leads_with_latex_example(self) -> None:
        text = README.read_text(encoding="utf-8")
        quickstart_match = re.search(
            r"^## Quickstart\b.*?(?=^## )", text, flags=re.MULTILINE | re.DOTALL
        )
        assert quickstart_match, "README Quickstart section missing"
        block = quickstart_match.group(0)

        latex_pos = block.find("compile_latex")
        build_context_pos = block.find("build_context")
        assert latex_pos != -1, "Quickstart should reference compile_latex"
        assert build_context_pos != -1, (
            "Quickstart should still reference build_context as the secondary path"
        )
        assert latex_pos < build_context_pos, (
            "Quickstart should show the LaTeX-source example before the "
            "programmatic build_context example"
        )
