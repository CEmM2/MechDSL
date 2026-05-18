# Phase 5 Scaffold Validation

| Task ID | Title | Missing / Incomplete Fields | Scaffold Action |
|---------|-------|-----------------------------|-----------------|
| P5-1 | Define Taichi as the only stable backend for the canonical LaTeX compile path. | `verification_commands` empty, `test_artifacts` empty | auto-filled (populated in Step 4 after stub generation) |
| P5-2 | Mark MFEM/MOOSE printers as experimental backend surfaces. | `verification_commands` empty, `test_artifacts` empty | auto-filled (populated in Step 4 after stub generation) |
| P5-3 | Add a small façade layer if needed to present codegen in the design-doc style while preserving current emitters. | `verification_commands` empty, `test_artifacts` empty | auto-filled (populated in Step 4 after stub generation) |
| P5-4 | Ensure the Taichi path consumes enriched IR data where available rather than relying primarily on implicit summaries. | `verification_commands` empty, `test_artifacts` empty | auto-filled (populated in Step 4 after stub generation) |
| P5-5 | Split codegen verification into stable vs experimental suites. | `verification_commands` empty, `test_artifacts` empty | auto-filled (populated in Step 4 after stub generation) |

Note: All semantic fields (`objective`, `acceptance_criteria`, `implementation_steps`, `deliverables`, `risks`, `test_plan.tier`, `test_plan.cases`) are populated. Only `verification_commands` and `test_artifacts` are placeholder-empty — both are auto-derived after stub generation in Step 4.

## Scaffold Summary

| Metric | Value |
|--------|-------|
| Tasks scaffolded | 5 |
| Test cases assessed | 10 (2 per task) |
| Cases covered by existing tests | 1 (P5-1-c2 partial→covered via test_documentation.py) |
| Cases partially covered (stubs generated) | 6 (P5-1-c1, P5-2-c1, P5-2-c2, P5-3-c1, P5-3-c2, P5-5-c2) |
| Cases with no existing tests (stubs generated) | 3 (P5-4-c1, P5-4-c2, P5-5-c1) |
| New stub files created | 5 |
| Total new stubs generated | ~37 (P5-1: 8, P5-2: 2, P5-3: 19, P5-4: 8, P5-5: 3 — based on subagent reports; final counts in stub files) |
| Tasks fully covered by existing tests (no stub needed) | 0 |
| Tasks needing human review | 0 |
| Auto-filled fields | `verification_commands`, `test_artifacts` (both populated from stub paths + existing relevant test paths) |

## Existing Test Coverage Found

| Task ID | Test case | Existing test file | Function | Coverage |
|---------|-----------|-------------------|----------|----------|
| P5-1 | c1 (Stable examples use Taichi only) | `tests/test_documentation.py` | `TestTaskP5T2` | partial — examples run but does not verify MFEM/MOOSE not imported |
| P5-1 | c2 (deliverables present) | `tests/test_documentation.py` | `TestTaskP5T1`, `TestTaskP5T3` | covered — README, quickstart, API docs, examples |
| P5-2 | c1 (experimental marker in tests/docs) | `tests/plan_tests/recovery_plan_latex_contract/test_p1_2.py` | `TestTaskP1_2::test_mfem_printer_marked_experimental`, `test_moose_printer_marked_experimental` | partial — Phase-1 scope; needs Phase-5 R4 lens |
| P5-2 | c2 (deliverables present at codegen/** + docs) | `mfem_printer.py`, `moose_printer.py` docstrings | (n/a — source-level marker only) | partial — no `__experimental__` flag, no runtime warning |
| P5-3 | c1 (façade snapshot/API stability) | `tests/test_taichi_printer.py`, `tests/test_phase1_codegen_fixes.py` | `TestPreamble`, `TestConstitutivePresent`, `TestCM3FunctionRename` | partial — emit_* helpers tested in isolation; no façade aggregation tests |
| P5-3 | c2 (façade exports) | (none) | (none) | missing |
| P5-4 | c1 (canonical path with enriched IR) | `tests/plan_tests/recovery_plan_latex_contract/test_p4_1.py`, `test_p4_3.py`, `test_p4_5.py`, `tests/test_artifact_bundle.py`, `tests/test_einsum.py` | enriched IR round-trip + bundle tests | partial — IR carries enrichment but printer-side consumption not verified |
| P5-4 | c2 (deliverables) | (none) | (none) | missing |
| P5-5 | c1 (stable suite independent of experimental) | `tests/test_codegen.py`, `tests/test_cross_backend.py`, `tests/test_mfem_printer.py`, `tests/test_moose_printer.py` | (no stable/experimental marker split) | missing |
| P5-5 | c2 (deliverables at test_codegen*.py) | (existing files) | n/a | partial |

## Tasks Needing Human Review Before Execute

| Task ID | Title | Field | Issue |
|---------|-------|-------|-------|
| _(none)_ | All P5 tasks fully scaffolded; semantic fields complete; only auto-fillable fields were empty pre-scaffold. |  |  |

## Ready for Execute

Fully scaffolded:
- **P5-1**: Define Taichi as the only stable backend for the canonical LaTeX compile path.
- **P5-2**: Mark MFEM/MOOSE printers as experimental backend surfaces.
- **P5-3**: Add a small façade layer if needed to present codegen in the design-doc style while preserving current emitters.
- **P5-4**: Ensure the Taichi path consumes enriched IR data where available rather than relying primarily on implicit summaries.
- **P5-5**: Split codegen verification into stable vs experimental suites.

Needs human review before execution:
- _(none)_

## Recommended execution order (from Handoff_Phase_5.md)

1. P5-1 (docs) — unblocks P5-5
2. P5-2 (docs) — independent
3. P5-3 (unit) — façade over existing emit_* helpers
4. P5-4 (unit) — wire codegen onto `element_ir_dict`; largest task
5. P5-5 (regression) — stable/experimental suite split; runs last

