# Handoff: Phase 9 → Phase 10

**From:** Phase 9 — Contraction template tuning
**To:** Phase 10 — MMS convergence + patch tests across elements
**Date:** 2026-04-18
**Phase 9 branch:** `plan-b_phase-9` (off `plan-b_phase-8` tip; Phases 5, 6, 7, 8, 9 not yet merged to main)
**Phase 9 commits:** `6480434` (P9-1 partial), `0405e2e` (P9-2), `dab2514` (P9-3)
**Phase 9 exit baseline:** **1307 passed / 81 skipped / 1 failed** in fast suite; the single failure is the P9-1 spec-prose test awaiting user apply of `/tmp/section9_new.md` (hook-protected path).

---

## What Phase 9 shipped

| Task | Title | Commits | Deliverables |
|------|-------|---------|--------------|
| P9-1 | Named contraction-family templates | `6480434` (partial) | `codegen/family_registry.py` (8-family taxonomy + classifier + EMISSION_SHAPES × 3 backends + ELEMENT_BACKEND_COVERAGE × 4 elements), `tests/test_p9_1_family_spec_completeness.py` (2/3 pass) |
| P9-2 | Family-aware emission dispatch | `0405e2e` | ContractionResult/ContractionPlan `family` field; `family_emitters` dispatch tables + `_dispatch_family` router in Taichi/MFEM/MOOSE printers; MECHDSL_FAMILY_EMITTERS feature flag; `tests/test_p9_2_family_emitters.py` (4/4 pass) |
| P9-3 | Budget regression across triples | `dab2514` | `tests/test_template_family_budget.py` (32 active / 80 justified skips), `tests/golden/template_family_emission_baseline.json`, `tests/tools/regen_p9_3_baseline.py` — **Phase 9 exit** |

### Acceptance evidence

- **8-family taxonomy** classifies every einsum string flowing through the codegen pipeline:
  DISPLACEMENT_GRADIENT, FORCE_INTEGRATION, MATERIAL_TANGENT_CONTRACTION,
  RANK2_OUTER, RANK2_SYMMETRIC_OUTER, TANGENT_DOUBLE_CONTRACTION,
  PUSH_FORWARD_RANK4, FALLBACK.
- **Dispatch reachability** confirmed on hot paths (not defined-but-uncalled, closing the Phase 8 Gate B pattern):
  - Taichi: lines 945 (DISPLACEMENT_GRADIENT), 996 (FORCE_INTEGRATION), 1067 (MATERIAL_TANGENT_CONTRACTION), 1165 (TANGENT_DOUBLE_CONTRACTION)
  - MFEM: lines 471, 493, 590
  - MOOSE: lines 445, 471
- **Byte-identity rollback**: `MECHDSL_FAMILY_EMITTERS=0` produces byte-identical output to legacy tier-only path (each per-family helper is a verbatim copy of the inline body it wraps).
- **Silent-fallback observability**: `_dispatch_family` emits `_logger.debug` when falling through to the legacy body. Under `PYTHONLOGLEVEL=DEBUG`, silent misclassification surfaces immediately.
- **Budget guarantee**: every realisable (element × formulation × material × backend) triple keeps `plan.tier in {1, 2}` (no @ti.func budget overflow). 16 realisable triples today, all on HEX8.
- **Wall-clock non-regression**: family-aware emission within 1.2× of tier-only baseline across all 16 triples. Measured range 0.9009 – 1.0761 (family-on occasionally *faster* than legacy because dispatch can shortcut work).

### Golden baseline

`packages/mechdsl-core/tests/golden/template_family_emission_baseline.json`
carries the per-triple median wall-clock numbers measured on this machine
at 2026-04-18, ratio tolerance 1.2, trials=5. Regenerate with
`uv run python packages/mechdsl-core/tests/tools/regen_p9_3_baseline.py`.

---

## Known gaps entering Phase 10

### 1. §9 spec prose patch pending user apply

