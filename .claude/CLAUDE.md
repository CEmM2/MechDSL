# MechDSL Monorepo — Project Instructions

## Monorepo structure

This is a **uv workspace** monorepo with two packages:

| Package | Path | Purpose |
|---------|------|---------|
| `mechdsl-core` | `packages/mechdsl-core/` | LaTeX tensor expressions → FEM solver code (Taichi) |
| `algo2code` | `packages/algo2code/` | LaTeX algorithm boxes (algpseudocode) → executable code |

Shared resources at root: `dev/design_docs/` (specs), `.claude/` (rules/agents/skills), `.github/` (CI).

`mvp_concept_demo/` contains an early concept prototype (notebook + script) — historical reference, not part of the build.

## Architecture (mechdsl-core)

The FEM compiler pipeline has six layers, each owning a subpackage under `packages/mechdsl-core/src/mechdsl/`:

| Layer | Package | Responsibility |
|-------|---------|---------------|
| 1 | `mechdsl.frontend` | LaTeX parsing, `% mechanics` directives, two-point tensor index resolution |
| 2 | `mechdsl.symbolic` | Kinematics (F→C→E→J), constitutive evaluation, Voigt contraction |
| 3 | `mechdsl.ir` | Mechanics IR (`ProblemIR`) — semantic center — and Element IR schemas |
| 4 | `mechdsl.lowering` | FE localisation: ProblemIR → ElementIR, einsum string extraction |
| 4b | `mechdsl.codegen.einsum_optimizer` | opt_einsum contraction paths + JIT budget counter |
| 5 | `mechdsl.codegen.taichi_printer` | Taichi code generation (sole backend until v1.0) |
| 6 | `mechdsl.verify` | Verification harness: reference comparison, AD oracle, patch tests |

Supporting packages: `mechdsl.solver` (Newton driver + imported linear solver adapter), `mechdsl.lib` (Tier 1 `@ti.func` library).

## Architecture (algo2code)

Pipeline under `packages/algo2code/src/algo2code/`: `algo_parser` → `expr_parser` → `type_inference` → `backends/taichi_codegen`. Zero runtime dependencies (stdlib only). See `dev/design_docs/11-ALGO2CODE.md`.

## Quick start

```bash
uv sync --all-packages --all-groups --all-extras  # install all deps (both packages)
uv run pre-commit install                    # set up git hooks
uv run pytest -m "not slow and not gpu"      # fast test suite
```

## Authoritative sources

- The `dev/design_docs/` directory is the single source of truth for all design decisions.
- `dev/design_docs/07-CONVENTIONS.md` is the authority on all tensor, Voigt, sign, and tolerance conventions. If code or comments disagree with 07-CONVENTIONS, the spec wins.

## Key conventions (from @dev/design_docs/07-CONVENTIONS.md)

- **Index convention**: lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material; mixed `F_{iI}` = two-point tensor.
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` with **unscaled shears** (tensorial Voigt, not engineering Voigt).
- **Sign**: tension-positive stress, compression-positive pressure (`p = -m`).
- **JIT budget**: max 512 unrolled lines per `@ti.func`, 2000 per `@ti.kernel`, 5000 absolute ceiling.
- **Index partitioning**: physics indices (range ≤ 6) → `ti.static`; mesh indices (nodes, quads, elements) → runtime loops. Never unroll mesh indices.

## IR discipline

- All information flows through three explicit IRs: **Mechanics IR → Element IR → Einsum IR**.
- Never bypass an IR layer. Symbolic expressions do not emit backend code directly.
- IRs are immutable dataclasses. Validation runs at construction time.
- Unsupported constructs must raise with the specific plan phase that adds support (e.g. "Updated Lagrangian is planned for Plan B phase B1").

## Testing requirements

- Every new module must have a corresponding test file in its package's `tests/` directory.
- mechdsl-core: handwritten reference kernels in `packages/mechdsl-core/tests/ref/`, golden files in `packages/mechdsl-core/tests/golden/`.
- Use `pytest.mark.slow` for Taichi compilation tests, `pytest.mark.gpu` for GPU tests, `pytest.mark.e2e` for end-to-end pipeline tests.

## Tooling — uv

This project uses **uv** as the package manager. Never invoke `python`, `pytest`, `ruff`, or `mypy` directly — they may not be on PATH or may pick up the wrong environment.

- **Run project code**: `uv run python ...`
- **Run project-scoped tools**: `uv run pytest ...`, `uv run ruff ...`, `uv run mypy ...`
- **Run globally-installed tools**: `uvx ruff ...`, `uvx pytest ...` (only if the tool is installed as a uv tool)
- **Install dependencies**: `uv sync --all-packages --all-groups --all-extras` (not `pip install`)
- **Add a dependency**: `uv add --package mechdsl-core <pkg>` or `uv add --package algo2code <pkg>`

Prefer `uv run` over `uvx` when working inside the project — it uses the project's locked environment.

## Code style

- Python 3.12, type hints encouraged.
- Formatting and linting: `uv run ruff check` and `uv run ruff format` (configured in root pyproject.toml).
- Type checking: `uv run mypy packages/mechdsl-core/src/mechdsl/` and `uv run mypy packages/algo2code/src/algo2code/`.
- Run `uv run pytest -m "not slow and not gpu"` for fast feedback during development.

## MVP scope

**mechdsl-core**: 3D Hex8, Total Lagrangian, convected coordinates, St. Venant-Kirchhoff elasticity + J2 plasticity with power-law hardening. Taichi is the sole backend. Linear solver is imported, not reimplemented.

**algo2code**: PCG solver transpilation from algpseudocode → Taichi. Consumed by mechdsl-core's Newton-Raphson driver.
