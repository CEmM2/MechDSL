"""Headline product story: equation-bearing LaTeX -> Taichi via compile_latex.

This is the canonical fgram first-run example (closure task P7-1). Unlike the
directive-only ``run_compile_latex.py``, the source here is *equation-bearing*:
beyond the mesh/material/boundary directives it declares the physics fields,
the constitutive role of each tensor (``Psi`` = strain energy, ``S`` = PK2
stress), and the weak-form residual. ``compile_latex`` parses those equation
declarations, threads them onto the artifact bundle as a ``latex_semantics``
record, and emits Taichi from the LaTeX-derived ``ProblemIR``.

Everything here goes through the single public facade ``mechdsl.compile_latex``
— no internal constructors — so the example cannot drift from the supported API.

Run with::

    uv run python examples/run_compile_latex_equation.py

See ``dev/reviews/fgram_closure_2026_05.md`` for the grammar-coverage map and
the list of remaining unsupported / deferred constructs.
"""

from __future__ import annotations

from mechdsl import compile_latex

# Equation-bearing LaTeX: directive core PLUS field / constitutive-role /
# weak-form declarations. The compiler understands the equation roles,
# not just a material name.
EQUATION_SOURCE = r"""
% MechDSL headline example -- equation-bearing SVK Hex8 cantilever.
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


def main() -> None:
    bundle = compile_latex(EQUATION_SOURCE, profile="mvp")

    print("compile_latex bundle summary (equation-bearing source):")
    print(f"  element_ir_summary: {bundle.element_ir_summary}")
    print(f"  content_hash:       {bundle.content_hash()}")

    # The LaTeX-derived equation semantics ride on the bundle so emitted
    # Taichi sections are traceable back to the source equation roles.
    semantics = bundle.problem_ir_dict.get("latex_semantics")
    assert semantics is not None, "equation-bearing source must attach latex_semantics"
    roles = {entry["symbol"]: entry["role"] for entry in semantics["constitutive"]}
    print("  LaTeX-derived equation semantics:")
    print(f"    fields:           {semantics['fields']}")
    print(f"    constitutive:     {roles}")
    print(f"    weak_form_label:  {semantics['weak_form_label']}")

    # Proof of generated Taichi: a kernel-bearing module emitted from LaTeX.
    assert "import taichi as ti" in bundle.emitted_source
    assert "@ti.kernel" in bundle.emitted_source
    n_lines = bundle.emitted_source.count("\n") + 1
    print(f"  emitted Taichi:     {n_lines} lines (contains @ti.kernel)")


if __name__ == "__main__":
    main()
