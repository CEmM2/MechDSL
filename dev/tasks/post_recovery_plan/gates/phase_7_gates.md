# Phase 7 Gate History

Plan: `dev/plans/post_recovery_plan.md`
Branch: `post-recovery-plan_phase-7` (off `post-recovery-plan_phase-6`)
Started: 2026-05-01

---

## P7-1 — Restore `## Inventory` anchor (#239)

### Gate A — Spec Compliance (attempt 1, pass)
- Added `## Inventory` heading to `dev/examples/README.md` with 4 bullet links to existing sections (canonical, programmatic, LaTeX-math grammar, PCG seam).

### Gate B — Domain Quality (attempt 1, pass)
- Inventory entries link to existing anchors; no new sections invented.

### Gate C (attempt 1, pass)
- 1/1 task test passes.

```json
{"task": "P7-1", "gate": "C", "attempt": 1, "result": "pass"}
```

---

## P7-2 — Robustify `test_p7_3.py` ordering + path matching (#240)

### Gate A (attempt 1, pass)
- Replaced `text.find("compile_latex(")` with a `_first_in_runnable_blocks` helper that scans only markdown code-fence content (` ```python ... ``` `).
- Replaced single-prefix path matching with three-prefix tuple `("dev/examples/", "./dev/examples/", "/dev/examples/")`. Absolute paths covered because they always contain `/dev/examples/`.

### Gate B (attempt 1, pass)
- Helper local to the test method; no new module-level state.
- Comment in source explains why the relaxation is safe.

### Gate C (attempt 1, pass)
- 3/3 task + 2/2 `test_p7_3` pass.

```json
{"task": "P7-2", "gate": "C", "attempt": 1, "result": "pass"}
```

---

## P7-3 — Rename `gen_p7_2` + remove obsolete comment (#241)

### Gate A (attempt 1, pass)
- Module name now derived from `uuid.uuid4().hex` per invocation (`gen_p7_2_<hex>`); literal `name="gen_p7_2"` no longer appears.
- Traction-string-gap forward-pointer comment was already removed (Phase 1 closure landed in P1-5/P1-6); P7-3 only adds the renaming work.

### Gate C (attempt 1, pass)
- 3/3 task tests pass.

```json
{"task": "P7-3", "gate": "C", "attempt": 1, "result": "pass"}
```

---

## P7-4 — Trim `test_p7_6.py` to [100, 250] (#242)

### Gate A (attempt 1, pass — no-op)
- `test_p7_6.py` is 193 lines, already within [100, 250]. R1/R2/R3 pillar references all present (10 hits).
- No trim required; budget pinned by the test stub for future drift protection.

### Gate C (attempt 1, pass)
- 2/2 task + 2/2 `test_p7_6` pass.

```json
{"task": "P7-4", "gate": "C", "attempt": 1, "result": "pass", "evidence": "no-op (193 lines already in budget)"}
```

---

## P7-5 — `_SUPERSEDED.md` runtime-active vs archived (#243)

### Gate A (attempt 1, pass)
- Appended `## Runtime-active vs archived sub-deliverables` section with two markdown sub-headings (`### Runtime-active` and `### Archived`).
- Runtime-active bucket lists Plan-B sub-deliverables that still ship code (B0-B3 layer split, B5 Taichi printer, B6 J2 reference path, B7-B9 SVK + verification harness).
- Archived bucket lists planning artifacts only (handoffs, scaffold validations, Hex20/TET10 deferral, governance reports).

### Gate C (attempt 1, pass)
- 2/2 task tests pass.

```json
{"task": "P7-5", "gate": "C", "attempt": 1, "result": "pass"}
```

---

## P7-6 — GitNexus index refresh (#244)

### Gate A — deferred per "Allowed Deviations"
- Plan §"Allowed Deviations" requires explicit user authorization to run `npx gitnexus analyze`. `.gitnexus/meta.json` is absent in this checkout (no prior index).
- Test stubs skip with explanatory pytest.skip messages rather than fail. When user authorizes the refresh, both assertions become live (lastIndexed timestamp + embeddings preservation).

### Gate C (attempt 1, pass — skipped)
- 0/2 ran; 2/2 skipped with auth-required note.

```json
{"task": "P7-6", "gate": "C", "attempt": 1, "result": "pass", "evidence": "deferred per plan §Allowed Deviations; tests skip pending user authorization"}
```

---

## P7-7 — CI baseline-stability smoke job (#245)

### Gate A (attempt 1, pass)
- Added `baseline-stability` job to `.github/workflows/ci.yml`:
  - Triggers on `workflow_dispatch`, `push`, and `pull_request`.
  - Runs `uv sync --all-packages --all-groups --all-extras`.
  - Smoke-imports `algo2code` core modules + library entries.
  - Runs `uv run pytest --collect-only -q packages/algo2code/tests/ packages/mechdsl-core/tests/` to catch any regression that breaks test collection.

### Gate C (attempt 1, pass)
- 2/2 task tests pass; PyYAML parse confirms all workflow files syntactically valid.

```json
{"task": "P7-7", "gate": "C", "attempt": 1, "result": "pass"}
```

---

## P2-2 docs allowlist generalised (Phase 7 cleanup, recurring `integration_break`)

The docs-collection invariant tripped a fourth time once `post_recovery_plan/test_p7_*.py` stubs joined the docs tier (after P3-1, P4-5, P5-5 widenings). Phase 7 cleanup replaced the per-prefix list with a directory-prefix entry: any test under `post_recovery_plan/` is now admitted. Removes the recurring widen-on-each-phase pattern flagged in Handoff_Phase_6.md.
