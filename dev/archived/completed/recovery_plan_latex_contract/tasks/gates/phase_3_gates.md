# Recovery-plan Phase 3 Gate History

**Plan:** `dev/plans/recovery_plan_latex_contract.md`
**Phase:** 3 — Enrich `ProblemIR` into the semantic center again (R2)
**Branch:** `SOSOVSKI/back2latex`
**Started:** 2026-04-27
**Mode:** Per-task gate cycles (Gate A spec compliance + Gate B domain quality + Gate C tests, per task)

---

## P3-1 — Add optional semantic fields to ProblemIR

**Started:** 2026-04-27 ~07:13 GMT+3
**BASE_SHA (before task):** `975b7c958ed30c493ee26322dc4ffd36b6490160`
**Issue:** #160

### Implementer note

Added four small frozen dataclasses (`FieldSpec`, `DomainSpec`,
`MeshContract`, `ResidualContract`), each with its own `to_dict/from_dict`,
and four new optional fields on `ProblemIR` (defaults: empty tuple / None).
Extended `ProblemIR.to_dict` to always emit the four enrichment keys and
`ProblemIR.from_dict` to accept both legacy (no keys) and enriched dicts.
The Code reality anchor in the recovery plan said "ProblemIR has no
to_dict/from_dict today" — that turned out to be wrong (lines 336/353
already had them); P3-1 *extended* them rather than adding from scratch.

### Gate A — Spec Compliance

The task spec checks against recovery R2.1:
- ✓ Adds the four named fields exactly: `fields`, `domain`, `mesh_contract`, `residual_contract`.
- ✓ All optional with safe defaults — backward compatibility preserved.
- ✓ Round-trip preserved for both legacy and enriched dicts (verified by `test_p3_1::TestProblemIRRoundTrip`).
- ✓ `ProblemIR` remains `@dataclass(frozen=True)`.
- ✓ No optimizer / printer / lowering leakage in the new types.
- ✓ Test coverage: 4 standalone enrichment-dataclass round-trips + 2 ProblemIR-with/without enrichment + 4 round-trip / forward-compat / legacy-dict cases.

A spec-checker subagent was dispatched but did not return a final
verdict; its tool-use trail confirmed the same conclusions. Self-review
verdict: **PASS**.

```json
{
  "gate_a": {
    "review_status": "PASS",
    "spec_compliance": "all 4 fields named exactly, optional defaults, round-trip preserved, backward compat verified by 325/325 wider regression"
  }
}
```

### Gate B — Domain Quality

A `convention-checker` subagent reviewed the diff against
`.claude/rules/ir.md` and `dev/design_docs/07-CONVENTIONS.md`. Findings:

- minor: `DomainSpec.metadata` / `MeshContract.metadata` are `dict` fields
  on a frozen dataclass — frozen blocks attribute reassignment, not
  mutation through the dict. Intentional design (permissive metadata
  bag); flagged for awareness.
- minor: `FieldSpec.kind` accepts a bare `str` with no runtime guard
  against out-of-vocabulary values. Validation is deferred to P3-5 per
  the recovery plan.
- false-positive medium: subagent flagged `unit` and `integration` as
  unregistered pytest markers. Verified against `pyproject.toml` —
  both ARE registered. The agent read `.claude/rules/tests.md`
  (a partial reminder, not the canonical config). Cleared.

```json
{
  "gate_b": {
    "review_status": "PASS",
    "review_score": 95,
    "issues": {"minor": 2, "medium": 0, "high": 0, "critical": 0},
    "false_positives_cleared": ["unit/integration markers (pyproject.toml has them)"]
  }
}
```

### Gate C — Tests

```
uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p3_1.py -v
=> 10 passed in 0.05s
```

Wider regression sweep (heavy ProblemIR consumers):

```
uv run pytest \
    packages/mechdsl-core/tests/test_mechanics_ir.py \
    packages/mechdsl-core/tests/test_mechanics_ir_configuration.py \
    packages/mechdsl-core/tests/test_compile_pipeline.py \
    packages/mechdsl-core/tests/test_e2e_taichi.py \
    packages/mechdsl-core/tests/test_e2e.py \
    packages/mechdsl-core/tests/test_codegen.py \
    packages/mechdsl-core/tests/test_taichi_printer.py \
    packages/mechdsl-core/tests/test_mfem_printer.py \
    packages/mechdsl-core/tests/test_moose_printer.py \
    packages/mechdsl-core/tests/test_localise.py \
    packages/mechdsl-core/tests/test_einsum.py \
    packages/mechdsl-core/tests/test_documentation.py \
    packages/mechdsl-core/tests/test_full_pipeline.py \
    packages/mechdsl-core/tests/plan_tests/ \
    -m "not slow and not gpu"
=> 325 passed, 8 skipped (P3-{2,3,4,5} stubs), 6 deselected
```

```json
{
  "gate_c": {
    "task_audit_command": "uv run pytest packages/mechdsl-core/tests/plan_tests/recovery_plan_latex_contract/test_p3_1.py -v",
    "task_audit_passed": 10,
    "task_audit_total": 10,
    "wider_regression_passed": 325,
    "wider_regression_total": 333,
    "wider_regression_skipped_stubs": 8,
    "exit_code": 0,
    "pass_rate": 100.0
  }
}
```

### Outcome

P3-1 **done**. ProblemIR is now Plan-2-Tasks-shaped semantically: four
optional enrichment fields carry the information that Plan A / drift made
implicit, with full backward compatibility. The next task in dependency
order is P3-4 (define a stable ProblemIR minimal subset for the
MVP-stable contract; independent of P3-2/P3-3/P3-5 — only blocked by
P3-1 which is now done).
