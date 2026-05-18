# MechDSL

A LaTeX-to-FEM compiler monorepo. Two packages turn LaTeX notation into executable finite element code:

- **mechdsl-core** — LaTeX tensor expressions (with `% mechanics` directives) into Taichi GPU solver code
- **algo2code** — LaTeX algorithm boxes (`algpseudocode`) into executable code (Taichi/NumPy/C)

## Monorepo Structure

This is a **uv workspace** monorepo. Python 3.12 required.

```
packages/
  mechdsl-core/     # FEM compiler (sympy, numpy, taichi, nrpylatex)
  algo2code/        # Algorithm transpiler (zero runtime deps, stdlib only)
dev/
  design_docs/      # Authoritative specs (14 files). If code disagrees, spec wins.
  plans/            # Sprint plans and tracking
.github/workflows/  # CI (lint + test + budget regression)
mvp_concept_demo/   # Historical prototype, not part of the build
```

## Quick Start

```bash
uv sync --all-packages --all-groups --all-extras   # install everything
uv run pre-commit install                           # git hooks (ruff, trailing whitespace)
uv run pytest -m "not slow and not gpu"             # fast test suite (~7s, ~123 tests)
```

**Important**: Always use `uv run` to invoke tools. Never call `python`, `pytest`, `ruff`, or `mypy` directly -- they may resolve to the wrong environment.

## Build & Lint Commands

| Task | Command |
|------|---------|
| Install all deps | `uv sync --all-packages --all-groups --all-extras` |
| Lint (violations) | `uv run ruff check` |
| Lint (format) | `uv run ruff format` |
| Type check (mechdsl) | `uv run mypy packages/mechdsl-core/src/mechdsl/` |
| Type check (algo2code) | `uv run mypy packages/algo2code/src/algo2code/` |
| Add a dependency | `uv add --package mechdsl-core <pkg>` |

## Test Commands

| Task | Command |
|------|---------|
| Fast suite (default) | `uv run pytest -m "not slow and not gpu"` |
| Slow tests only | `uv run pytest -m slow` |
| GPU tests only | `uv run pytest -m gpu` |
| End-to-end tests | `uv run pytest -m e2e` |
| Benchmark tests | `uv run pytest -m benchmark` |
| Budget regression | `uv run pytest packages/mechdsl-core/tests/test_einsum.py -k budget -v` |
| mechdsl-core only | `uv run pytest packages/mechdsl-core/tests/` |
| algo2code only | `uv run pytest packages/algo2code/tests/` |

Pytest uses `--import-mode=importlib` (configured in root `pyproject.toml`).

## Architecture: mechdsl-core

Six-layer compiler pipeline under `packages/mechdsl-core/src/mechdsl/`:

| Layer | Package | Responsibility |
|-------|---------|---------------|
| 1 | `frontend/` | LaTeX parsing, `% mechanics` directives, two-point tensor index resolution |
| 2 | `symbolic/` | Kinematics (F, C, E, J), constitutive evaluation, Voigt contraction |
| 2b | `symbolic/models/` | Constitutive models: `svk.py` (St. Venant-Kirchhoff), `j2_power_law.py` (J2 plasticity) |
| 3 | `ir/` | `ProblemIR` (semantic center) and `ElementIR` schemas -- immutable dataclasses |
| 4 | `lowering/` | FE localisation: ProblemIR to ElementIR, einsum string extraction |
| 4b | `codegen/einsum_optimizer.py` | opt_einsum contraction paths + JIT budget counter |
| 5 | `codegen/taichi_printer.py` | Taichi code generation (sole backend) |
| 6 | `verify/` | Reference comparison, AD oracle, patch tests, convergence studies |

Supporting modules:
- `solver/` -- Newton-Raphson driver, CG/PCG linear solver adapters, mesh I/O, load stepping
- `lib/` -- Tier-1 `@ti.func` library (deformation gradients, matrix ops, PK transforms)

**Compilation flow**: LaTeX --> Frontend Parser --> `ProblemIR` --> Lowering --> `ElementIR` --> Einsum Optimization --> Taichi emission --> `ArtifactBundle`

**Public API**: `from mechdsl import compile` -- takes a `ProblemIR`, returns an `ArtifactBundle`.

## Architecture: algo2code

Pipeline under `packages/algo2code/src/algo2code/`:

```
algo_parser.py --> ast_nodes.py --> expr_parser.py --> type_inference.py --> backends/
```

Backends: `taichi_codegen.py` (MVP), `numpy_codegen.py`, `c_petsc_codegen.py`.

**Public API**: `from algo2code import transpile` -- takes LaTeX source string, returns generated code.

