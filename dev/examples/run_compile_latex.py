"""Canonical first-run example: LaTeX source -> Taichi via compile_latex.

This is the MVP-stable entry point recommended for new users. The script
embeds a small ``% mechanics`` LaTeX source string and forwards it to the
canonical ``mechdsl.compile_latex`` facade, which parses the directives,
adapts them to a ``ProblemIR``, and runs localisation, einsum planning,
and Taichi emission.

Run with::

    uv run python dev/examples/run_compile_latex.py

The programmatic ``build_context()`` / direct ``ProblemIR`` examples in
this directory remain available as advanced/testing aids; LaTeX-first is
the documented stable story (recovery-plan P7-3).
"""

from __future__ import annotations

from mechdsl import compile_latex

LATEX_SOURCE = r"""
% MechDSL canonical first-run example -- elastic cantilever (SVK Hex8).
% mechanics dim 3
% mechanics cell hex8
% mechanics formulation total_lagrangian
% mechanics material svk --E 200e3 --nu 0.3
% mechanics boundary fix --type dirichlet --value 0 --components 0 1 2
% mechanics boundary load --type neumann --traction "0 0 -1000"
"""


def main() -> None:
    bundle = compile_latex(LATEX_SOURCE, profile="mvp")
    print("compile_latex bundle summary:")
    print(f"  element_ir_summary: {bundle.element_ir_summary}")
    print(f"  content_hash: {bundle.content_hash()}")


if __name__ == "__main__":
    main()
