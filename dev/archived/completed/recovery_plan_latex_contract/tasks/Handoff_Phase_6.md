# Phase 6 Handoff (from Phase 5 — Re-anchor Taichi codegen as the stable path (R4))

**Predecessor phase:** Phase 5 (R4) — Taichi as MVP-stable, MFEM/MOOSE as experimental, façade over emit_* helpers, printer consumes enriched ElementIR.
**Successor phase:** Phase 6 (R5) — Integrate `algo2code` at the least risky seam.
**Handoff date:** 2026-04-28.
**Branch:** `SOSOVSKI/recovery-phase5` (PR pending; tip `838754a`).
**Plan:** `dev/plans/recovery_plan_latex_contract.md`.

---

## Skills to Load Before Starting

- `compile-check` — trace algo2code → PCG path through pipeline once integration lands.
- `update-golden` — if P6-1 wires PCG into the Newton driver and any golden snapshot covers solver output.
- `qmd-search` — search both `mechdsl-core` and `algo2code` codebases when designing the integration seam.

---

## Phase 5 Completion Summary

| Task ID | Title | Commit | Tests (pass/total) | Failing |
|---------|-------|--------|--------------------|---------|
| P5-1 | Define Taichi as the only stable backend (docs) | `538bed1` | 32/33 (1 intentional smoke skip) | 0 |
| P5-2 | Mark MFEM/MOOSE experimental (codegen marker + warning) | `7439014` + DRY in `d230f02` | 7/7 | 0 |
| P5-3 | TaichiCodegenFacade façade over emit_* | `302028b` + delegation patch `41bcf73` + polish `d230f02` | 27/27 | 0 |
| P5-4 | Printer prefers element_ir_dict + opt-in audit | `2ec85da` + polish `838754a` | 136/136 | 0 |
| P5-5 | stable_backend / experimental_backend pytest markers | `32a668c` + polish `838754a` | 42 pass + 3 expected skip | 0 |

**Aggregate:** **244 task-dedicated tests passing (P5-* + scoped regression)**, 0 failing across the phase. Full mechdsl-core fast suite at **1629 pass / 81 skipped / 110 deselected / 0 failed** (up from 1581 at Phase-4 close — +48 net plan tests across the phase including delegation patches and deferral cleanups).

**GitHub:** Phase 5 issue #145 closed. Task issues #175 (P5-1), #176 (P5-2), #177 (P5-3), #178 (P5-4), #179 (P5-5) all closed with `done` / `gate-a-pass` / `gate-b-pass` labels.

---

## Architecture and State After Phase 5

### Public surface

- **`mechdsl.compile_latex(...)`** and **`mechdsl.codegen.compile(problem_ir)`** docstrings now name Taichi as the only MVP-stable backend on the canonical LaTeX compile path; MFEM and MOOSE are documented as experimental with pointers to Plan B §B8 and recovery-plan Phase 5.
- **`mechdsl.codegen` `__all__`** = `["ExperimentalBackendWarning", "TaichiCodegenFacade", "compile"]`. Three public symbols, expressed via `from mechdsl.codegen import *` and consistent with the package docstring conventions.

### New / modified components

- **`packages/mechdsl-core/src/mechdsl/codegen/_experimental.py`** (new) — defines `ExperimentalBackendWarning(UserWarning)` and `warn_experimental_backend_once(state: dict, backend_name: str)`. The helper centralises the one-shot warning pattern used by both experimental printers (DRY refactor in P5-2 polish).
- **`mfem_printer.py`** and **`moose_printer.py`** — each carries `__experimental__: bool = True` plus `_warn_state: dict[str, bool] = {"warned": False}`. The public `emit()` calls `warn_experimental_backend_once(_warn_state, "MFEM" / "MOOSE")` on first use; subsequent calls are silent. Both modules export `ExperimentalBackendWarning` via `__all__` so autoflake doesn't strip the re-export.
- **`taichi_printer.py`** — gains:
  - Module-private helpers `_ir_field(bundle, key, default)`, `_ir_block(bundle, block_name)`, `_n_quadrature_points(bundle, default=8)` that prefer `bundle.element_ir_dict` (post-P4-5 canonical surface) and fall back to `bundle.element_ir_summary`.
  - `EmissionContext.verbose: bool = False` field (default off) gating `_emit_enrichment_audit`. When verbose AND enrichment present, the function emits an "Enriched-IR contract surface (recovery P5-4 audit)" block in the file's docstring listing stress measure, strain measure, tangent rank, n_quad, force `n_dof (n_nodes × dim)`, tangent `n_dof`, tangent symmetric.
  - `TaichiCodegenFacade` class (post-emit() tail addition) with 13 thin-delegation methods aggregating the existing `emit_*` helpers under one design-doc-aligned API. `make_context(*, verbose: bool = False)` is the keyword-only entrypoint for verbose audit; default emission stays byte-identical to legacy.
