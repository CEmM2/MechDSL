# Core concepts

A short tour of the ideas that make MechDSL different from a hand-written FEM code.

## 1. LaTeX is the source of truth

A MechDSL input is a **dual-use document**: it renders through `pdflatex` as a normal
paper *and* compiles to a solver. The `% mechanics` directives are LaTeX comments, so
they're invisible to the typesetter and meaningful to the compiler.

The consequence is the project's guiding principle:

> **Derive models from LaTeX; don't hand-code what the compiler should generate.**

When you write a strain-energy function Ψ in LaTeX, the compiler differentiates it to
produce the second Piola–Kirchhoff stress **S = ∂Ψ/∂E** and the material tangent
**C = ∂²Ψ/∂E²**. You never transcribe those derivatives into a kernel by hand — that's
exactly where sign errors and Voigt-ordering bugs creep in.

## 2. The six-layer pipeline

Compilation flows through six layers, each owning one responsibility and one
intermediate representation:

```text
LaTeX source
   │  Layer 1 · Frontend       parse % mechanics directives, two-point tensor indices
   ▼
SymPy symbolic tensors
   │  Layer 2 · Symbolic       kinematics F→C→E→J, constitutive eval, Voigt contraction
   ▼
Mechanics IR  (ProblemIR)      the semantic centre — formulation, frame, stress measure
   │  Layer 3
   ▼
Element IR                     localisation: element metadata + einsum strings (Hex8…)
   │  Layer 4
   ▼
Einsum IR                      contraction-family plans + JIT-budget-aware optimisation
   │  Layer 4b / 5
   ▼
Taichi solver code             Layer 6 · deterministic source emission
```

Two rules keep the layers honest:

- **Never bypass an IR.** Symbolic expressions do not emit backend code directly;
  everything flows Mechanics IR → Element IR → Einsum IR.
- **IRs are immutable** dataclasses, validated at construction time. Unsupported
  constructs raise with the specific plan phase that will add support, rather than
  silently producing wrong code.

See [How it works](../reference/architecture.md) for the per-layer detail and links to the
authoritative design docs.

## 3. Two ways in: LaTeX façade vs. programmatic API { #two-ways-in }

| Path | When to use | Entry point |
|---|---|---|
| **LaTeX façade** (canonical, MVP-stable) | Documentation, examples, production | `compile_latex(source)` |
| **Programmatic API** (secondary) | Tests, embedding the compiler in another tool | `build_context(...)` → `compile(ProblemIR(...))` |

The LaTeX path is preferred everywhere user-facing. The programmatic path exists so you
can construct a `ProblemIR` directly without a parser round-trip — handy in tests — but
it is explicitly a secondary contract surface.

## 4. Hyperelastic vs. dissipative models

The derivation strategy depends on the model class — this matters when you add your own:

- **Hyperelastic models** (SVK, Neo-Hookean, Mooney-Rivlin, Ogden, HGO) have a stored
  energy Ψ. Stress and tangent come from `sympy.diff` of Ψ. This is the "derive from
  LaTeX" path.
- **Dissipative models** (J2 plasticity, viscoplasticity, damage) have **no** usable
  stored energy for the stress. Their stress and the *algorithmic consistent tangent*
  come from a **return-mapping algorithm**, not from differentiating an energy. Those
  algorithms are authored as `algpseudocode` and transpiled by
  [algo2code](../algo2code/index.md). Never force a strain-energy formulation onto a dissipative
  model.

## 5. Conventions are enforced, not assumed { #conventions }

Every tensor, Voigt, sign, and tolerance choice is fixed in one authoritative document
(`dev/design_docs/07-CONVENTIONS.md`). The highlights:

- **Indices:** lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed
  `F_{iI}` = two-point tensor.
- **Voigt ordering:** `[xx, yy, zz, xy, xz, yz]` with **unscaled shears** (tensorial
  Voigt, not engineering Voigt).
- **Sign:** tension-positive stress; compression-positive pressure (`p = -m`).
- **JIT budget:** ≤ 512 unrolled lines per `@ti.func`, ≤ 2000 per `@ti.kernel`.

Generated code is checked against hand-written reference kernels to within the
tolerances in the spec — so a convention slip fails a test rather than shipping.

## 6. Support tiers { #support-tiers }

Every public feature is one of two tiers:

- **`MVP-stable`** — the canonical LaTeX compile path: Hex8, Total Lagrangian,
  convected coordinates, SVK elasticity, J2 power-law plasticity, and the Taichi
  backend. Stable public API, passing tests on every commit to `main`.
- **`experimental`** — preserved in-tree but provisional: MFEM/MOOSE backends, explicit
  dynamics, the non-MVP materials (Mooney-Rivlin, Ogden, HGO, viscoplasticity, damage),
  and the non-canonical elements (Hex8-R, Hex20, Tet4, Tet10). Available to use, but may
  shift, lose tests, or be deprecated without a release note.

Experimental scope is never deleted — it's *labeled*, so the canonical story stays
unambiguous. When you build on an experimental feature, you're doing so knowing the
contract is provisional.
