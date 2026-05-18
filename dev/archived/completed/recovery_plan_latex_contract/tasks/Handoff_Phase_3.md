# Recovery-plan Phase 2 Handoff

> **From**: Phase 2 agent
> **To**: Phase 3 agent
> **Date**: 2026-04-27
> **Branch**: SOSOVSKI/back2latex (compressed exec; no dedicated phase branch)
> **Plan**: dev/plans/recovery_plan_latex_contract.md

---

## Skills to Load Before Starting

- `Aut_Faciam` (ScaffoldPhase + ExecPhase / ExecTask).
- `gitnexus-impact-analysis` — Phase 3 modifies `ir/mechanics_ir.py`, which is one of the most heavily consumed files in the package. Run impact analysis before every edit.
- `convention-checker` — Phase 3 adds new fields to a frozen dataclass; the supported-subset rules in `.claude/rules/ir.md` apply.

---

## Phase 2 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing Tests |
|---------|-------|--------|--------------------|---------------|
| P2-1 | compile_latex façade in mechdsl/__init__.py | ca79e7b | 4/4 | none |
| P2-4 | Reconcile MVP P2.x rows with recovery tasks | 8602cae | 4/4 | none |
| P2-2 | build_context as documented secondary; README LaTeX-first | 2526e45 | 4/4 | none |
| P2-3 | Frontend split (parser-of-record vs adapter) | 7a3c395 | 6/6 | none |
| P2-5 | LaTeX-source frontend contract test suite | 7b9f3eb | 6/6 | none |
| P2-6 | Contract-level error coverage via compile_latex | (this batch) | 10/10 | none |

**Overall test status**: 34/34 Phase-2-dedicated audit + integration tests passing; 53/53 across recovery-plan Phase 1 + Phase 2 combined; 278/278 across the wider regression set (plan_tests + IR + codegen + frontend + compile_pipeline).

---

## Architecture and State After Phase 2

> What the codebase looks like NOW. The next agent must understand this before touching anything.

- **`mechdsl/__init__.py`** is the new public entry surface. Two exports: `compile` (legacy programmatic, preserved verbatim) and **`compile_latex(source: str, profile: str = "mvp") -> ArtifactBundle`** (canonical MVP-stable). The thin `_problem_ir_from_context` helper at the bottom is internal — Phase 3 may either keep it as-is or migrate the logic into the IR layer (R2.2 / P3-2 cover that).
- **`mechdsl/frontend/__init__.py`** module docstring splits public entry points into Canonical and Secondary sections. `build_context()` is preserved and still functional, just demoted in docs.
- **`mechdsl/frontend/ARCHITECTURE.md`** is new. It pins NRPyLaTeX as the parser of record for math grammar and identifies the local triad (parser.py = scanner; directives.py = normalizer; build_context = validator; two_point.py = index validator).
- **MVP_plan tracker** retagged: P2.1–P2.5 are now `implemented-via-substitute` with substitute citations.
- **No code-generator changes** in Phase 2. Codegen / IR / lowering surfaces are untouched. The only Phase-2 production-code edit was `mechdsl/__init__.py` (added `compile_latex` + adapter); everything else was docstrings or doc files.

---

## Assumptions Made During Phase 2

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|-----------------|-----------|---------------|
| The thin `_problem_ir_from_context` adapter belongs in `mechdsl/__init__.py` for now | P2-1 | Smallest blast radius: keeps the recovery plan additive and avoids touching IR construction in Phase 2. R2.2 / P3-2 will pick the canonical home. | If Phase 3 prefers it on `ProblemIR` itself (e.g. `ProblemIR.from_context(ctx)` factory), the adapter will move — that's a normal Phase-3 refactor, not a regression. |
| nrpylatex math-grammar integration is out of scope for Phase 2 | P2-3 ARCHITECTURE.md | The recovery plan's R1 constraints explicitly say "do not block recovery on full parser completeness; a thin but canonical stable subset is sufficient at first" | If Phase 4 or 5 needs `\Psi`-style user-defined energy functions, integration becomes urgent — but those phases are explicitly later in the recovery sequence. |
| The MVP context-dict schema (10 keys) is stable for the Phase-2 lifetime | P2-1 adapter | The schema has been stable across Plan B; no in-tree caller has rotated its keys. | If a Plan B follow-up adds context keys the adapter ignores, only those keys would be silently dropped — non-fatal, but worth a Phase-3 audit to widen the adapter / move to ProblemIR.from_context. |

