# FAQ & troubleshooting

## Frequently asked

### How do I install it? Is it on PyPI?

Yes — every package is published on PyPI under the MIT license, so `pip install` is the
normal way in:

```bash
pip install mechdsl-core                   # the compiler, Taichi-free
pip install "mechdsl-core[verify]"         # the full engine: run and verify solves
pip install algo2code                      # the transpiler alone, stdlib-only
pip install ti-runtime                     # the Taichi runtime alone
pip install "mechdsl-workbench[mechdsl]"   # the browser workbench plus the engine
```

You do **not** need to clone the repository or install `uv` unless you want the
runnable `examples/` tree, the test suite, or to contribute. Full matrix on the
[Installation](../installation.md) page.

### Why does the base install not include Taichi?

Because only one entry point needs it. Emission, transpilation, `capabilities()`, and
`model_catalog()` are proven Taichi-free by the test suite; only
`mechdsl.integration.verify()` imports Taichi, and it does so lazily at call time. That
lets downstream consumers depend on `mechdsl-core` for code generation without pulling
Taichi's ~170 MB into their dependency closure. `pip install "mechdsl-core[verify]"`
when you actually want to run solves.

### Which Python version do I need?

`mechdsl-core`, `algo2code`, and `ti-runtime` accept **Python 3.11–3.13**
(`>=3.11,<3.14`). The `mechdsl-workbench` companion is narrower and pins **Python 3.12**
(`>=3.12,<3.13`).

### Can I try it without writing any code?

Yes. `pip install "mechdsl-workbench[mechdsl]"`, run `mechdsl-workbench`, and open
<http://127.0.0.1:8000> — LaTeX in the left pane, generated Taichi in the right. See
[the workbench page](../workbench.md).

### Is this a replacement for Abaqus / ANSYS / a full FE package?

No. MechDSL is a **compiler** that generates solver code from a LaTeX description of a
problem. It targets research workflows where the constitutive model *is* the deliverable
and you want the code to provably match the math, not a turnkey commercial solver.

### Do I have to write LaTeX?

The canonical path is LaTeX-driven, and it's preferred for everything user-facing — the
whole point is that your paper source and your simulation source are the same file. But
there's also a programmatic API (`build_context(...)` → `compile(ProblemIR(...))`) for
tests and for embedding the compiler in another tool. See
[Core concepts → two ways in](../mechdsl-core/concepts.md#two-ways-in).

### Does the `.tex` still render as a normal PDF?

Yes. The `% mechanics` directives are LaTeX comments — `pdflatex` ignores them. The same
file typesets as a paper and compiles as a simulation.

### What's the difference between MVP-stable and experimental?

`MVP-stable` features (Hex8, Total Lagrangian, SVK, J2 power-law, Taichi) have a stable
API and pass tests on every commit. `experimental` features (MFEM/MOOSE backends, the
non-MVP materials and elements) are preserved in-tree but provisional. Full policy in
[Core concepts → support tiers](../mechdsl-core/concepts.md#support-tiers).

### Which backend does it emit?

Taichi, which runs on CPU and GPU. MFEM (C++) and MOOSE backends exist but are
experimental. Until v1.0, Taichi is the sole stable target.

### Can I add my own constitutive model?

Yes — two routes depending on the model class:

- **Hyperelastic (has an energy Ψ):** write Ψ in LaTeX and use the
  `constitutive --strain_energy` directive. The compiler differentiates it for you.
- **Dissipative (return-mapping):** author the scalar return-map as `algpseudocode`,
  transpile via [algo2code](../algo2code/index.md), and add a Python orchestration wrapper.

See [Constitutive models → adding your own](../mechdsl-core/constitutive-models.md#adding-your-own-model).

### Why is plasticity split between a `.tex` algorithm and Python?

The transpiled `algpseudocode` is the **scalar** return-mapping loop (solve for the
plastic multiplier). The **tensor** algebra — deviatoric split, von Mises, back-stress
update, algorithmic tangent — lives in a Python orchestration wrapper. This keeps the
algorithm identical to the published algorithm while letting the tensor bookkeeping use
numpy. See [the algo2code page](../algo2code/usage.md#how-the-j2-family-is-wired-into-the-solver).

---

## Troubleshooting

### `command not found` / wrong package versions

**In a source checkout:** you're probably calling `python`/`pytest`/`ruff` directly.
Always prefix with `uv run`. If the environment looks stale, re-sync:

```bash
uv sync --all-packages --all-groups --all-extras
```

**With a `pip install`ed MechDSL:** check you're in the environment you installed into
(`python -c "import mechdsl; print(mechdsl.__file__)"`) and that the interpreter is
3.11–3.13. A `pip install` puts MechDSL in whatever environment `pip` points at, so a
virtualenv you forgot to activate is the usual culprit.

### `ModuleNotFoundError: No module named 'taichi'`

Expected on the base install — it is deliberately Taichi-free. Anything that *runs*
generated code (`mechdsl.integration.verify()`, the solver path, the `slow`/`gpu` tests)
needs the full engine:

```bash
pip install "mechdsl-core[verify]"
```

### A construct raises "planned in phase ..."

That's intentional. Unsupported constructs raise explicitly with the plan phase that adds
support, rather than emitting wrong code. Check the message for the phase reference; the
feature is on the roadmap, not broken.

### My LaTeX directive isn't taking effect

- Directives must be on their **own line** and start with `% mechanics`.
- They're processed **in order** — a directive that references a symbol must come after
  the one that defines it.
- Use the syntax from the [directive reference](../mechdsl-core/latex-directives.md), which mirrors the
  runnable inputs in `examples/`. The design-doc grammar in `02-LATEX-DSL.md` includes
  planned directives that the current `compile_latex` path may not yet consume.

### Generated code changed unexpectedly / a golden test failed

Generated output is deterministic and pinned by golden files. A golden-test diff means
the emitted code changed. If the change is intentional, regenerate the goldens **with
explicit intent** (they're never auto-updated); if not, the diff is showing you a real
regression.

### Tests are slow

Use the fast tier during development:

```bash
uv run pytest -m "not slow and not gpu" -q
```

`slow` tests involve Taichi JIT compilation; `gpu` tests need a GPU; `e2e` tests run the
whole pipeline.

---

## Building these docs locally

```bash
uv sync --group docs
uv run mkdocs serve     # live-reload preview at http://127.0.0.1:8000
uv run mkdocs build     # static site into ./site
```

## Still stuck?

- The authoritative specs live in the internal `dev/design_docs/` tree of the
  private development repository.
- Open an issue at <https://github.com/CEmM2/MechDSL/issues>.
