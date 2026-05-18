"""Task P6-5: Document ``algo2code``'s role in the recovered architecture.

Phase 6 (R5.5) — docs-tier acceptance: ensure the public architecture
description names both packages of the monorepo and explains the
relationship between them, so the recovered seam between
``mechdsl-core`` and ``algo2code`` cannot silently regress to the
"design-doc only" state called out in the recovery plan.

Acceptance criteria:
  1. Public architecture description includes both packages and their
     relationship.
  2. All deliverables for P6-5 are in place at the surfaces listed
     (``README.md``, architecture docs, examples).
  3. No regressions on the existing test suite.

Plan reference: ``dev/plans/recovery_plan_latex_contract.md`` (Phase 6,
R5.5, line 321).

Surfaces under test:
  * Top-level ``README.md`` — must name both ``mechdsl-core`` and
    ``algo2code`` in the public architecture section and describe the
    consumer/producer relationship (e.g. ``mechdsl-core`` consumes
    ``algo2code``-generated artifacts behind ``LinearSolverInterface``).
  * ``dev/design_docs/`` — architecture documentation must reflect the
    recovered relationship (not just sibling existence).
  * ``dev/examples/`` — at least one example, or the examples README,
    points at the ``algo2code`` seam so the relationship is
    discoverable from runnable code.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]


def _split_paragraphs(text: str) -> list[str]:
    """Split markdown text into paragraph blocks (separated by blank lines)."""
    return [block.strip() for block in text.split("\n\n") if block.strip()]


def _extract_architecture_section(readme_text: str) -> str:
    """Return the body of the top-level ``## Architecture`` section.

    Includes any nested subsections (``###``) until the next top-level
    ``## `` heading is encountered.
    """
    lines = readme_text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## Architecture"):
            inside = True
            out.append(line)
            continue
        if inside and line.startswith("## ") and not line.startswith("## Architecture"):
            break
        if inside:
            out.append(line)
    return "\n".join(out)


class TestP6_5:
    """Tests for Task P6-5: document algo2code's role in the recovered architecture.

    Tier: docs (documentation/example audit).
    """

    def test_readme_architecture_section_names_both_packages(self) -> None:
        """P6-5-c1: README architecture description names both packages and
        their relationship.

        Verifies: top-level ``README.md`` contains a public architecture
        section that names both ``mechdsl-core`` and ``algo2code`` and
        documents that ``mechdsl-core`` consumes ``algo2code``-generated
        artifacts (e.g. the PCG path) behind ``LinearSolverInterface``.

        File under test: ``README.md`` (repo root).
        Expected wording (substrings):
          * ``mechdsl-core`` — the FEM compiler package is named.
          * ``algo2code`` — the sibling package is named.
          * ``LinearSolverInterface`` — the seam is identified, not
            just the package names.
          * a paragraph with both ``consumes`` and ``algo2code`` —
            making the consumer/producer relationship explicit.
          * ``PCG`` appears somewhere in the architecture section.

        Acceptance criterion: P6-5-c1.
        """
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")

        assert "mechdsl-core" in readme, "README must name the mechdsl-core package"
        assert "algo2code" in readme, "README must name the algo2code package"
        assert "LinearSolverInterface" in readme, (
            "README must name the LinearSolverInterface seam (CamelCase)"
        )

        # Consumer/producer relationship must live in a single paragraph.
        paragraphs = _split_paragraphs(readme)
        assert any("consumes" in p and "algo2code" in p for p in paragraphs), (
            "README must contain a paragraph that uses both 'consumes' and "
            "'algo2code' to describe the consumer/producer relationship"
        )

        arch_section = _extract_architecture_section(readme)
        assert arch_section, "README must contain a '## Architecture' section"
        assert "PCG" in arch_section, (
            "Architecture section must mention the PCG path landed in Phase 6"
        )

    def test_p6_5_deliverables_present_at_listed_surfaces(self) -> None:
        """P6-5-c2: deliverables present at the surfaces listed in the plan.

        Verifies: each surface listed for P6-5 in
        ``dev/plans/recovery_plan_latex_contract.md`` has the
        documentation deliverable in place.

        Files under test:
          * ``README.md`` — public architecture section mentions
            ``algo2code`` alongside ``mechdsl-core`` and the
            ``LinearSolverInterface`` seam.
          * ``dev/design_docs/11-ALGO2CODE.md`` — names the recovered
            seam (``PCG``, ``LinearSolverInterface``, ``algo2code``,
            ``Algo2CodePCGSolver``) and the canonical-source pointer
            ``PCG_ALGORITHM_LATEX``.
          * ``dev/examples/`` — a README or example docstring mentions
            ``algo2code`` so the seam is reachable from runnable code.

        Acceptance criterion: P6-5-c2.
        """
        # Surface 1 — README architecture section names algo2code.
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        arch_section = _extract_architecture_section(readme)
        assert arch_section, "README must contain a '## Architecture' section"
        assert "algo2code" in arch_section, "README architecture section must name algo2code"

        # Surface 2 — design doc names the full recovered seam.
        design_doc = (_ROOT / "dev" / "design_docs" / "11-ALGO2CODE.md").read_text(encoding="utf-8")
        for needle in (
            "PCG",
            "LinearSolverInterface",
            "algo2code",
            "Algo2CodePCGSolver",
            "PCG_ALGORITHM_LATEX",
        ):
            assert needle in design_doc, (
                f"dev/design_docs/11-ALGO2CODE.md must mention {needle!r} "
                "to document the recovered seam"
            )

        # Surface 3 — examples directory advertises the algo2code seam.
        examples_dir = _ROOT / "dev" / "examples"
        examples_readme = examples_dir / "README.md"
        readme_mentions = examples_readme.is_file() and "algo2code" in examples_readme.read_text(
            encoding="utf-8"
        )
        example_docstring_mentions = any(
            "algo2code" in path.read_text(encoding="utf-8") for path in examples_dir.glob("*.py")
        )
        assert readme_mentions or example_docstring_mentions, (
            "dev/examples/ must advertise the algo2code seam either via a "
            "README.md or via an example docstring"
        )
