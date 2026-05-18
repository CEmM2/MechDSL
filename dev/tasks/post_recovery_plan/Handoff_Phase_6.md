# Phase 6 Handoff

> **From**: Phase 5 agent
> **To**: Phase 6 agent
> **Date**: 2026-05-01
> **Branch**: `post-recovery-plan_phase-5` (off `post-recovery-plan_phase-4`)
> **Plan**: `dev/plans/post_recovery_plan.md`

---

## Skills to Load Before Starting

- `Aut_Faciam`
- No domain-specific skills required — Phase 6 is test-layer hardening (regex matchers, helper extraction, robustness against fragile patterns).

---

## Phase 5 Completion Summary

| Task | Title | Tests pass/total | Notes |
|------|-------|------------------|-------|
| P5-1 | dev/algorithms/radial_return_j2.tex algpseudocode | 4/4 | algo2code parser smoke-parses |
| P5-2 | algo2code radial-return codegen test | 5/5 codegen + 5/5 meta-spec | JIT budget probe ≤ 512 |
| P5-3 | lib/plasticity.py dispatcher + feature flag | 5/5 | bit-equality under flag confirmed |
| P5-4 | imported vs algo2code parity test | 4/4 parity + 5/5 meta-spec | BASELINE_TOL=1e-12 |
| P5-5 | design-doc note (07-CONVENTIONS §11) | 3/3 | cross-task: P2-2 allowlist widened (3rd time) |

**Overall**: 31 task-dedicated tests pass; 1835/1835 fast suite green.

---

## Architecture and State After Phase 5

### New artifacts

- `dev/algorithms/radial_return_j2.tex` — canonical J2 radial-return algpseudocode source.
- `packages/algo2code/src/algo2code/library/radial_return_j2.py` — library wrapper (mirrors `library.pcg` pattern; reads canonical `.tex` at import time).
- `packages/mechdsl-core/src/mechdsl/lib/plasticity.py` — dispatcher: `radial_return`, `active_path_name`, `FEATURE_FLAG_ENV`.
- `packages/algo2code/tests/test_radial_return_codegen.py` — 5 codegen tests (parse, ast.parse, entry-point, JIT budget, deferral-doc).
- `packages/mechdsl-core/tests/test_j2_radial_return_parity.py` — 4 parity tests.
- `dev/design_docs/07-CONVENTIONS.md §11` — substitution doc (`MECHDSL_USE_IMPORTED_RR`, parity contract, stability soak).

### Public API additions

```python
from mechdsl.lib.plasticity import (
    radial_return,           # dispatcher
    active_path_name,        # "algo2code" | "imported"
    FEATURE_FLAG_ENV,        # "MECHDSL_USE_IMPORTED_RR"
    ReturnMappingResult,     # re-exported
)
```

`radial_return` signature is bit-identical to `mechdsl.symbolic.models.j2_power_law.radial_return`. Callers should switch their imports to `mechdsl.lib.plasticity` going forward.

---

## Assumptions & Deferrals

| Decision | Rationale | Risk |
|----------|-----------|------|
| algo2code path body is verbatim Python translation, not transpiled output | algo2code parser bugs (multi-letter scratch tokenisation, dropped `/` in some assignment LHS contexts) block direct emission. Documented in source-file header. | Low — parity test asserts bit-equality today; future parser fix replaces body with single `algo2code.transpile` call. |
| Note placed in `07-CONVENTIONS.md` not `06-PLASTICITY.md` | `06-PLASTICITY.md` does not exist. Plan permits either (line 252-256). | Low — doc lives next to other conventions; cross-linked from `dev/algorithms/`. |
| BASELINE_TOL = 1e-12 (parity tolerance) | Imported-path Newton tolerance is `1e-12`; parity uses same baseline-derived ceiling per plan line 267-268. | Low — bounded above 0 and ≤ 1e-9; tightening or loosening requires explicit constant edit. |

---

## Recurring failure mode (P2-2 docs allowlist) — Phase 6 cleanup target

The P2-2 docs-collection invariant has now tripped **three times** when phases add new doc-tier homes outside `recovery_plan_latex_contract/test_p7_*`:

- P3-1: added `post_recovery_plan/test_p3_*.py` and `tests/test_compile_latex_docstring.py`.
- P4-5: added `tests/test_nrpylatex_round_trip.py`.
- P5-5: added `post_recovery_plan/test_p5_*.py`.

The allowlist comment in `test_p2_2.py` now flags this as a Phase 6 cleanup target. **Recommended approach for Phase 6**: replace the explicit prefix list with a registry pattern — either read allowed-prefix entries from a tracker file, or expose a per-test-module marker that auto-registers a path as docs-tier-eligible. Phase 6's existing scope (test-layer hardening, replacing fragile patterns with robust matchers) is a natural home for this fix.

---

## Next Phase Direction (Phase 6 — test-layer hardening)

Plan §lines 274+:

- Extract `packages/mechdsl-core/tests/_e2e_helpers.py` shared module housing `_import_generated_module` and other helpers duplicated across e2e tests (item 12).
- `test_p7_4.py` notes-iteration robustness (replace `notes[0]` with iteration filtering by plan-referenced filename).
- Replace `test_phase6_exit.py` line-number whitelist with regex/marker pattern.
- Recommended: address the P2-2 docs allowlist registry pattern as part of this phase's cleanup scope.

Lower complexity than Phase 5. Most tasks are mechanical refactors with strong before/after assertions; main-thread direct implementation is fine.

---

## Open Items

- None blocking Phase 6.
- Post-merge of Phase 5 PR: `pytest -m docs` will collect 28 nodeids (was 24 after Phase 4) — the new `test_p5_5.py` adds 3 docs-tagged tests.
- Algo2code parser bugs (multi-letter scratch identifiers, dropped `/` in assignment contexts) remain pending — flagged in `algo2code.library.pcg` and now also `algo2code.library.radial_return_j2`. A future plan should clear them so the algo2code path can transpile rather than translate.
