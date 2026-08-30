# MechDSL examples

Runnable, self-contained examples that exercise the canonical
`mechdsl-core` compile path. Each script is invoked under `uv run` from
the repository root.

## Inventory

- [Headline product story (equation-bearing LaTeX-first)](#headline-product-story-equation-bearing-latex-first) — `run_compile_latex_equation.py`, `run_compile_latex.py`.
- [Programmatic API examples (advanced / testing aids)](#programmatic-api-examples-advanced--testing-aids) — `elastic_cantilever.py`, `cook_membrane.py`, `necking_bar.py`, `patch_test.py`, `plastic_uniaxial.py`, `gen_meshes.py`, `run_pipeline.py`, `run_elastic_reference.py`.
- [LaTeX-math grammar (post_recovery_plan Phase 4, P4-5)](#latex-math-grammar-post_recovery_plan-phase-4-p4-5) — `svk_latex_math.tex`.
- [`algo2code`-generated PCG seam (opt-in)](#algo2code-generated-pcg-seam-opt-in) — runtime knob, no separate script.

## Headline product story (equation-bearing LaTeX-first)

The MVP-stable contract is LaTeX-driven, and the fgram full-grammar story
is *equation-bearing* LaTeX: a source that declares physics fields, the
constitutive role of each tensor (`Psi` = strain energy, `S` = PK2 stress),
and the weak-form residual — not only a built-in material name. New users
should start here:

| Script | What it shows |
|--------|---------------|
| `run_compile_latex_equation.py` | Equation-bearing LaTeX (field/constitutive/weak_form) -> `mechdsl.compile_latex` -> Taichi, with the LaTeX-derived `latex_semantics` record on the bundle |
| `run_compile_latex.py` | Minimal directive-only LaTeX source -> `mechdsl.compile_latex` -> Taichi-ready bundle |

```bash
uv run python examples/run_compile_latex_equation.py
uv run python examples/run_compile_latex.py
```

Both go through the single public facade `mechdsl.compile_latex`, so they
cannot drift from the supported API. The equation-bearing script is the
fgram closure headline (P7-1); the directive-only script remains the
minimal entry point referenced from the repository
[`README.md`](../../README.md) Quickstart and from
[`dev/plans/recovery_plan_latex_contract.md`](../plans/recovery_plan_latex_contract.md)
P7-3. See [`dev/reviews/fgram_closure_2026_05.md`](../reviews/fgram_closure_2026_05.md)
for the grammar-coverage map.

## Programmatic API examples (advanced / testing aids)

The scripts below construct a `ProblemIR` directly via `build_context()`.
They remain supported (P2-2 mandate) but are demoted to advanced /
testing-aid status: the LaTeX-first script above is the documented
stable story.

| Script | What it shows |
|--------|---------------|
| `elastic_cantilever.py` | SVK Hex8 cantilever via `build_context()` + `compile()` |
| `plastic_uniaxial.py` | J2 power-law uniaxial bar |
| `cook_membrane.py` | Cook's membrane benchmark (mid-tip displacement) |
| `necking_bar.py` | Necking-bar plasticity benchmark |
| `patch_test.py` | Constant-strain patch test |
| `run_pipeline.py` | SVK + J2 end-to-end, writes emitted Taichi source to disk |
| `gen_meshes.py` | Helper that generates the meshes used above |
| `run_elastic_reference.py` | Reference-kernel comparison harness |

LaTeX source inputs live alongside the scripts (`elastic_cantilever.tex`,
`plastic_necking.tex`) and are consumed by the canonical
`run_compile_latex.py` flow.

## LaTeX-math grammar (post_recovery_plan Phase 4, P4-5)

`svk_latex_math.tex` exercises the `nrpylatex` math-grammar integration
landed by post_recovery_plan Phase 4 (P4-1 / P4-2 / P4-3). The file mixes
canonical `% mechanics` directives with `% declare` directives for the
`nrpylatex` parser and a `$...$` indexed-tensor block; the
`mechdsl.frontend.parse_with_math` entry point routes the math block
through `mechdsl.frontend.math_parser` → `mechdsl.symbolic.bridge` and
attaches the resulting `SymbolicNode` map under `context["math"]`.

| Source | What it shows |
|--------|---------------|
| `svk_latex_math.tex` | LaTeX-math integration via `parse_with_math`; two-point `F^{iI}` index distinction |

```bash
uv run python -c "from pathlib import Path; from mechdsl.frontend import parse_with_math; ctx = parse_with_math(Path('examples/svk_latex_math.tex').read_text()); print(list(ctx['math']['tensors'].keys()))"
```

The example deliberately uses a rank-2 copy as the SVK PK1 surrogate;
the closed-form expression depends on `\det F` / `\log J` intrinsics
that `nrpylatex` 1.4.0 does not register, deferred to a later phase.

## `algo2code`-generated PCG seam (opt-in)

The Newton–Raphson driver consumes any `LinearSolverInterface` adapter.
The default is `ScipyCGSolver`; the `algo2code`-derived `Algo2CodePCGSolver`
(verbatim translation of `algo2code.library.pcg.PCG_ALGORITHM_LATEX`,
landed by recovery-plan Phase 6 / P6-1..P6-3) is opt-in:

```python
from mechdsl.solver import select_linear_solver
from mechdsl.solver.newton import newton_solve

solver = select_linear_solver("generated")  # algo2code-derived PCG path
# newton_solve(..., linear_solver=solver)    # opt-in; default stays ScipyCGSolver
```

The examples above keep the default fallback so they remain stable
under CI; swapping in the generated path is a one-line change at the
call site. See
[`dev/design_docs/11-ALGO2CODE.md`](../design_docs/11-ALGO2CODE.md) §1.1
for the seam description and §2.5 for the canonical PCG algpseudocode.