- **Default emission is byte-identical to pre-P5-4 codegen.** `ArtifactBundle.content_hash` is unchanged (covers `problem_ir_dict + element_ir_summary + contraction_plans` — none of which changed). Existing golden snapshots survive verbatim.

### Test taxonomy

- New pytest markers registered in `pyproject.toml`:
  - `stable_backend` — tests guarding the MVP-stable Taichi codegen contract (must pass on every push).
  - `experimental_backend` — tests exercising experimental backends (MFEM/MOOSE), may xfail/skip without blocking the stable contract.
- Module-level `pytestmark = pytest.mark.<name>` on:
  - **stable_backend** — `test_codegen.py`, `test_taichi_printer.py`, `test_taichi_printer_ul.py`, `test_emission_phase5.py`, `test_emission_verification.py`, `test_emit_lame_conversion.py`.
  - **experimental_backend** — `test_cross_backend.py`, `test_mfem_printer.py`, `test_moose_printer.py`.
- Selection counts: stable=189 / experimental=19 / disjoint intersection=0 (provably so).

### Side effect for Phase 6 to be aware of

- **`test_phase6_exit.py`** carries a `_INTENTIONAL_CLEANUP_MATCHES` whitelist that hard-codes line numbers in `test_emission_verification.py`. The Phase-5 P5-5 polish bumped lines 745→747 and 748→750 to compensate for the new `pytestmark` insertion. Future edits to the head of `test_emission_verification.py` will need similar updates — this is structural fragility, not Phase-5 scope.

---

## Phase 6 cross-phase blockers (status)

- **P6-1** is blocked by **P4-1** (✓ done in Phase 4 — `ElementIR` enrichment dataclasses landed). Cross-phase prerequisite satisfied.
- P6-2..P6-5 have no upstream dependencies inside the recovery plan that aren't already done.

---

## Recommended Phase 6 execution order

1. **P6-5** (R5.5) — docs-tier. Document `algo2code`'s role in the recovered architecture. Cheapest task; clarifies the integration intent before any code lands.
2. **P6-4** (R5.4) — docs-tier. Defer radial-return replacement explicitly. Keeps scope discipline before P6-1 lands.
3. **P6-1** (R5.1) — integration-tier. Add the optional `algo2code`-generated PCG path behind `LinearSolverInterface`. Largest task; needs the enriched `ElementIR` (P4-1) for any contract-surface coupling.
4. **P6-2** (R5.2) — unit-tier. Keep the imported solver path as default fallback. Mostly contract / wiring work.
5. **P6-3** (R5.3) — integration-tier. Add the stable end-to-end test for `algo2code` → PCG → Newton plumbing. Runs last so the production seam is in place.

---

## Pointers / tripwires for Phase 6

- **Solver adapter shape** — `solver/import_adapter.py:26-57` already exposes `LinearSolverInterface` (Protocol) plus `CGSolver` and `PCGSolver`. P6-1's "optional `algo2code`-generated PCG path" should add a third concrete adapter (e.g. `Algo2CodePCGSolver`) that satisfies the Protocol — do NOT modify the Protocol or existing adapters. This keeps `LinearSolverInterface` stable while new adapter is opt-in.
- **`algo2code` is sibling, runtime-free** — keep it that way. Per Phase-6 constraint "Keep `algo2code` runtime-independence intact". The integration seam goes one direction: `mechdsl-core` consumes generated PCG; `algo2code` does not depend on `mechdsl-core`.
- **Default fallback** — P6-2 says "Keep the current imported solver path as the default". Whatever P6-1 wires in must be opt-in (config flag, kwarg, or env var). Do not flip the default until P6-3's integration test proves the new path stable.
- **Stable contract preserved** — `mechdsl.compile()` and `compile_latex()` docstrings (P5-1) currently identify Taichi codegen as the MVP-stable backend. Linear-solver swap is orthogonal to codegen tier. P6 should NOT mention solver choice in those docstrings unless it materially changes the contract.
- **Marker hygiene** — new Phase-6 tests should pick up an appropriate marker. Pure unit tests covering `LinearSolverInterface` adapters are tier:unit; the P6-3 integration test is tier:integration. None should carry `stable_backend` / `experimental_backend` since those markers are codegen-scoped, not solver-scoped.
- **`element_ir_dict` consumption** — P5-4 introduced `_ir_field` / `_ir_block` / `_n_quadrature_points` helpers in `taichi_printer.py`. If P6-1 needs to read enrichment metadata to drive PCG sizing decisions, mirror this priority pattern (`element_ir_dict` first, fall back to `element_ir_summary`) rather than reinventing it. The helpers are module-private to `taichi_printer.py` today; if P6 needs them, lift them into a shared `mechdsl.codegen` private module.

---

## Assumptions made during Phase 5

