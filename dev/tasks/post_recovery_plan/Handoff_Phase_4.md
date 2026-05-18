# Phase 4 Handoff

> **From**: Phase 3 agent
> **To**: Phase 4 agent
> **Date**: 2026-05-01
> **Branch**: `post-recovery-plan_phase-3` (off `post-recovery-plan_phase-2` → main)
> **Plan**: `dev/plans/post_recovery_plan.md`

---

## Skills to Load Before Starting

- `Aut_Faciam`
- `taichi-gpu-sim` (Phase 4 wires nrpylatex into the symbolic layer; the bridge eventually feeds Taichi codegen)
- `sympy` (Phase 4 emits symbolic expressions consumable by `mechdsl.symbolic`)
- `nlm-skill` / `obsidian-cli` if any DSL-grammar docs need cross-referencing.

---

## Phase 3 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P3-1 | BC handoff paragraph in compile_latex docstring | (this branch, P3-1 commit) | 3/3 (test_p3_1) + ruff D clean + 1772/1772 fast suite | none |
| P3-2 | test_compile_latex_docstring.py regression guard | (this branch, P3-2 commit) | 6/6 (deliverable + meta-spec) + 17/17 -m docs + 1778/1778 fast suite | none |

**Overall**: 9 task-dedicated tests + 17 docs-tier tests pass; 1778/1778 fast suite green.

---

## Architecture and State After Phase 3

- **`compile_latex.__doc__`** (in `packages/mechdsl-core/src/mechdsl/__init__.py`) gained a NumPy-style "Boundary conditions" section between Parameters and Returns. The section enumerates Dirichlet/Neumann support, references `BoundaryCondition`, and documents the `f_ext` caller-provisioning contract plus the `f_ext_kernel` override semantics. Pre-existing D413 (blank line after Raises) cleared in the same edit.
- **Regression guard** — new file `packages/mechdsl-core/tests/test_compile_latex_docstring.py` (3 `@pytest.mark.docs` tests) reads `inspect.getdoc(compile_latex)` and asserts substring presence on `BoundaryCondition`, `f_ext` + caller-provisioning synonym, and Dirichlet/Neumann naming. The file lives at the canonical `tests/` root (not under `plan_tests/`) because it is a permanent contract guard.
- **P2-2 invariant updated** — `tests/plan_tests/post_recovery_plan/test_p2_2.py::test_docs_marker_selects_only_p7_doc_tier_tests` allowlist widened to admit `post_recovery_plan/test_p3_*.py` and `tests/test_compile_latex_docstring.py` as legitimate doc-tier homes (the original Phase 2 narrow check predated Phase 3's doc-tier additions).
- **No public API or solver changes**.

---

## Assumptions Made During Phase 3

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| Substring assertions (BoundaryCondition, f_ext, plus a caller-provisioning synonym set) are sufficient regression-guard granularity | tests/test_compile_latex_docstring.py | Per Phase 3 context decision: assert on lowercase keywords, not full sentences, to allow incidental copy-edits | Low — if the contract phrasing changes substantively, update the synonym set or add new substrings |
| Pre-existing D413 in compile_latex docstring should be cleared in the same commit as P3-1 | `__init__.py` Raises section trailing newline | Acceptance criterion 3 ("docstring linter passes") could not be satisfied with the pre-existing violation | Low — adjacent to the edit, single-line fix, no behavioural risk |
| P2-2 docs-collection invariant should widen rather than fork into a P3-specific test | test_p2_2.py allowlist | The invariant is "all `-m docs` nodeids belong to known doc-tier homes"; widening the allowlist preserves the invariant cleanly while supporting Phase 3 | Low — explicit prefix list is auditable; future doc-tier homes need an explicit allowlist entry |

---

## Next Phase Direction (Phase 4 — NRPyLaTeX math grammar integration)

Plan §lines 188+:
- New module `packages/mechdsl-core/src/mechdsl/frontend/math_parser.py` wrapping `nrpylatex` parser; normalize index conventions (lowercase spatial / uppercase material per 07-CONVENTIONS.md).
- `frontend/__init__.py` wires the math parser into the top-level pipeline so `$...$` math blocks reach symbolic.
- `symbolic/bridge.py` adapter from nrpylatex AST → mechdsl symbolic types.
- `tests/test_nrpylatex_round_trip.py` covers SVK first-PK, J2 yield, two-point tensor `F_{iI}`.
- New example under `dev/examples/svk_latex_math.tex` plus README listing.

Phase 4 has higher complexity / risk than Phase 3 — task analysis and execution should default to subagent dispatch (Sonnet/Opus) rather than direct implementation, especially for the bridge module and round-trip test.

---

## Open Items / Follow-ups

- None blocking Phase 4.
- After this branch merges to main, the Phase 2 `docs-tests` CI job will pick up the 6 new doc-tier nodeids on the next dispatch — first end-to-end CI validation of `tier:docs` routing.
