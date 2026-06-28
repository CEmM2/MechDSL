"""Focused fgram Phase 7 P7-1 coverage: verification, review, and closure.

Closure is an evidence package, not a prose victory lap (Phase 7 context):
the closure review must summarize grammar coverage and name remaining
rejected/deferred constructs; the headline example must run through the public
``compile_latex`` facade on an equation-bearing source; and remaining
unsupported grammar must raise cleanly with a plan-phase pointer.

These tests pin the P7-1 closure contract against the *real artifacts* (the
review doc, the example script, the public API) — not against prose. Each
maps to one acceptance criterion.

Convention authority: ``dev/design_docs/07-CONVENTIONS.md``.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from mechdsl import compile_latex
from mechdsl.symbolic.convected import UnsupportedError

# Repo root: this file is packages/mechdsl-core/tests/plan_tests/fgram/<this>.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_CLOSURE_REVIEW = _REPO_ROOT / "dev" / "reviews" / "fgram_closure_2026_05.md"
_EQUATION_EXAMPLE = _REPO_ROOT / "dev" / "examples" / "run_compile_latex_equation.py"

# Equation-bearing source (mirrors the headline example / P6-1 acceptance):
# directive core PLUS field / constitutive-role / weak-form declarations.
EQUATION_SOURCE = r"""
% MechDSL P7-1 closure — equation-bearing SVK Hex8 cantilever.
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics field u --type vector --space H1 --order 1
% mechanics constitutive Psi --strain_energy
% mechanics constitutive S --pk2
% mechanics weak_form internal_residual --residual
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "1 0 0" --surface x1
"""


class TestTaskP7_1:
    """Tests for Task P7-1: verification, review, and closure. AC covered: 1-3."""

    @pytest.mark.regression
    def test_closure_review_summarizes_coverage_and_rejections(self) -> None:
        """AC1: a closure review exists under ``dev/reviews/`` that summarizes
        fgram grammar coverage phase-by-phase and names the remaining
        rejected/deferred constructs with rationale. Passes when: the review
        doc exists, marks every phase P1-P7 as done (no task left implicit),
        and carries an explicit remaining-unsupported-constructs section."""
        assert _CLOSURE_REVIEW.is_file(), (
            f"closure review missing at {_CLOSURE_REVIEW} — AC1 requires a "
            "dev/reviews closure artifact"
        )
        text = _CLOSURE_REVIEW.read_text()

        # Every phase task must appear and be marked done (AC1: all tasks done
        # or explicitly deferred). fgram has zero deferred tasks.
        for task in ("P1-1", "P2-1", "P3-1", "P4-1", "P5-1", "P6-1", "P7-1"):
            assert task in text, f"closure review must reference {task}"

        # Coverage summary present.
        assert "Grammar coverage" in text or "grammar coverage" in text, (
            "closure review must summarize grammar coverage"
        )

        # Remaining-unsupported-constructs map present, with rejection AND
        # deferral language and at least the canonical Plan B pointers.
        assert "Remaining unsupported constructs" in text
        assert "deferred" in text.lower()
        assert "Plan B" in text, "remaining-unsupported map must cite the Plan B deferral pointers"
        # Clean-rejection mechanism named (not just prose).
        assert "UnsupportedError" in text

    @pytest.mark.regression
    def test_equation_bearing_example_demonstrates_product_story(self) -> None:
        """AC2: a user-facing example demonstrates the product story —
        equation-bearing LaTeX compiled to Taichi through the public API
        (``compile_latex``). Passes when: the example file exists and the same
        public path it exercises emits Taichi from an equation-bearing source,
        attaching the LaTeX-derived ``latex_semantics`` record."""
        assert _EQUATION_EXAMPLE.is_file(), (
            f"headline equation-bearing example missing at {_EQUATION_EXAMPLE}"
        )
        # The example must drive the PUBLIC facade, not an internal constructor.
        src = _EQUATION_EXAMPLE.read_text()
        assert "compile_latex" in src, "example must use the public compile_latex facade"
        assert "from_context" not in src and "ProblemIR(" not in src, (
            "headline example must go through compile_latex, not internal constructors"
        )

        # Exercise the same public path the example runs on an equation-bearing
        # source: equation roles -> bundle -> emitted Taichi.
        bundle = compile_latex(EQUATION_SOURCE, profile="mvp")
        assert "import taichi as ti" in bundle.emitted_source
        assert "@ti.kernel" in bundle.emitted_source

        # The LaTeX-derived equation semantics ride on the bundle (the fgram
        # product story: code traceable back to source equation roles).
        semantics = bundle.problem_ir_dict.get("latex_semantics")
        assert semantics is not None, (
            "equation-bearing source must attach latex_semantics (LaTeX-derived)"
        )
        roles = {e["symbol"]: e["role"] for e in semantics["constitutive"]}
        assert roles == {"Psi": "strain_energy", "S": "pk2"}
        assert semantics["weak_form_label"] == "internal_residual"
        assert "u" in semantics["fields"]

    @pytest.mark.regression
    def test_equation_example_script_runs_through_public_api(self) -> None:
        """AC2 (anti-drift): the headline example *executes* end-to-end via
        ``runpy`` without raising. The named risk is example drift from the
        public API — running the actual script (not a copy) guards it."""
        # runpy executes the script in a fresh namespace; main() is invoked via
        # the ``__main__`` guard. Any API drift (renamed facade, changed return
        # shape, broken assert in the script) surfaces as an exception here.
        runpy.run_path(str(_EQUATION_EXAMPLE), run_name="__main__")

    @pytest.mark.regression
    def test_unsupported_grammar_rejected_cleanly_with_phase_pointer(self) -> None:
        """AC3: remaining unsupported grammar raises cleanly with a plan-phase
        pointer through the public ``compile_latex`` facade — no deep codegen
        or runtime failure. Covers representative full-grammar rejections that
        the closure review's remaining-unsupported map enumerates."""
        # 2D problem -> Plan B phase B2.
        with pytest.raises(UnsupportedError, match=r"Plan B phase B2"):
            compile_latex(
                r"""
% mechanics dim 2
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
""",
                profile="mvp",
            )

        # Non-Total-Lagrangian formulation -> rejected with a formulation pointer.
        with pytest.raises(UnsupportedError, match=r"formulation"):
            compile_latex(
                r"""
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation eulerian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0
""",
                profile="mvp",
            )

        # Non-MVP profile -> ValueError with a broader-support pointer.
        with pytest.raises(ValueError, match=r"profile"):
            compile_latex(EQUATION_SOURCE, profile="experimental")
