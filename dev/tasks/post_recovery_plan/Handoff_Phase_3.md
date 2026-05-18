# Phase 3 Handoff

> **From**: Phase 2 agent
> **To**: Phase 3 agent
> **Date**: 2026-05-01
> **Branch**: `post-recovery-plan_phase-2`
> **Plan**: `dev/plans/post_recovery_plan.md`

---

## Skills to Load Before Starting

- `Aut_Faciam` (this pipeline)
- `claude-md-management:revise-claude-md` (if `compile_latex` docstring touches CLAUDE.md surface)

Phase 3 is a docstring-only contract clarification. No constitutive-model or codegen skills required.

---

## Phase 2 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P2-1 | Register `docs` pytest marker (pyproject + tests.md) | b82cb6a | 3/3 (test_p2_1) + 1765/1765 fast suite | none |
| P2-2 | Swap `@pytest.mark.integration` → `@pytest.mark.docs` on test_p7_3..6 | 841fad2 | 2/2 (test_p2_2) + 8/8 (-m docs) + 1767/1767 fast suite | none |
| P2-3 | Add `docs-tests` CI job + audit | d0e0765 | 2/2 (test_p2_3) + ci.yml YAML-valid + 1769/1769 fast suite | none |

**Overall test status**: 7/7 task-dedicated tests passing; 1769/1769 fast suite green; 8/8 doc-tier tests selected by `pytest -m docs`.

---

## Architecture and State After Phase 2

- **Marker registry** — `pyproject.toml` `[tool.pytest.ini_options].markers` now includes `"docs: documentation-anchor / doc-tier tests"`. `.claude/rules/tests.md` ## Markers section lists `@pytest.mark.docs`. The marker name is the canonical entry — never use `@pytest.mark.integration` as a doc-tier substitute again.
- **Doc-tier tests** — `test_p7_3.py`, `test_p7_4.py`, `test_p7_5.py`, `test_p7_6.py` (under `packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/`) now carry `@pytest.mark.docs` on every test method. Eight nodeids total.
- **CI workflow** — `.github/workflows/ci.yml` has a new `docs-tests` job (between `budget-regression` and EOF) that runs `uv run pytest packages/mechdsl-core/tests/ -m docs --tb=short -q`. Triggered by `workflow_dispatch`, `pull_request`, or any PR carrying the `tier:docs` label.
- **Stub harness** — three new test files under `packages/mechdsl-core/tests/plan_tests/post_recovery_plan/test_p2_{1,2,3}.py` permanently codify the marker-registration / decorator-state / workflow-selector invariants. They run in the fast suite (tier `unit` / `integration`).

No new public APIs, fields, or solver kernels.

---

## Assumptions Made During Phase 2

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| Fast-tier selector `-m "not slow and not gpu and not e2e"` already covers docs-tier tests in normal CI runs | `ci.yml` test job | docs is none of slow/gpu/e2e; the existing selector is set-complement | Low — if a future tier (e.g. `nightly`) needs to also exclude docs, must update both selectors |
| Dedicated `docs-tests` job is opt-in (`workflow_dispatch` / PR / `tier:docs` label) | `ci.yml` `docs-tests` job | Avoids tripling test invocations on every push when fast-tier already covers | Low — visible in PR check list; can be promoted to always-on later |
| `test_p7_6.py` should also carry `@pytest.mark.docs` despite having no prior marker | the swap commit | Plan §Phase 2 explicitly enumerated test_p7_6.py among the affected files | Low — if test_p7_6 is later determined non-doc, drop the decorator |

---

## Next Phase Direction (Phase 3)

Phase 3 — `compile_latex` boundary-condition handoff docstring (plan §lines 156+):
- Add a paragraph to `compile_latex` docstring (`packages/mechdsl-core/src/mechdsl/__init__.py`, around line 33) describing: LaTeX directives populate `BoundaryCondition` slots; numeric `f_ext` is supplied separately by caller; current Dirichlet/Neumann support level.
- Author/extend `packages/mechdsl-core/tests/test_compile_latex_docstring.py` to assert the BC-handoff paragraph exists and references `BoundaryCondition`.

Phase 3's verifying test is naturally a doc-tier test — register it with `@pytest.mark.docs` (the marker now exists, no fallback needed).

---

## Open Items / Follow-ups

- None blocking Phase 3.
- Post-merge of the Phase 2 PR, the new `docs-tests` CI job's first execution will validate the workflow change end-to-end.
