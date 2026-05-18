# Phase 4 Context Summary: NRPyLaTeX math grammar integration

**Plan:** `dev/plans/post_recovery_plan.md`

## Conventions

- **Index convention enforcement** (07-CONVENTIONS): lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed `F_{iI}` = two-point tensor. nrpylatex AST is post-processed to enforce this before symbolic ingestion.
- **Math block delimiter:** `$...$`. Directive-only LaTeX (no `$...$`) skips the math parser entirely.
- **Reuse:** `nrpylatex` is already declared in pyproject.toml. No dependency-management work — only import wiring.

## Key Principles

- **IR discipline holds:** math expressions land in the symbolic layer, which feeds the IR. The math parser does not emit backend code.
- **Bridge isolates conversion:** `symbolic/bridge.py` is the only module that knows about nrpylatex AST shapes. Failure modes raise with explicit "unsupported NRPyLaTeX node" pointing at this phase.
- **Performance: parse only when needed.** Skip the math parser entirely if the input has no `$...$` blocks (plan line 226-227).

## Pre-resolved Design Decisions

- Math parser entry point: `packages/mechdsl-core/src/mechdsl/frontend/math_parser.py`.
- Bridge module: `packages/mechdsl-core/src/mechdsl/symbolic/bridge.py` (extend if exists; otherwise create).
- Round-trip test covers SVK PK1, J2 yield function, two-point tensor `F_{iI}`.
- Example file: `dev/examples/svk_latex_math.tex` listed under README ## Inventory.

## Allowed Deviations

- The plan permits in-scope extension of the bridge to cover any nrpylatex node needed for the three round-trip cases. If a node is unreachable from those three, defer.

## Downstream Impact

- Subsequent plans can write LaTeX-math-only constitutive expressions without `% mechanics constitutive` directives.
- Provides test coverage for nrpylatex integration that future updates to nrpylatex versions will need to satisfy.