Test 3 of P9-1 (`test_tier_and_family_are_orthogonal`) reads
`dev/design_docs/09-EINSUM-OPTIMISER.md` and asserts §9 contains the new
taxonomy prose. The replacement content is staged at `/tmp/section9_new.md`
(118 lines). The `.claude/hooks/protect-spec.sh` PreToolUse hook blocks
all automated writes to `dev/design_docs/`. User must apply manually
(`mv /tmp/section9_new.md` then hand-merge with lines 183-208 of the spec).
Phase 10 does **not** depend on this patch — the registry module is
authoritative for code paths; the spec patch closes documentation drift.

### 2. Non-HEX8 elements still skip

All 72 skipped cases (TET4, TET10, HEX20) point at §B5.1-5.3. Phase 5
work lands them. Phase 10's MMS matrix should be coded to unblock
automatically once §B5 completes (parametrize over `ElementType`; no
per-element branches in the test harness).

### 3. MFEM non-SVK materials

MFEM printer only supports SVK today (8 skips). Out-of-scope for Phase 10;
call out in the README if MMS runs MFEM only for SVK.

### 4. Taichi + Perzyna

Perzyna not wired in the Taichi codegen emitter yet (2 skips at
HEX8-TL-perzyna-taichi and HEX8-UL-perzyna-taichi). Phase 10's Perzyna
convergence study must either restrict backends or hand-wire the Taichi
emission for Perzyna.

---

## What Phase 10 needs

**Phase 10 scope (Plan B §B10, lines 257-259):**

> MMS convergence studies over the full (element × formulation × material ×
> backend) matrix. Each triple exercised at ≥4 refinement levels; observed
> order of convergence must match the element's theoretical rate within
> tolerance. Patch tests (constant-strain reproduction) at machine
> precision.

### Consumes from Phase 9

- **`mechdsl.codegen.family_registry`**: stable; read-only for Phase 10.
- **`MECHDSL_FAMILY_EMITTERS` flag**: leave defaulted ON. MMS runs should
  produce identical convergence rates flag-on vs flag-off (an extra guard
  test worth adding — byte-identity at emission should imply numerical
  identity at runtime).
- **`test_template_family_budget.py::_realisable_triples()`** helper (now
  in tests/): Phase 10 can reuse the same enumeration to stay in sync with
  the realisable matrix.

### Dependencies Phase 10 blocks on

- **P2-5** (analytical MMS solver infra) — already done at `35c7656`.
- **P5-7** (multi-element convergence harness) — pending §B5.
- **P9-3** — done.

### Suggested task breakdown (tentative)

- **P10-1**: MMS convergence rate assertion per realisable triple (≥4 levels).
- **P10-2**: Patch test (constant Cauchy-Green) per triple.
- **P10-3**: Convergence rate report artifact (JSON / Markdown summary).

---

## Branch / merge state

Phases 5, 6, 7, 8, 9 remain unmerged on separate branches. Phase 10 should
branch off `plan-b_phase-9` tip (`dab2514`) to keep the chain going. The
Phase 9 commits cleanly apply on top of Phase 8, and the cumulative fast
suite is 1307 passed — no regression vs Phase 8's 1286.

Before merging Phase 9 to main:

1. User applies `/tmp/section9_new.md` to the spec → P9-1 test 3 passes.
2. Merge P5 → P6 → P7 → P8 → P9 in that order (or rebase + squash as
   preferred).
3. Re-run `npx gitnexus analyze --embeddings` to refresh the knowledge
   graph (index last updated at 5465694).

---

## Phase 9 in one sentence

Phase 9 introduced a named-family realisation layer orthogonal to the
existing Tier 1/2/3 budget scheduling, wired it through all three
backend printers behind a feature flag with byte-identical rollback, and
proved via a 16-triple budget+wall-clock regression that the refactor
costs at most a 7.6 % overhead (and often saves a few percent).