---

## Known Issues and Deferred Concerns

### Failing tests (quantified)
| Test name/file | Failure reason | Impact on Phase 3 |
|----------------|---------------|-------------------|
| (none) | — | — |

### Known limitations
- `compile_latex` only accepts `profile="mvp"`. Future profiles (extended LaTeX math, non-canonical backends) will need to be added explicitly with a fail-closed default.
- The Phase-2 regression suite was scoped to plan_tests + IR + codegen + frontend + compile_pipeline. Wider integration tests (e.g. `test_e2e_taichi.py`) were not re-run; they were not edited and don't import the new `compile_latex` symbol.

### Test coverage gaps
- No Phase-2 test exercises a *file-on-disk* LaTeX source — only inline `_LATEX = r"""..."""` strings. If a Phase-3 regression adds a `compile_latex_file(path)` helper, it should grow a parallel test.

---

## Lessons Learned

### Process
- Compressed exec on Phase 2 was the right call once we reached unit/integration tier — the diffs were genuinely small per task, and the per-phase Gate C cycle gave the same evidence as per-task gates would have, at ~4× lower cost.
- The MVP tracker has both a 10-column main task table and a 3-column verification mapping table, both starting with `| P2.`. Tests that scan the file by ID prefix must discriminate by column count (P2-4 hit this).
- Always run `uv sync --all-packages --all-groups --all-extras` before the wider regression sweep; the bare `uv run python` venv is minimal and will collect-error on numpy.

### Physics and numerics
- N/A — Phase 2 did not change any constitutive / kinematics / lowering code paths.

---

## What Phase 3 Must Know Before Starting

> Phase 3 enriches `ProblemIR` with new optional semantic fields. This is a **frozen-dataclass** edit to one of the most consumed surfaces in the package. The risk profile is materially higher than Phase 2.

- **Critical surface**: `packages/mechdsl-core/src/mechdsl/ir/mechanics_ir.py`. The `ProblemIR` dataclass (around line ~210, post-Phase-1 docstring edits) has roughly six widely-consumed fields. Phase 3 / R2.1 = canonical task `P3-1` adds `fields`, `domain`, `mesh_contract`, `residual_contract` as **optional** with safe defaults, plus `ProblemIR.to_dict() / from_dict()` (see Code reality anchor in the recovery plan: `BoundaryCondition` and `MaterialSpec` already serialize, but `ProblemIR` itself does not).
- **High-risk task: P3-1 (semantic field addition)** — this is the gate for the rest of Phase 3 + cross-phase blockers P4-1, P4-3, P5-4. Run `gitnexus_impact` (or `grep -rn "ProblemIR(" packages/`) before adding fields. Backward compatibility is mandatory: every existing call site must keep working without source changes.
- **Recommended starting point**: P3-1, then P3-2 (compatibility constructors / adapters — this is where the `_problem_ir_from_context` helper from Phase 2 may want to migrate to `ProblemIR.from_context()`).
- **Constraint reminder**: `ProblemIR` must remain `@dataclass(frozen=True)`. New fields must have safe defaults. Do not push optimizer-specific or printer-specific data into `ProblemIR` — those belong on `ElementIR` (Phase 4) or downstream.
- **Test discipline**: every IR change must keep `test_mechanics_ir.py` (15+ tests) and `test_compile_pipeline.py` (10+ tests) green. The `test_p3_*` audit suite under `plan_tests/recovery_plan_latex_contract/` is the canonical phase verification.
- **Environment**: run `uv sync --all-packages --all-groups --all-extras` before any pytest invocation that touches the broader suite.