| Assumption | Where it applies | Rationale | Risk if wrong |
|------------|------------------|-----------|---------------|
| `LocalForceDescriptor.layout` does not exist on the dataclass | P5-4 audit emitter substituted `n_dof (n_nodes × dim)` instead | Verified against current `element_ir.py`; spec-side wording predates dataclass shape | If `layout` is added later, P5-4 audit needs a one-line addition; defensive `if "layout" in ...` would auto-surface it (not currently in place) |
| `MaterialEvalContract.support_tier` does not exist on the dataclass | Same as above; audit surfaces `tangent_rank` instead with defensive `if "support_tier" in ...` check | Same as above | Auto-surfaces when added — no action needed |
| Conservative branch policy | P5-4 did NOT introduce new behavioural branches keying on `material_eval.stress_measure`; audit-only path satisfies P5-4-c1 | Per task guidance "do not introduce new branches if none exist today" | If a future task sniffs `problem_ir.formulation` and could be replaced with `element_ir_dict` reads, the routing helpers are already in place — minor refactor only |
| Cross-backend tests skip cleanly when MFEM/MOOSE absent | P5-5 marker selection independence relies on this | Verified locally: `test_cross_backend.py` 3 tests skip with explicit `MFEM_DIR`/`MOOSE_DIR` checks | If skip mechanism changes, the stable suite could pick up unintended deselections; covered by `test_p5_5.py` AST inspection |

---

## Known issues and deferred concerns

### Failing tests
None.

### Deferred Plan-B follow-ups (non-blocking, candidate for future phases)
1. **P5-3** — `inspect.signature` tests in `test_p5_3.py` use loose `"ctx" in params` checks now (loosened from exact lists during Phase-5 polish). No further action needed.
2. **P5-4** — `EmissionContext.verbose` placement among mutable-state fields is ad-hoc. If a second config flag joins later (e.g. `debug_comments`, `golden_mode`), refactor into nested `EmissionConfig` dataclass.
3. **P5-5** — A monkey-patch test that forces `mfem_printer` import to raise and asserts `pytest -m "stable_backend"` still passes would harden the independence guarantee beyond structural reflection. Out of scope for the regression-tier task; candidate for a Phase 7 alignment test.
4. **P5-1** — `test_no_regression_on_existing_test_suite` is intentionally a smoke skip (regression sentinel). CI enforces full regression externally. No action needed.

### Test coverage gaps
None affecting Phase 6 correctness. Phase-5 enrichment coverage is via P5-4's 8 tests + P5-3's 27 façade tests + the audit emitter is exercised at verbose=True only.

---

## Lessons learned

### Process
- **Subagent dispatch chains for batched polish:** the deferrals batches (3-leg Plan-B in `d230f02` and 3-leg P5-4/P5-5 polish in `838754a`) each required 2-3 agent hops because formatter autoflake stripped imports between turns when a helper was being introduced before its caller existed. Workaround that worked: add `__all__` lists to keep re-exports alive, OR inline imports inside helper bodies. Future polish batches that touch experimental_backend imports should pre-anchor the `__all__` first.
- **Hard-coded line-number whitelists are fragile.** `test_phase6_exit.py` had to be touched in P5-5 polish to compensate for the +2 line shift caused by `pytestmark` insertion in `test_emission_verification.py`. Phase 6 should consider replacing these with regex-or-marker-based matching when the file is next under maintenance — not a Phase-6 deliverable, but worth flagging.
- **Gate-B medium triage worked well.** User-elected fix-now path on P5-3 medium (trivial snapshot test) and P5-4 medium (façade verbose kwarg) rather than deferring kept the Plan-B backlog manageable. Recommend the same triage discipline for Phase 6.

### Physics and numerics
- Phase 5 was infrastructure-shaped (docs, markers, façade, audit comments, helper plumbing). No constitutive or numerical surprises encountered.
- `ArtifactBundle.content_hash` invariance held throughout — verbose audit comments live in the emitted Taichi source string, not in the bundle dict, so existing goldens survive verbatim.

---

## What Phase 6 Must Know Before Starting

- **Critical dependency:** `LinearSolverInterface` Protocol is the public seam. P6-1 ADDS a concrete adapter; do not modify the Protocol or existing CGSolver/PCGSolver classes.
- **High-risk task:** **P6-1** (integration-tier) is the largest. The risk is dragging `algo2code`-runtime dependencies into `mechdsl-core` — the import direction must stay one-way (mechdsl-core consumes algo2code-generated artifacts; algo2code stays runtime-free). Use `gitnexus_impact` before adding any cross-package import.
- **Recommended starting point:** **P6-5** (docs) first to anchor the architectural intent, then **P6-4** (defer radial-return), then code (**P6-1** → **P6-2** → **P6-3**). The plan-B-style "docs first" approach already paid off in Phase 5 (P5-1 unblocked P5-5).
- **Branch:** create `SOSOVSKI/recovery-phase6` from `838754a` (current Phase-5 tip).
- **Time-saver flagged from Phase 5:** if you spawn parallel subagents for any P6 task, watch for autoflake stripping freshly-added imports between hops. Either anchor with `__all__` upfront or inline the import inside the consumer.
