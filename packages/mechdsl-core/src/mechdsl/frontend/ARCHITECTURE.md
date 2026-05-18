# Frontend Architecture — Layer 1

This document records the split between **parser of record** and **adapter /
normalizer / validator** that recovery-plan Phase 2 (R1.3 / canonical
task `P2-3`) makes explicit. The split is design-doc consistent with
`dev/design_docs/02-LATEX-DSL.md` and `dev/design_docs/PLAN-A.md §A3`.

## Two responsibilities, two homes

The frontend handles two genuinely different jobs:

1. **Math grammar** — parsing user-defined strain-energy expressions
   (`\Psi = ...`), index gymnastics, and tensor-valued LaTeX expressions
   in general. This is hard, requires a real LaTeX-math parser, and is
   the work of the [NRPyLaTeX](https://nrpylatex.readthedocs.io/) library
   (already declared as a dependency in `pyproject.toml`).
2. **Directive parsing + normalization + validation** — processing
   `% mechanics` *directives* (configuration knobs like `cell hex8`,
   `material svk --E 200e3 --nu 0.3`, `boundary fix --type dirichlet`),
   normalizing them into the context-dict schema, validating that the
   result is in the MVP-supported subset, and resolving two-point tensor
   index families. This is bespoke, deterministic, and lives in this
   package.

The recovered contract assigns these responsibilities cleanly:

| Layer | Owner | What it does |
|-------|-------|--------------|
| Math grammar (`\Psi = …`) | **NRPyLaTeX** (parser of record) | Tokenizes and parses user-defined strain-energy expressions. Currently wired in `pyproject.toml` but not yet imported under `src/`; the recovery plan defers actual integration to a follow-up task within Phase 2 (R2 + onward). MVP constitutive models (SVK, J2 power-law) are hardcoded in the symbolic layer, so this surface is not yet on the critical path. |
| `% mechanics` directives | `mechdsl.frontend.parser` | Scans LaTeX for `% mechanics …` lines, dispatches to per-directive handlers, returns a context dict. |
| Normalization | `mechdsl.frontend.directives` | Per-directive handlers that translate raw directive arguments into the canonical context-dict schema (booleans, lists, scalars, etc.). |
| Validation | `mechdsl.frontend.build_context` (in `__init__.py`) | Asserts the context dict falls in the MVP-supported subset. Out-of-subset constructs raise `UnsupportedError` with a Plan B phase pointer. |
| Index resolution | `mechdsl.frontend.two_point` | Resolves two-point tensor index families (lowercase = spatial, uppercase = material) and detects mixed-tier index errors. |

## Why both halves stay in this package today

Even though NRPyLaTeX is the *parser of record* for math grammar, the
**adapter** it would live behind has not been written yet. The MVP path
intentionally avoids parsing `\Psi`-style expressions at all, because the
two MVP constitutive models (SVK and J2 power-law) are hardcoded in the
symbolic engine. So today's frontend is exactly the directive parser
plus normalization plus validation, and that is correct.

The placeholder for the math-grammar adapter is intentionally absent:
the recovery plan's `P2-1` (canonical façade) and the broader `R1`
phase land first; the actual nrpylatex integration moves later, when
there is a real motivating user expression.

## Pointers

- The MVP-stable canonical entry point is `mechdsl.compile_latex` (see
  `mechdsl/__init__.py` and the README Quickstart).
- The directive grammar reference is `dev/design_docs/02-LATEX-DSL.md`.
- The recovery plan that introduces this split is
  `dev/plans/recovery_plan_latex_contract.md` Phase 2 (R1).
