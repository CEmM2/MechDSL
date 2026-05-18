# Phase 5 Handoff (from Phase 4 — Enrich `ElementIR` and normalize lowering boundaries (R3))

**Predecessor phase:** Phase 4 (R3) — `ElementIR` enrichment, lowering refactor.
**Successor phase:** Phase 5 (R4) — Re-anchor Taichi codegen as the stable path.
**Handoff date:** 2026-04-27.
**Branch:** `SOSOVSKI/recovery-phase4` (PR pending).

## What Phase 4 delivered

| Task | Deliverable | Tests |
|------|-------------|-------|
| **P4-1** | Four optional contract dataclasses on `ElementIR` (`GeometrySummary`, `MaterialEvalContract`, `LocalForceDescriptor`, `LocalTangentDescriptor`) + `ElementIR.to_dict / from_dict`. | 25/25 |
| **P4-2** | `EinsumSpec` / `LocalisationResult` docstrings demoted to "derived view" + new `LocalisationResult.from_element_ir()` classmethod. | 9/9 |
| **P4-3** | `localise()` emits enriched `ElementIR` first, then derives the einsum optimizer view. `ArtifactBundle.from_pipeline` surfaces enrichment in `element_ir_summary`. | 15/15 |
| **P4-4** | `LocalisationError(UnsupportedError, ValueError)` re-exported from `mechdsl.lowering`. Centralised `_check_stable_path_combo` rejects axis-by-axis with Plan-B pointers. | 11/11 |
| **P4-5** | `ArtifactBundle.element_ir_dict` carries the canonical `ElementIR.to_dict()` surface; ownership hierarchy spelled out in the bundle docstring. | 10/10 |

**Aggregate:** 70 new plan-test cases across the five files. Full mechdsl-core suite at **1581 pass / 0 fail** (80 skipped, 110 deselected for slow/gpu/e2e markers). GitNexus reindexed: 15,291 → 15,575 nodes, 21,912 → 22,404 edges.

## What Phase 5 starts from

- The IR layer (Mechanics IR + Element IR) carries every contract block downstream codegen needs to make a stable Taichi-backend decision. Pre-recovery, codegen had to sniff `ProblemIR.formulation`, `element_type`, and `material.model` to pick stress measures, force layouts, and tangent symmetries; post-P4-3, all of that lives on `ElementIR.material_eval`, `ElementIR.local_force`, and `ElementIR.local_tangent`.
- `ArtifactBundle.element_ir_dict` is the canonical handoff surface: a JSON-serialisable record of every IR fact codegen needs.
- Lowering rejections are now `LocalisationError` instances with Plan-B phase pointers. Codegen does not need to re-implement these rejections — it can rely on lowering to fail before reaching the printer.

## Phase 5 cross-phase blockers (already satisfied)

- **P5-4** is blocked by **P2-1** (✓ done in Phase 2), **P3-1** (✓ done in Phase 3), and **P4-1** (✓ done now). All Phase-5 prerequisites that come from Phases 2/3/4 are satisfied.
- P5-1, P5-2, P5-3, P5-5 have no upstream dependencies inside the recovery plan; P5-5 only blocks on P5-1.

## Recommended Phase 5 execution order

1. **P5-1** (R4.1) — docs-tier. Define Taichi as the only stable backend. Cheap; unblocks P5-5.
2. **P5-2** (R4.2) — docs-tier. Mark MFEM/MOOSE as experimental on the codegen surface.
3. **P5-3** (R4.3) — unit-tier. Façade over the existing `emit_*` helpers in `taichi_printer.py` (R4.3 already half-done — see anchor in plan §Phase 5).
4. **P5-4** (R4.4) — unit-tier. Wire codegen to consume `element_ir_dict` instead of `element_ir_summary` for the new contract data. This is the largest of the Phase-5 tasks because it touches the printer body.
5. **P5-5** (R4.5) — regression-tier. Split codegen verification into stable vs experimental suites. Runs last so it can scope to the post-P5-1 stability tagging.

## Pointers / tripwires

- **`ArtifactBundle.content_hash` is intentionally unchanged** by P4-3 / P4-5. Existing golden files survive verbatim. If Phase 5 needs to extend the hash to cover `element_ir_dict`, plan a single golden-file regeneration commit and budget time for it (see `feedback_golden_budget.md` — ref-solver re-runs cost ~10min).
- **`element_ir_summary` is now derived** from the enriched IR. Phase 5 codegen should still read it for back-compat (the Taichi printer already does at `taichi_printer.py:333-352`), but should prefer `element_ir_dict` when consuming the P4-1 contract blocks.
- **`LocalisationError` is double-inheritance** (`UnsupportedError, ValueError`). Existing `except ValueError` callers continue to work. Phase 5 codegen tests can rely on either base class.
- **Phase 5 §B5.4 anchor correction note (2026-04-27):** the Phase-5 anchor in the recovery plan (now at L268 after P1-2 amendments) explicitly corrects the earlier wording about `emit*` helpers. Plan accordingly when wiring the façade.

## Open questions for Phase 5 owner

- Should `ArtifactBundle.from_pipeline` stop populating the legacy `element_ir_summary` once P5-4 wires codegen onto `element_ir_dict`? Recommendation: keep it for two more recovery phases, then deprecate in a Phase-7 alignment review.
- The `LocalForceDescriptor.contraction_sketch` and `LocalTangentDescriptor.contraction_sketch` fields are documentation-grade today (free-form strings). Phase 5 may want to formalise them so the Taichi printer can derive emission shapes from the IR rather than its own inline knowledge.
