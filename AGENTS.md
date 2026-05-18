# MechDSL — Agent Instructions

## Tooling

This project uses **uv** as its sole package manager. Never invoke `python`, `pytest`, `ruff`, or `mypy` directly — always prefix with `uv run`.

## Lint

```bash
uv run ruff check packages/
uv run ruff format --check packages/
uv run mypy packages/mechdsl-core/src/mechdsl/
uv run mypy packages/algo2code/src/algo2code/
```

Auto-fix lint issues:

```bash
uv run ruff check --fix packages/
uv run ruff format packages/
```

## Test

Fast tests (no GPU, no Taichi compilation):

```bash
uv run pytest -m "not slow and not gpu" --tb=short -q
```

Full test suite:

```bash
uv run pytest --tb=short -q
```

## Monorepo structure

| Package | Path | Purpose |
|---------|------|---------|
| `mechdsl-core` | `packages/mechdsl-core/` | LaTeX tensor expressions → FEM solver code (Taichi) |
| `algo2code` | `packages/algo2code/` | LaTeX algorithm boxes (algpseudocode) → executable code |

## Key conventions

- **Design docs are read-only**: `dev/design_docs/` is the single source of truth. Do not modify these files.
- **IR discipline**: All information flows through Mechanics IR → Element IR → Einsum IR. Never bypass a layer.
- **IRs are immutable dataclasses**, validated at construction time.
- **Voigt ordering**: `[xx, yy, zz, xy, xz, yz]` with unscaled shears.
- **Index convention**: lowercase `i,j,k,l` = spatial; uppercase `I,J,K,L` = material.
- **JIT budget**: max 512 unrolled lines per `@ti.func`, 2000 per `@ti.kernel`.
- **Constitutive models**: Hyperelastic models derive stress via `sympy.diff` of strain energy Ψ. Dissipative models (e.g. J2 plasticity) use algorithmic tangent from return mapping — never force strain energy formulation on these.
- **Tests**: every new module needs a corresponding test file. Use `pytest.mark.slow` for Taichi compilation tests, `pytest.mark.gpu` for GPU tests.

## Codex mirrors

Claude-specific repo assets are mirrored for Codex under `.agents/`:

- **Skills and command mirrors**: `.agents/skills/`
- **Rule mirrors**: `.agents/rules/`
- **Hook mirrors**: `.agents/hooks/`

Keep the original `.claude/` files intact. For Codex work, prefer the `.agents/` mirrors.

## Codex hook workflow

Codex does not execute `.claude/settings.json` hooks automatically. Mirror the same behavior manually with the repo-local helpers:

1. **Before editing any file**, run:
   ```bash
   bash .agents/hooks/protect-spec.sh <path> [<path> ...]
   ```
2. **After editing any Python file**, run:
   ```bash
   bash .agents/hooks/post-edit.sh <path> [<path> ...]
   ```
3. If `protect-spec.sh` exits non-zero, do not edit that file.

Do not modify the Claude hook implementations in `.claude/hooks/`; the `.agents/hooks/` files are Codex-side mirrors only.

## Path-scoped rules

Before editing the following paths, read the matching mirrored rule file:

- `packages/mechdsl-core/src/mechdsl/codegen/**` → `.agents/rules/codegen.md`
- `packages/mechdsl-core/src/mechdsl/ir/**` and `packages/mechdsl-core/src/mechdsl/lowering/**` → `.agents/rules/ir.md`
- `packages/mechdsl-core/src/mechdsl/symbolic/**` → `.agents/rules/symbolic.md`
- `packages/*/tests/**` → `.agents/rules/tests.md`

## Codex capability mirror

The following Claude-only assets now have Codex mirrors:

- `.claude/agents/add-constitutive-model/AGENT.md` → `.agents/skills/add-constitutive-model/SKILL.md`
- `.claude/agents/convention-checker/AGENT.md` → `.agents/skills/convention-checker/SKILL.md`
- `.claude/agents/golden-updater/AGENT.md` → `.agents/skills/golden-updater/SKILL.md`
- `.claude/agents/ir-validator/AGENT.md` → `.agents/skills/ir-validator/SKILL.md`
- `.claude/agents/lint-fixer/AGENT.md` → `.agents/skills/lint-fixer/SKILL.md`
- `.claude/agents/pipeline-tracer/AGENT.md` → `.agents/skills/pipeline-tracer/SKILL.md`
- `.claude/agents/spec-checker/AGENT.md` → `.agents/skills/spec-checker/SKILL.md`
- `.claude/agents/test-coverage-mapper/AGENT.md` → `.agents/skills/test-coverage-mapper/SKILL.md`
- `.claude/agents/test-runner/AGENT.md` → `.agents/skills/test-runner/SKILL.md`
- `.claude/agents/verify-numerics/AGENT.md` → `.agents/skills/verify-numerics/SKILL.md`
- `.claude/commands/done.md` → `.agents/skills/done/SKILL.md`

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **MechDSL** (11747 symbols, 23987 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/MechDSL/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/MechDSL/context` | Codebase overview, check index freshness |
| `gitnexus://repo/MechDSL/clusters` | All functional areas |
| `gitnexus://repo/MechDSL/processes` | All execution flows |
| `gitnexus://repo/MechDSL/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
