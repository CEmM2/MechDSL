# Browser workbench

[`mechdsl-workbench`](https://github.com/CEmM2/mechdsl-workbench) is a companion
browser application for MechDSL: **LaTeX on the left, the compiled mechanics or
transpiled algorithm on the right**. It is the fastest way to try the language before
committing to the pipeline — no scripts, no `ProblemIR`, no local Taichi wrangling.

It lives in its own repository, is published to PyPI, and is MIT-licensed like the rest
of the toolchain.

```text
┌─────────────────────────────────────────────────────────────────┐
│ Mechanics | Algorithm        Example ▾            Compile/Run   │
├─────────────────────────────────────────────────────────────────┤
│ LaTeX source                                                    │
│                                                                 │
│ % mechanics ...        or        % algorithm pcg                │
│                                  \begin{algorithmic} ...        │
├─────────────────────────────────────────────────────────────────┤
│ Preview | Generated Taichi | Translation View | Diagnostics     │
└─────────────────────────────────────────────────────────────────┘
```

## Install and run

```bash
pip install "mechdsl-workbench[mechdsl]"   # workbench + the MechDSL engine, one command
mechdsl-workbench
```

Then open <http://127.0.0.1:8000>.

The `[mechdsl]` extra pulls `mechdsl-core[verify]` and `algo2code` from PyPI — the full
engine including Taichi, so expect a large download. If you already have an engine
installed (or want to point at a source checkout), take the workbench alone:

```bash
pip install mechdsl-workbench              # bring your own mechdsl-core
```

!!! warning "Python 3.12"
    The workbench pins `requires-python = ">=3.12,<3.13"`, which is narrower than the
    `>=3.11,<3.14` range the three monorepo packages accept. Install it into a 3.12
    environment.

Common flags and the full environment-variable table (bind host and port, compile
timeout, concurrency and payload limits, MathJax source) are documented in the
[workbench README](https://github.com/CEmM2/mechdsl-workbench#run-options):

```bash
mechdsl-workbench --host 127.0.0.1 --port 8000
mechdsl-workbench --reload
```

A Docker image is available too — `docker compose up` from the workbench repository.

## The two modes

### Mechanics mode

Compile a `% mechanics` document through
[`compile_from_sources()`](reference/architecture.md#integration-facade):

- line-numbered LaTeX editor, with an optional separate constitutive-energy source;
- MathJax preview and `% mechanics` directive cards;
- the generated Taichi source;
- the public Element IR summary, the semantic content hash, and whether a derived
  energy was present;
- bundled SVK Hex8, equation-bearing Hex8, and Tet4 examples.

### Algorithm mode

Transpile a LaTeX `algorithmic` block through `transpile_algorithm()`:

- `% algorithm`, `% backend`, `% args`, and `% type` contract preview;
- the generated Taichi/Python source;
- entry-point name, line count, backend, and Python-validity result;
- bundled J2 radial-return and PCG examples.

Both modes share an explicit action button (or `Ctrl+Enter` / `Cmd+Enter`), copy and
download actions for the source and the generated `.py`, and browser-local drafts kept
separately per mode.

## How it talks to the compiler

The dependency direction is strictly one-way, and checked in the workbench's CI:

```text
mechdsl-workbench  ->  mechdsl.integration  ->  mechdsl-core / algo2code
MechDSL            -X->  mechdsl-workbench
```

The workbench only ever calls the five entry points of the `mechdsl.integration`
façade — the stable, machine-readable Tier-1 surface. It never imports `algo2code`
directly and never reaches into the parser, IR, lowering, symbolic, or codegen
internals. That is deliberate: the workbench is the reference consumer that proves the
public integration surface is sufficient to build a real application on.

!!! note "Nothing generated is executed"
    Each translation runs in a short-lived worker subprocess with a hard timeout, and
    the server terminates it if it overruns. The workbench **does not execute the code
    it emits** — the preview is presentational, and the Translation View reports only
    what the public integration result actually returned.

## Where to next

- [Installation](installation.md) — the full PyPI and source matrix for every package.
- [LaTeX directive reference](mechdsl-core/latex-directives.md) — what to type into the
  mechanics pane.
- [algo2code usage](algo2code/usage.md) — what to type into the algorithm pane.