## IR Discipline

All information flows through three explicit IRs:

```
Mechanics IR  -->  Element IR  -->  Einsum IR
```

Rules:
- Never bypass an IR layer. Symbolic expressions do not emit backend code directly.
- IRs are immutable dataclasses. Validation runs at construction time.
- Unsupported constructs must raise with the specific plan phase that adds support.

## Key Conventions

Source of truth: `dev/design_docs/07-CONVENTIONS.md`

| Convention | Rule |
|-----------|------|
| Index naming | Lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed `F_{iI}` = two-point |
| Voigt ordering | `[xx, yy, zz, xy, xz, yz]` with **unscaled shears** (tensorial, not engineering) |
| Sign convention | Tension-positive stress, compression-positive pressure (`p = -m`) |
| JIT budget | Max 512 unrolled lines per `@ti.func`, 2000 per `@ti.kernel`, 5000 absolute ceiling |
| Index partitioning | Physics indices (range <= 6) use `ti.static`; mesh indices (nodes, quads, elements) use runtime loops. Never unroll mesh indices. |

## Key File Locations

| What | Path |
|------|------|
| Workspace config | `pyproject.toml` (root) |
| mechdsl-core config | `packages/mechdsl-core/pyproject.toml` |
| algo2code config | `packages/algo2code/pyproject.toml` |
| Design specs (authoritative) | `dev/design_docs/` (14 files) |
| Conventions spec | `dev/design_docs/07-CONVENTIONS.md` |
| CI pipeline | `.github/workflows/ci.yml` |
| Pre-commit config | `.pre-commit-config.yaml` |
| mechdsl-core source | `packages/mechdsl-core/src/mechdsl/` |
| algo2code source | `packages/algo2code/src/algo2code/` |
| mechdsl-core tests | `packages/mechdsl-core/tests/` (~49 test files) |
| algo2code tests | `packages/algo2code/tests/` (6 test files) |
| Reference kernels | `packages/mechdsl-core/tests/ref/` |
| Golden files | `packages/mechdsl-core/tests/golden/` |

## Testing Infrastructure

- **Reference kernels** (`tests/ref/`): Hand-written ground-truth implementations (`ref_hex8_elastic.py`, `ref_hex8_plastic.py`) for validation.
- **Golden files** (`tests/golden/`): Regression snapshots of generated Taichi code and numerical data (`.py.golden`, `.npz`).
- **Test markers**: `slow` (Taichi compilation), `gpu` (GPU-only), `e2e` (end-to-end pipeline), `audit` (verification audit), `benchmark` (performance regression).
- Every new module must have a corresponding test file in its package's `tests/` directory.

## CI Pipeline

Runs on push/PR to `main` (`.github/workflows/ci.yml`):

1. **lint** -- `ruff check`, `ruff format --check`, `mypy` on both packages
2. **test** -- fast tests for both packages (`-m "not slow and not gpu"`)
3. **slow-tests** -- (PR only) runs if `codegen/` or `solver/` files changed
4. **budget-regression** -- einsum budget tests to catch JIT limit violations

## Dependencies

**mechdsl-core** (runtime):
- sympy >= 1.12, numpy >= 1.24, opt-einsum >= 3.3, taichi >= 1.7, pyyaml >= 6.0
- nrpylatex (git dependency from github.com/SOSOVSKI/nrpylatex)
- Optional (verify group): torch >= 2.0, scipy >= 1.17.0

**algo2code** (runtime): Zero dependencies (stdlib only).

**Dev tools** (shared): pytest, pytest-cov, mypy, ruff, pre-commit.

## Code Style

- Python 3.12, type hints encouraged
- Ruff rules: E, W, F, I (isort), UP, B (bugbear), SIM, TCH, RUF
- Line length: 100
- Ruff excludes: `packages/algo2code/prototypes`, `mvp_concept_demo`

## MVP Scope

**mechdsl-core**: 3D Hex8 elements, Total Lagrangian formulation, convected coordinates, St. Venant-Kirchhoff elasticity + J2 plasticity with power-law hardening. Taichi is the sole backend. Linear solver is imported, not reimplemented.

**algo2code**: PCG solver transpilation from algpseudocode to Taichi. Consumed by mechdsl-core's Newton-Raphson driver.

## Known Limitations

The pure-NumPy reference solver (unpreconditioned CG with finite-difference tangent) is computationally infeasible beyond approximately 50 nodes. Meshes like 40x8x4 cantilever or 16^3 MMS cannot solve in reasonable time. This is a reference implementation limitation, not a limitation of the generated Taichi code.
