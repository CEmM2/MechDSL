# Phase 5 Task Analysis

| Task ID | Title | Complexity (1-5) | Risk (1-5) | Combined Score | Blocked By | Blocks | Model |
|---------|-------|-----------------|------------|----------------|------------|--------|-------|
| P5-1 | Define Taichi as the only stable backend for the canonical LaTeX compile path. | 1 | 1 | 2 | — | P5-5, P7-1, P7-2, P7-5, P7-6 | Sonnet 4.6 (docs-tier, low risk) |
| P5-2 | Mark MFEM/MOOSE printers as experimental backend surfaces. | 2 | 2 | 4 | — | — | Sonnet 4.6 |
| P5-3 | Add a small façade layer if needed to present codegen in the design-doc style while preserving current emitters. | 3 | 2 | 5 | — | — | Sonnet 4.6 (cmplx=3 triggers Sonnet/Opus rule) |
| P5-4 | Ensure the Taichi path consumes enriched IR data where available rather than relying primarily on implicit summaries. | 4 | 4 | 8 | P2-1✓, P3-1✓, P4-1✓ | — | **Opus 4.6** (combined > 6) |
| P5-5 | Split codegen verification into stable vs experimental suites. | 2 | 2 | 4 | P5-1 | — | Sonnet 4.6 |

## File-scope overlap matrix (parallel batch eligibility)

| | P5-1 | P5-2 | P5-3 | P5-4 | P5-5 |
|---|---|---|---|---|---|
| P5-1 | — | docs README overlap | — | — | — |
| P5-2 |  | — | — | — | — |
| P5-3 |  |  | — | **taichi_printer.py overlap** | — |
| P5-4 |  |  |  | — | — |
| P5-5 |  |  |  |  | — |

**Verdict:** All sequential. P5-1↔P5-2 may both touch README; P5-3↔P5-4 both touch `taichi_printer.py`. P5-4 builds on P5-3 façade. P5-5 needs P5-1 done.

## Execution order (per Handoff_Phase_5.md + analysis)

1. P5-1 (solo, low risk) — unblocks P5-5
2. P5-2 (solo)
3. P5-3 (solo, façade groundwork)
4. **[user review checkpoint]**
5. P5-4 (solo, **Opus**, sequential — biggest task)
6. **[user review checkpoint]**
7. P5-5 (solo, blocked-label removed after P5-1 lands)
8. Phase handoff

## Failure-pattern scan (prior gates)

Scanned `gates/phase_{1,2,3}_gates.md` — recurring patterns to watch:
- **`extra_work`** flagged historically when implementers expanded scope (e.g. Phase-1 P1-2 over-tagged unrelated docs). For docs-tier P5-1/P5-2: keep change set narrow to listed surfaces.
- **`misunderstanding`** when "experimental" labelling was conflated with "deprecated"/"removed". P5-2 must preserve experimental code in-tree.
- **`integration_break`** on golden-file drift. P5-4 must keep `ArtifactBundle.content_hash` stable on existing fixtures (Handoff §Pointers).
