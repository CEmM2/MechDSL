# How it works

This page is for the curious user who wants to understand the machinery before relying
on it. The authoritative, read-only design docs live in the internal `dev/design_docs/`
tree of the private development repository; this is a guided tour.

## The six layers

Each layer owns one subpackage under `packages/mechdsl-core/src/mechdsl/` and one
representation. Information only ever flows downward, through the IRs.

| Layer | Package | Responsibility |
|---|---|---|
| 1 · Frontend | `mechdsl.frontend` | Parse LaTeX + `% mechanics` directives; resolve two-point tensor indices |
| 2 · Symbolic | `mechdsl.symbolic` | Kinematics (F→C→E→J), constitutive evaluation, Voigt contraction |
| 3 · Mechanics IR | `mechdsl.ir` | `ProblemIR` — the semantic centre (formulation, frame, stress measure) |
| 4 · Lowering | `mechdsl.lowering` | Localise ProblemIR → Element IR; extract einsum strings |
| 4b · Einsum optimiser | `mechdsl.codegen.einsum_optimizer` | `opt_einsum` contraction paths + JIT-budget counter |
| 5 · Codegen | `mechdsl.codegen.taichi_printer` | Taichi source emission (sole MVP backend) |
| 6 · Verify | `mechdsl.verify` | Reference comparison, AD oracle, patch tests |

Supporting packages: `mechdsl.solver` (Newton driver + imported linear solver adapter)
and `mechdsl.lib` (the Tier-1 `@ti.func` library and plasticity orchestration).

```text
LaTeX ──▶ SymPy tensors ──▶ ProblemIR ──▶ ElementIR ──▶ EinsumIR ──▶ Taichi
        frontend        symbolic       lowering      optimiser     codegen
```

## IR discipline

Three rules keep the pipeline correct and testable:

1. **All information flows through the three IRs** — Mechanics IR → Element IR → Einsum
   IR. Symbolic expressions never emit backend code directly.
2. **IRs are immutable dataclasses**, validated at construction. A malformed problem
   fails fast at the IR boundary, not deep in codegen.
3. **Unsupported constructs raise explicitly** — with the specific plan phase that will
   add support — instead of silently emitting wrong code.

## Determinism & golden files

`compile_latex` returns a bundle with a `content_hash()`. Identical inputs always produce
an identical hash and identical emitted source. That determinism is what makes the
compiler testable: serialized output bundles are stored as **golden files** under
`packages/mechdsl-core/tests/golden/`, and any change to generated code shows up as a
visible diff. Golden updates require explicit intent — they are never auto-applied.

## Verification { #verification }

Correctness is anchored to hand-written **reference kernels** in
`packages/mechdsl-core/tests/ref/` (e.g. `ref_hex8_elastic.py`, `ref_hex8_plastic.py`),
which are the ground truth. Generated code must match them within the tolerances fixed in
`dev/design_docs/07-CONVENTIONS.md §6`:

- generated vs. reference displacement: max diff `< 1e-10`
- patch test (constant strain): exact reproduction
- Cook's membrane: within 2% of literature
- necking bar: load–displacement within 2% of Simo & Hughes (1998)

An automatic-differentiation oracle (`mechdsl.verify.ad_oracle`) independently checks that
derived stresses/tangents match a numerical derivative of the energy — catching a
mis-derivation that a single load case might hide.

## `mechdsl-core` ↔ `algo2code`

The two packages have a strict consumer/producer relationship: `mechdsl-core` consumes
`algo2code`-generated artifacts; `algo2code` is runtime-free and never imports `mechdsl`.
The seam is the `LinearSolverInterface` protocol in `mechdsl.solver.import_adapter`, which
the Newton driver calls through. See [the algo2code page](../algo2code/index.md) for the full
story, and `dev/design_docs/11-ALGO2CODE.md` for the authoritative reference.

## Where to read more

| Topic | Design doc |
|---|---|
| Document map | `00-OVERVIEW.md` |
| Pipeline structure | `01-ARCHITECTURE.md` |
| LaTeX DSL grammar | `02-LATEX-DSL.md` |
| Symbolic engine | `03-SYMBOLIC-ENGINE.md` |
| Mechanics / Element IR | `04-MECHANICS-IR.md`, `05-ELEMENT-IR.md` |
| Codegen | `06-CODEGEN.md` |
| Conventions (authoritative) | `07-CONVENTIONS.md` |
| Verification matrix | `08-VERIFICATION.md` |
| Einsum optimiser | `09-EINSUM-OPTIMISER.md` |
| Boundaries | `10-BOUNDARIES.md` |
| algo2code | `11-ALGO2CODE.md` |
